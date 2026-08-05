#!/usr/bin/env python3
"""
Hawaiʻi Appleseed bill watcher.

Each run:
  1. Resolve the current HI legislative session via LegiScan.
  2. Parse positions.md for every bill HA has a position on.
  3. Cross-reference with the master list; pull bills with hearings in the next N days.
  4. Skip bills already drafted (state JSON dedup).
  5. Skip bills already covered by a recent testimony file in testimony/<topic>/.
  6. For each remaining bill: retrieve relevant chunks via bot.retrieve and
     generate a pre-draft via bot.generate.
  7. Emit a digest (Google Doc + WhatsApp short summary).

Usage:
  .venv/bin/python bill_watcher.py --dry-run
  .venv/bin/python bill_watcher.py --bill HB2049
  .venv/bin/python bill_watcher.py                       # full run
  .venv/bin/python bill_watcher.py --hearing-window 14   # widen the window
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import bot  # noqa: E402
import legiscan_client as ls  # noqa: E402

STATE_PATH = Path.home() / ".openclaw" / "state" / "bill-watcher.json"
LOG_PATH = Path.home() / ".openclaw" / "logs" / "appleseed-bill-watcher.log"
REPORTS_FOLDER_ID = "1_YUKRBPkpeOF1ml3KQk5mt74FLTyxWll"  # OpenClaw Reports
WHATSAPP_NOTIFY = Path.home() / ".openclaw" / "scripts" / "whatsapp-notify.sh"

BILL_RE = re.compile(r"\b([HS]B\s?\d{3,5})(?!\d)")
TOPIC_MAP = {
    "labor & wages": "labor",
    "tax fairness & budget": "tax-and-budget",
    "housing & renters": "housing",
    "food equity": "food-equity",
    "transportation": "transportation",
}


def log(msg: str):
    line = f"[{datetime.now().isoformat(timespec='seconds')}] {msg}"
    print(line, flush=True)
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# positions.md parsing
# ---------------------------------------------------------------------------

def parse_positions(text: str) -> dict[str, dict]:
    """Return {bill_number: {topic, snippets: [text]}}. A bill mentioned in N
    places gets N snippets; topic comes from the enclosing ### header."""
    out: dict[str, dict] = {}
    topic = None
    for line in text.splitlines():
        m = re.match(r"^###\s+(.+)$", line.strip())
        if m:
            heading = m.group(1).strip().lower()
            topic = TOPIC_MAP.get(heading, heading)
            continue
        if re.match(r"^#{1,4}\s", line) and not line.startswith("###"):
            # Top-level section change (e.g., "## Voice signature") — stop tagging bills under a topic
            topic = None
            continue
        for bill in BILL_RE.findall(line):
            num = bill.upper().replace(" ", "")
            entry = out.setdefault(num, {"topic": topic, "snippets": []})
            entry["snippets"].append(line.strip())
    return out


def existing_testimony_bills() -> set[str]:
    """Bill numbers that already have a testimony file in the corpus."""
    out: set[str] = set()
    for p in (ROOT / "testimony").rglob("*.txt"):
        m = BILL_RE.search(p.name)
        if m:
            out.add(m.group(1).upper().replace(" ", ""))
    return out


# ---------------------------------------------------------------------------
# State dedup
# ---------------------------------------------------------------------------

def load_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text())
        except Exception:
            pass
    return {"version": 1, "entries": {}}


def save_state(state: dict):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2))


def state_key(bill_number: str, hearing_date: str) -> str:
    return f"{bill_number}_{hearing_date}"


# ---------------------------------------------------------------------------
# Drafting
# ---------------------------------------------------------------------------

def draft_for(bill_number: str, topic: str | None, position_snippets: list[str], hearing: dict,
              *, collection, anthropic_client, n_results: int = 8) -> tuple[str, list[tuple[str, dict]]]:
    snippet_blob = "\n".join(position_snippets)
    where = bot.build_where_filter(doc_type=None, topic=topic, year_min=2023)
    query = f"Hawaiʻi Appleseed position and prior testimony on {bill_number}. " + snippet_blob[:500]
    hits = bot.retrieve(collection, query, n_results, where)

    prompt = (
        f"Draft testimony on {bill_number} for a {hearing.get('description') or 'committee'} hearing "
        f"on {hearing.get('date')}. Hawaiʻi Appleseed's position from positions.md:\n\n"
        f"{snippet_blob}\n\n"
        f"Follow HA's standard testimony structure. Cite retrieved sources inline."
    )
    text, _usage = bot.generate(prompt, hits, mode="testimony", client=anthropic_client)
    return text, hits


# ---------------------------------------------------------------------------
# Delivery
# ---------------------------------------------------------------------------

