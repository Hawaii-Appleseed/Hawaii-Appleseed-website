#!/usr/bin/env python3
"""Notice when the Tax Fairness Coalition's Pol.is poll picks up activity.

fetch-polis-report.py can already pull the poll, and polis-sync-primer.py can
already push the result into the primer-editor report. The manual step in the
middle is *noticing* that the poll moved — which today means remembering to go
look, and which is why a report update has more than once been prompted by
someone mentioning new votes rather than by us seeing them.

Exit codes follow the same contract as the DOTAX monitors in BudgetPrimerFinal:
    0   checked, nothing worth reporting
    10  material change — the workflow writes a packet and opens an issue
    1   the fetch failed or returned nothing parseable

"Material" deliberately excludes single stray votes. A poll that gains one
vote overnight is not news; a new idea, or a real burst of participation, is.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE.parent / "data" / "polis"
FETCHER = HERE / "fetch-polis-report.py"

# Tuned so ordinary trickle is quiet but a real push shows up. A single new
# idea always counts: someone took the trouble to write something.
NEW_IDEA_THRESHOLD = 1
PARTICIPANT_THRESHOLD = 3
VOTE_THRESHOLD = 15


def fetch(report_id: str, out: Path) -> dict:
    subprocess.run([sys.executable, str(FETCHER), report_id, "-o", str(out)],
                   check=True, capture_output=True, text=True)
    return json.loads(out.read_text())


def idea_key(idea: dict) -> str:
    """Stable identity for an idea: its pol.is tid if present, else its text."""
    for k in ("tid", "id", "comment_id"):
        if idea.get(k) is not None:
            return f"{k}:{idea[k]}"
    return "txt:" + " ".join(str(idea.get("text", idea.get("txt", ""))).split())[:160]


def summarize(cur: dict) -> dict:
    st = cur.get("stats", {})
    return {
        "participants": cur.get("participant_count", 0),
        "ideas": st.get("ideas", len(cur.get("ideas", []))),
        "votes": st.get("votes_cast", 0),
        "agree": st.get("agree", 0),
        "disagree": st.get("disagree", 0),
        "groups": len(cur.get("groups", [])),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("report_id", nargs="?", default="r3v45armukntdykxcyucd",
                    help="pol.is report id (default: TFC 2027 priorities)")
    ap.add_argument("--name", default="tfc-2027-priorities",
                    help="basename for the snapshot and packet files")
    ap.add_argument("--packet", help="write a change packet here on exit 10")
    a = ap.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    snapshot_path = DATA_DIR / f"{a.name}.json"
    # Fetch beside the snapshot, not over it: a failed or partial pull must not
    # destroy the baseline we diff against.
    tmp = snapshot_path.with_suffix(".fetching.json")

    try:
        cur = fetch(a.report_id, tmp)
    except subprocess.CalledProcessError as exc:
        tmp.unlink(missing_ok=True)
        print(f"fetch failed: {exc.stderr or exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        tmp.unlink(missing_ok=True)
        print(f"fetch failed: {exc}", file=sys.stderr)
        return 1

    if not cur.get("ideas"):
        tmp.unlink(missing_ok=True)
        print("poll returned no ideas — endpoint or report id may have changed",
              file=sys.stderr)
        return 1

    prev = {}
    if snapshot_path.is_file():
        try:
            prev = json.loads(snapshot_path.read_text())
        except Exception:  # noqa: BLE001
            prev = {}

    now, before = summarize(cur), summarize(prev) if prev else None

    if not prev:
        snapshot_path.write_text(json.dumps(cur, indent=2) + "\n")
        tmp.unlink(missing_ok=True)
        print(f"baseline written: {now}")
        return 0

    old_keys = {idea_key(i) for i in prev.get("ideas", [])}
    new_ideas = [i for i in cur["ideas"] if idea_key(i) not in old_keys]

    d_part = now["participants"] - before["participants"]
    d_votes = now["votes"] - before["votes"]

    material = (len(new_ideas) >= NEW_IDEA_THRESHOLD
                or d_part >= PARTICIPANT_THRESHOLD
                or d_votes >= VOTE_THRESHOLD)

    # Always refresh the snapshot: the point of the threshold is to stay quiet,
    # not to keep re-reporting the same drift until it crosses the line.
    snapshot_path.write_text(json.dumps(cur, indent=2) + "\n")
    tmp.unlink(missing_ok=True)

    if not material:
        print(f"no material change (participants {d_part:+d}, votes {d_votes:+d}, "
              f"new ideas {len(new_ideas)})")
        return 0

    lines = [
        f"# Pol.is poll activity — {cur.get('topic', a.name)}",
        "",
        f"Report: https://pol.is/report/{a.report_id}",
        f"Checked: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        "",
        "## Movement since the last check",
        "",
        "| | before | now | change |",
        "|---|---:|---:|---:|",
    ]
    for label, key in [("Participants", "participants"), ("Ideas", "ideas"),
                       ("Votes cast", "votes"), ("Agree", "agree"),
                       ("Disagree", "disagree"), ("Opinion groups", "groups")]:
        delta = now[key] - before[key]
        lines.append(f"| {label} | {before[key]} | {now[key]} | {delta:+d} |")
    lines.append("")

    if new_ideas:
        lines += [f"## {len(new_ideas)} new idea(s)", ""]
        for i in new_ideas:
            text = " ".join(str(i.get("text", i.get("txt", ""))).split())
            votes = []
            for k in ("agree_count", "agrees", "disagree_count", "disagrees"):
                if i.get(k) is not None:
                    votes.append(f"{k}={i[k]}")
            suffix = f"  \n  _{', '.join(votes)}_" if votes else ""
            lines.append(f"- {text}{suffix}")
        lines.append("")

    if now["groups"] != before["groups"]:
        lines += ["## Opinion groups changed", "",
                  f"Pol.is now clusters participants into {now['groups']} groups, "
                  f"was {before['groups']}. The report's group-by-group reading "
                  "is stale until it is regenerated.", ""]

    lines += [
        "## Next step",
        "",
        "Refresh the downstream report from the new pull:",
        "",
        "```bash",
        "python3 tax-fairness/scripts/polis-sync-primer.py",
        "```",
        "",
    ]

    text = "\n".join(lines)
    if a.packet:
        Path(a.packet).write_text(text)
        print(a.packet)
    else:
        print(text)
    return 10


if __name__ == "__main__":
    sys.exit(main())
