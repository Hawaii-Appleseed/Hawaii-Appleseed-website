#!/usr/bin/env python3
"""
File a drafted testimony on the staff hub, where it becomes (or lands on) the
hearing's testimony task with the draft attached, due at the Capitol's 24-hour
cutoff, ready for sign-off. No copy-paste: the task opens with the draft and
the Send-for-review controls.

Usage:
    python file_to_hub.py draft.txt --bill SB3125 --hearing 2026-03-05T10:15 \\
        --committee WAM --position support --author abbey@hiappleseed.org \\
        [--html out/SB3125.html] [--area "Tax and Budget"] [--chamber Senate] \\
        [--note "CITATION NEEDED: the DBEDT figure"] [--doc https://docs.google.com/...]

    --hearing    the hearing's day and time as the notice gives them, Honolulu
                 time: 2026-03-05T10:15 (or just the day, 2026-03-05)
    --committee  the committee code(s) from the notice: WAM, FIN, JDC/WAM
    --position   support, oppose or comments
    --author     the drafter's hub address (defaults to APPLESEED_EMAIL, then
                 git's user.email when it is an @hiappleseed.org one)
    --html       the rendered page from render_testimony.py; the hub then files
                 it as a Google Doc in the issue area's Testimony folder and
                 links the task to it (--area picks the folder: "Tax and Budget",
                 "Housing", "Food Equity", "Transportation Equity", "Labor & Other")
    --note       a flag for the reviewer, repeatable (what you could not source,
                 a hearing detail you could not verify)
    --doc        a Doc that already exists, instead of --html
    --hub        the hub's origin (default https://staff-updates-internal.pages.dev;
                 HUB_URL overrides; staging is https://staging.staff-updates-internal.pages.dev)

Prints where the task is. Filing the same bill and hearing again replaces the
draft on the same task (a new version); it never makes a second task. Testimony
the hub already shows as submitted is refused: it has gone in.

The hub sits behind Cloudflare Access. This script sends the Access SERVICE
TOKEN the hub's other machine callers use, read from the macOS Keychain
(`apps-script:CF_ACCESS_CLIENT_ID` / `apps-script:CF_ACCESS_CLIENT_SECRET`) or
from CF_ACCESS_CLIENT_ID / CF_ACCESS_CLIENT_SECRET in the environment. It never
prints them. Without them it exits 2 and says so: the draft is still on disk,
and the person asks Devin Thomas to file it or to put the token on their Mac.
Never paste a token into chat or into this file.
"""
from __future__ import annotations
import argparse, json, os, re, subprocess, sys, urllib.error, urllib.request

DEFAULT_HUB = "https://staff-updates-internal.pages.dev"
ROUTE = "/api/events-sync/testimony"
POSITIONS = ("support", "oppose", "comments")


def die(msg: str, code: int = 1):
    print(msg, file=sys.stderr)
    sys.exit(code)


