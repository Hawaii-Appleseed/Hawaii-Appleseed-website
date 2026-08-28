#!/usr/bin/env python3
"""
Ground a testimony header block in real LegiScan data instead of brackets.

Returns the four things the appleseed-testimony skill otherwise has to leave as
placeholders: the bill's official title, its current draft suffix (HD1/SD2/CD1),
the committee hearing it, and the hearing date and time.

Usage:
    python bill_lookup.py HB1884
    python bill_lookup.py HB1884 --json
    python bill_lookup.py HB1884 --hearing-window 21

Requires LEGISCAN_API_KEY (free tier, 30K queries/month:
https://legiscan.com/user/register). Wraps writing-bot/legiscan_client.py,
which resolves the active HI session per run and caches by change_hash.
"""
from __future__ import annotations
import argparse, json, os, re, sys
from pathlib import Path

WB = Path(os.path.expanduser("~/HawaiiAppleseed/writing-bot"))
sys.path.insert(0, str(WB))

DRAFT_RE = re.compile(r"\b((?:[HS]D)\s?\d|CD\s?\d)\b", re.I)


def die(msg: str, code: int = 1):
    print(msg, file=sys.stderr)
    sys.exit(code)


def norm(bill: str) -> str:
    return re.sub(r"\s+", "", bill).upper()


def pick_committee(payload: dict) -> str | None:
    c = payload.get("committee") or {}
    if isinstance(c, dict) and c.get("name"):
        chamber = c.get("chamber") or ""
        name = c["name"]
        return f"{chamber} Committee on {name}".strip() if chamber and "Committee" not in name else name
    # Fallback: the referral line gives committee ABBREVIATIONS (e.g. "TRN, FIN"),
    # not a letterhead-ready name. Return it flagged so it is never pasted as-is.
    for h in reversed(payload.get("history") or []):
        m = re.search(r"referred to ([A-Z/, ]+)", str(h.get("action", "")), re.I)
        if m:
            return f"[COMMITTEE — LegiScan gave only the referral abbreviations " \
                   f"'{m.group(1).strip()}'; expand from the hearing notice]"
    return None


def current_draft(payload: dict) -> str | None:
    """Latest draft suffix from the texts list, else from the bill number itself."""
    texts = payload.get("texts") or []
    for t in reversed(texts):
        label = str(t.get("type") or t.get("type_id") or "")
        m = DRAFT_RE.search(label)
        if m:
            return m.group(1).upper().replace(" ", "")
    m = DRAFT_RE.search(str(payload.get("bill_number", "")))
    return m.group(1).upper().replace(" ", "") if m else None


def lookup(bill_number: str, window_days: int) -> dict:
    if not os.environ.get("LEGISCAN_API_KEY"):
        die(
            "LEGISCAN_API_KEY is not set.\n"
            "  Get a free key at https://legiscan.com/user/register (30K queries/month), then:\n"
            "      export LEGISCAN_API_KEY=...\n"
            "  Until then, leave the header block bracketed and tell the user which\n"
            "  hearing details you could not verify. Do not guess them.",
            2,
        )
    try:
        import legiscan_client as ls
    except Exception as e:  # noqa: BLE001
        die(f"could not import legiscan_client from {WB}: {e}")

    want = norm(bill_number)
    session_id = ls.get_active_hi_session_id()
    master = ls.get_master_list(session_id)

    entry = master.get(want) or next(
        (v for k, v in master.items() if norm(k) == want), None
    )
    if not entry:
        die(f"{want} is not in the LegiScan master list for HI session {session_id}.\n"
            f"  Check the bill number, or the bill may not have been introduced this session.")

    payload = ls.get_bill(entry["bill_id"], change_hash=entry.get("change_hash"))
    hearings = ls.upcoming_hearings(payload, window_days=window_days)
    hearing = hearings[0] if hearings else None

    title = (payload.get("title") or "").strip()
    subject = re.sub(r"^relating to\s+", "", title, flags=re.I).strip() or title
    draft = current_draft(payload)

    return dict(
        session_id=session_id,
        bill=want,
        draft=draft,
        bill_with_draft=f"{want} {draft}" if draft else want,
        title=title,
        subject=subject,
        status=payload.get("status_desc") or payload.get("status"),
        last_action=(payload.get("history") or [{}])[-1].get("action"),
        last_action_date=(payload.get("history") or [{}])[-1].get("date"),
        committee=pick_committee(payload),
        hearing_date=(hearing or {}).get("date"),
        hearing_time=(hearing or {}).get("time"),
        hearing_desc=(hearing or {}).get("description"),
        hearing_location=(hearing or {}).get("location"),
        url=payload.get("url") or payload.get("state_link"),
    )


def header_block(d: dict) -> str:
    bill = d["bill_with_draft"]
    subject = d["subject"] or "[SUBJECT]"
    committee = d["committee"] or "[COMMITTEE — not returned by LegiScan; confirm from the hearing notice]"
    when = "[HEARING DATE/TIME — no hearing scheduled in the window; confirm from the notice]"
    if d.get("hearing_date"):
        when = d["hearing_date"] + (f", at {d['hearing_time']}" if d.get("hearing_time") else "")
    return "\n".join([
        "Testimony of the Hawaiʻi Appleseed Center for Law and Economic Justice",
        f"[Support|Opposition|Comments] for {bill} – Relating to {subject}",
        committee,
        when,
    ])


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("bill")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--hearing-window", type=int, default=14)
    a = ap.parse_args()

    d = lookup(a.bill, a.hearing_window)
    if a.json:
        print(json.dumps(d, indent=2, ensure_ascii=False))
        return

    print(f"LegiScan · HI session {d['session_id']}")
    for label, key in [("Bill", "bill_with_draft"), ("Title", "title"), ("Status", "status"),
                       ("Last action", "last_action"), ("Committee", "committee"),
                       ("Hearing", "hearing_date"), ("Location", "hearing_location"),
                       ("URL", "url")]:
        if d.get(key):
            print(f"  {label:<12}: {d[key]}")
    if not d.get("hearing_date"):
        print(f"  {'Hearing':<12}: none scheduled in the next {a.hearing_window} days")
    print("\nHeader block — pick the position word, verify the rest against the hearing notice:\n")
    print(header_block(d))


if __name__ == "__main__":
    main()
