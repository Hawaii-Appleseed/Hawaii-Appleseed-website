#!/usr/bin/env python3
"""Save the last good copy of the Legislature bill-status feed for the assistant (content/bill-status-snapshot.json).

The feed (tax-fairness/data/bill-status.json) is rewritten by a scheduled job from capitol.hawaii.gov, which sometimes answers
HTTP 403; a refresh made of nothing but errors would otherwise erase what the assistant knows about each bill.
build_index.py uses the live feed for every bill that has data and this snapshot for the rest.

    python3 chatbot/snapshot_bills.py            # refuses unless nearly every bill in the feed has data
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_index as b  # noqa: E402


def main() -> int:
    d = json.loads(b.BILL_STATUS.read_text(encoding="utf-8"))
    bills, area = b._usable_bills(d)
    total = len(d.get("bills", {}))
    if not total or len(bills) < 0.9 * total:
        print(f"refusing: only {len(bills)} of {total} bills in {b.BILL_STATUS} have data (a failed refresh?)", file=sys.stderr)
        return 1
    snap = {"_comment": "Last good copy of the bill-status feed's latest action per bill; see snapshot_bills.py. Used by build_index.py only for bills the live feed has no data for.",
            "generatedAt": d.get("generatedAt"), "source": d.get("source"),
            "areas": {k: area[k] for k in sorted(area)}, "bills": {k: bills[k] for k in sorted(bills)}}
    b.BILL_SNAPSHOT.write_text(json.dumps(snap, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {b.BILL_SNAPSHOT.relative_to(HERE.parent)}: {len(bills)} bills, feed pulled {snap['generatedAt']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