def keychain(name: str) -> str:
    """One Keychain item, or '' (no `security` on this machine, or no item)."""
    try:
        r = subprocess.run(["security", "find-generic-password", "-s", f"apps-script:{name}", "-w"],
                           capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return r.stdout.strip() if r.returncode == 0 else ""


def token() -> tuple[str, str]:
    cid = os.environ.get("CF_ACCESS_CLIENT_ID") or keychain("CF_ACCESS_CLIENT_ID")
    sec = os.environ.get("CF_ACCESS_CLIENT_SECRET") or keychain("CF_ACCESS_CLIENT_SECRET")
    if not (cid and sec):
        die("No Access service token on this machine, so the draft cannot be filed on the hub\n"
            "from here. It is still on disk. Either:\n"
            "  - ask Devin Thomas to file it (send the draft and the hearing details), or\n"
            "  - have Devin put the hub's service token in this Mac's Keychain\n"
            "    (apps-script:CF_ACCESS_CLIENT_ID / CF_ACCESS_CLIENT_SECRET).\n"
            "Do not ask anyone to paste a token into chat.", 2)
    if not cid.endswith(".access"):
        die("The Keychain's CF_ACCESS_CLIENT_ID does not end in .access, as every Cloudflare\n"
            "service-token id does; it is not the token. Ask Devin to check it.", 2)
    return cid, sec


def default_author() -> str:
    a = os.environ.get("APPLESEED_EMAIL", "").strip()
    if a:
        return a
    try:
        r = subprocess.run(["git", "config", "user.email"], capture_output=True, text=True, timeout=10)
        a = r.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        a = ""
    return a if a.lower().endswith("@hiappleseed.org") else ""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("draft", help="the plain-text draft (header block, greeting, body, footnotes)")
    ap.add_argument("--bill", required=True)
    ap.add_argument("--hearing", required=True, help="2026-03-05T10:15, Honolulu time")
    ap.add_argument("--committee", required=True, help="WAM, FIN, JDC/WAM")
    ap.add_argument("--position", required=True, choices=POSITIONS)
    ap.add_argument("--author", default=default_author())
    ap.add_argument("--chamber", default="", help="House or Senate")
    ap.add_argument("--html", help="the rendered .html from render_testimony.py, to file as a Doc")
    ap.add_argument("--area", default="", help="the issue area's Testimony folder for the Doc")
    ap.add_argument("--doc", default="", help="a Doc that already holds it")
    ap.add_argument("--note", action="append", default=[], help="a flag for the reviewer; repeatable")
    ap.add_argument("--hub", default=os.environ.get("HUB_URL", DEFAULT_HUB))
    ap.add_argument("--dry-run", action="store_true", help="print the filing (without the token) and stop")
    a = ap.parse_args()

    if not re.match(r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2})?$", a.hearing):
        die("--hearing is the day and time, Honolulu: 2026-03-05T10:15 (or 2026-03-05)")
    if not a.author:
        die("Say who drafted it: --author <their hub address> (or set APPLESEED_EMAIL)")
    try:
        text = open(a.draft, encoding="utf-8").read()
    except OSError as e:
        die(f"could not read the draft: {e}")
    html = ""
    if a.html:
        try:
            html = open(a.html, encoding="utf-8").read()
        except OSError as e:
            die(f"could not read the rendered page: {e}")

    bill = re.sub(r"\s+", "", a.bill).upper()
    filing = {
        "bill": bill, "position": a.position, "author": a.author,
        "hearing": {"when": a.hearing, "committee": a.committee, "chamber": a.chamber},
        "draft": {"text": text, **({"html": html} if html else {}), **({"url": a.doc} if a.doc else {}),
                  **({"area": a.area} if a.area else {}),
                  "name": f"{bill} {a.committee.upper()} Testimony (draft)"},
        "notes": "\n".join(n.strip() for n in a.note if n.strip()),
    }
    if a.dry_run:
        shown = dict(filing); shown["draft"] = {**filing["draft"], "text": f"<{len(text)} chars>", **({"html": f"<{len(html)} chars>"} if html else {})}
        print(json.dumps(shown, indent=2, ensure_ascii=False))
        return 0

    cid, sec = token()
    req = urllib.request.Request(a.hub.rstrip("/") + ROUTE, method="POST", data=json.dumps(filing).encode("utf-8"),
                                 headers={"CF-Access-Client-Id": cid, "CF-Access-Client-Secret": sec,
                                          "Content-Type": "application/json", "Accept": "application/json",
                                          "User-Agent": "appleseed-testimony/file_to_hub"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            body, status = r.read().decode("utf-8", "replace"), r.status
    except urllib.error.HTTPError as e:
        body, status = e.read().decode("utf-8", "replace"), e.code
    except urllib.error.URLError as e:
        die(f"could not reach the hub at {a.hub}: {e.reason}")
    try:
        out = json.loads(body)
    except ValueError:
        out = None
    if status in (401, 403) or (out is None and "cloudflareaccess" in body):
        die("The hub's Access turned the service token away (HTTP %d). Ask Devin to check the token." % status, 2)
    if not isinstance(out, dict):
        die(f"the hub answered HTTP {status} with something other than a filing: {body[:300]}")
    if "error" in out:
        die(f"not filed (HTTP {status}): {out['error']}")

    hub = a.hub.rstrip("/")
    task = out.get("task") or {}
    verb = "made" if out.get("created") else "updated"
    print(f"Filed on the hub: task {verb}, draft {task.get('draft_text', {}).get('version', 1)}.")
    print(f"  {task.get('title', '')}")
    print(f"  due {task.get('due') or '?'} · held by {task.get('assignee') or 'nobody'} · sign-off: drafting")
    print(f"  task:   {hub}{out.get('url', '')}")
    print(f"  packet: {hub}{out.get('packet', '')}")
    doc = task.get("draft_doc") or {}
    if doc.get("url"):
        print(f"  doc:    {doc['url']}")
    if out.get("warning"):
        print(f"  note: the draft is on the task, but the Doc was not made: {out['warning']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