def upload_doc(title: str, body: str) -> str | None:
    """Write `body` to a Google Doc in the OpenClaw Reports folder; return webViewLink or None on failure."""
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as tmp:
        tmp.write(body)
        path = tmp.name
    try:
        r = subprocess.run(
            ["gog", "docs", "create", title, f"--file={path}", f"--parent={REPORTS_FOLDER_ID}", "--json"],
            capture_output=True, text=True, timeout=60,
        )
        if r.returncode != 0:
            log(f"  gog docs create failed: {r.stderr.strip()}")
            return None
        try:
            data = json.loads(r.stdout)
            return data.get("webViewLink") or data.get("webViewURL")
        except Exception:
            return r.stdout.strip() or None
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def whatsapp(msg: str) -> None:
    if not WHATSAPP_NOTIFY.exists():
        log("  whatsapp-notify.sh missing; skipping notify")
        return
    try:
        subprocess.run([str(WHATSAPP_NOTIFY), msg], check=False, timeout=20)
    except Exception as e:
        log(f"  whatsapp notify failed: {e}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="don't draft, don't upload, don't notify")
    ap.add_argument("--bill", help="run for one bill only (e.g. HB2049)")
    ap.add_argument("--hearing-window", type=int, default=7, help="days ahead to look for hearings (default 7)")
    ap.add_argument("--no-skip-existing", action="store_true", help="draft even if testimony/<topic>/HBXXXX_* exists")
    args = ap.parse_args()

    if not os.environ.get("LEGISCAN_API_KEY"):
        log("ERROR: LEGISCAN_API_KEY not set — bill watcher cannot run.")
        sys.exit(1)
    need_anthropic = not args.dry_run
    if need_anthropic and not os.environ.get("ANTHROPIC_API_KEY"):
        log("ERROR: ANTHROPIC_API_KEY not set — cannot generate drafts. Run with --dry-run or set the key.")
        sys.exit(1)

    log("=== Bill watcher starting ===")
    positions_text = bot.load_positions()
    positions = parse_positions(positions_text)
    log(f"positions.md: {len(positions)} unique bills referenced")

    if args.bill:
        b = args.bill.upper().replace(" ", "")
        positions = {b: positions[b]} if b in positions else {}
        if not positions:
            log(f"  {args.bill} not in positions.md — exiting")
            sys.exit(0)

    session_id = ls.get_active_hi_session_id()
    log(f"active HI session_id: {session_id}")
    master = ls.get_master_list(session_id)
    log(f"master list: {len(master)} bills")

    existing = existing_testimony_bills() if not args.no_skip_existing else set()
    state = load_state()

    items_to_draft = []          # list of (bill_number, topic, hearing, snippets, bill_payload)
    items_skipped = []           # list of (bill_number, reason)

    cache = ls._load_cache()
    for bill_number, position in positions.items():
        master_entry = master.get(bill_number)
        if not master_entry:
            items_skipped.append((bill_number, "not in master list this session"))
            continue
        if bill_number in existing:
            items_skipped.append((bill_number, "testimony file already in corpus"))
            continue
        bill = ls.get_bill(master_entry["bill_id"], change_hash=master_entry.get("change_hash"), cache=cache)
        hearings = ls.upcoming_hearings(bill, window_days=args.hearing_window)
        if not hearings:
            continue
        hearing = hearings[0]  # earliest
        key = state_key(bill_number, hearing["date"])
        if key in state["entries"] and state["entries"][key].get("drafted"):
            items_skipped.append((bill_number, f"already drafted for {hearing['date']}"))
            continue
        items_to_draft.append((bill_number, position["topic"], hearing, position["snippets"], bill))

    log(f"to draft: {len(items_to_draft)}  |  skipped: {len(items_skipped)}")
    for b, reason in items_skipped:
        log(f"  skip {b}: {reason}")

    if args.dry_run:
        for b, topic, h, _snips, _bill in items_to_draft:
            log(f"  DRY {b} ({topic or '?'}) — {h['date']} {h.get('description','')[:60]}")
        log("=== Bill watcher dry-run complete ===")
        return

    if not items_to_draft:
        # Send a short "nothing new" only if it's helpful — usually we stay quiet.
        log("=== Nothing to draft ===")
        return

    import anthropic
    anthropic_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    collection = bot.index_documents(force=False)

    sections = []
    for bill_number, topic, hearing, snippets, bill in items_to_draft:
        log(f"  drafting {bill_number} (hearing {hearing['date']})")
        try:
            draft, hits = draft_for(bill_number, topic, snippets, hearing,
                                    collection=collection, anthropic_client=anthropic_client)
        except Exception as e:
            log(f"    draft failed: {e}")
            continue
        srcs = sorted({m.get("source", "?") for _, m in hits})
        sections.append(
            f"# {bill_number} — hearing {hearing['date']}\n\n"
            f"**Topic:** {topic or 'unknown'}  \n"
            f"**Bill title:** {bill.get('title','?')}  \n"
            f"**Hearing:** {hearing.get('description','')} @ {hearing.get('location','?')}\n\n"
            f"## Position (from positions.md)\n\n" + "\n".join(snippets) + "\n\n"
            f"## Pre-draft testimony\n\n{draft}\n\n"
            f"## Retrieved sources\n\n" + "\n".join(f"- {s}" for s in srcs) + "\n"
        )
        state["entries"][state_key(bill_number, hearing["date"])] = {
            "at": datetime.now().isoformat(timespec="seconds"),
            "drafted": True,
            "hearing_date": hearing["date"],
        }

    if not sections:
        log("all drafts failed; not uploading")
        save_state(state)
        return

    doc_title = f"Bill watcher drafts — {date.today().isoformat()}"
    body = f"# {doc_title}\n\n" + "\n\n---\n\n".join(sections)
    doc_url = upload_doc(doc_title, body)
    if doc_url:
        log(f"  doc: {doc_url}")
        for bill_number, _, h, _, _ in items_to_draft:
            k = state_key(bill_number, h["date"])
            if k in state["entries"]:
                state["entries"][k]["doc_url"] = doc_url
    save_state(state)

    short = "⚖️ Bills with hearings (no testimony yet): " + ", ".join(
        f"{b} ({h['date'][5:]})" for b, _, h, _, _ in items_to_draft[:5]
    )
    if doc_url:
        short += f". Drafts: {doc_url}"
    whatsapp(short)
    log("=== Bill watcher complete ===")


if __name__ == "__main__":
    main()
