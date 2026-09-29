#!/usr/bin/env python3
"""
Keep the skills' reference files in step with the writing-bot corpus.

Two kinds of file, handled differently:

  generated   appleseed-testimony/reference/citations.md is pure output of
              build_citations.py, so it is rebuilt here and the workflow
              commits any change.
  measured    testimony-profile.md and appleseed-voice's style-profile.md are
              written by hand around measured numbers; regenerating them would
              throw away the prose. Each states the corpus size it measured.
              This compares that to the corpus today and reports drift past
              DRIFT, so a person re-measures (profile_testimony.py prints the
              testimony numbers).

    python scripts/refresh_skill_reference.py          # rebuild + report
    python scripts/refresh_skill_reference.py --json   # machine-readable, for CI

Exit 0 either way; the workflow decides what to do with the report.
"""
from __future__ import annotations

import argparse, json, os, re, subprocess, sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILLS = REPO / ".claude" / "skills"
WB = REPO / "writing-bot"
DRIFT = 0.10  # re-measure once the corpus is 10% bigger or smaller than measured

PROFILES = [
    # (profile file, regex for the documented count, how to count the corpus today)
    (SKILLS / "appleseed-testimony/reference/testimony-profile.md",
     r"\*\*(\d+) real testimonies\*\*",
     lambda: sum(1 for p in (WB / "testimony").glob("*/*.txt") if not p.name.startswith("sample_"))),
    (SKILLS / "appleseed-voice/reference/style-profile.md",
     r"Derived from all (\d+) posts",
     lambda: sum(1 for _ in (WB / "blog-posts").glob("*/*.txt"))),
]


def rebuild_citations() -> bool:
    out = SKILLS / "appleseed-testimony/reference/citations.md"
    before = out.read_bytes()
    env = dict(os.environ, APPLESEED_WEBSITE=str(REPO))
    subprocess.run([sys.executable, str(out.with_name("build_citations.py")), "-o", str(out)],
                   check=True, env=env, stdout=subprocess.DEVNULL)
    return out.read_bytes() != before


def drift() -> list[dict]:
    rows = []
    for path, rx, count in PROFILES:
        m = re.search(rx, path.read_text(encoding="utf-8"))
        if not m:  # the doc was reworded; fail loudly rather than go quiet
            raise SystemExit(f"{path.relative_to(REPO)}: can't find the measured corpus size "
                             f"({rx!r}) — update PROFILES in {Path(__file__).name}")
        measured, now = int(m.group(1)), count()
        rows.append({"file": str(path.relative_to(REPO)), "measured": measured, "now": now,
                     "change": (now - measured) / measured, "stale": abs(now - measured) / measured >= DRIFT})
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    changed, rows = rebuild_citations(), drift()
    if a.json:
        print(json.dumps({"citations_changed": changed, "profiles": rows}))
        return 0
    print(f"citations.md: {'rebuilt — changed' if changed else 'current'}")
    for r in rows:
        flag = "STALE — re-measure" if r["stale"] else "ok"
        print(f"{r['file']}: measured {r['measured']}, corpus now {r['now']} ({r['change']:+.0%}) {flag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
