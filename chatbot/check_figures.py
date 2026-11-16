#!/usr/bin/env python3
"""Report every figure in the assistant's content that no published source states (see figures.py).

    python3 chatbot/check_figures.py                 positions only: the part that goes out unreviewed
    python3 chatbot/check_figures.py --all           also about.md and practical.md (from site pages, so expect more)
    python3 chatbot/check_figures.py --json          machine-readable, for the sign-off page
    python3 chatbot/check_figures.py --strict        exit 1 if any figure is unpublished and not accepted

Accept a figure on purpose in content/figures.json: {"allow": [{"section": "...", "figure": "usd:300000000", "reason": "..."}]}.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_index as b  # noqa: E402
import figures as fg  # noqa: E402

ALLOW = HERE / "content" / "figures.json"


def load_allow() -> list[dict]:
    return json.loads(ALLOW.read_text(encoding="utf-8")).get("allow", []) if ALLOW.exists() else []


def build_corpus() -> fg.Corpus:
    docs = list(b.corpus_docs(Counter()))
    feed = b.BILL_STATUS.read_text(encoding="utf-8") if b.BILL_STATUS.exists() else ""
    return fg.Corpus(docs, feed)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--all", action="store_true", help="also about.md and practical.md")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--show-accepted", action="store_true")
    ap.add_argument("--matches", action="store_true", help="also list the published sentence matched to each supported figure")
    a = ap.parse_args()
    files = ("positions.md", "about.md", "practical.md") if a.all else ("positions.md",)
    sections = [it for f in files for it in b.parse_sections(HERE / "content" / f)
                if it.get("group") != "Topics with no stated public position"]
    report = fg.check(sections, build_corpus(), load_allow())
    print(json.dumps(report, ensure_ascii=False, indent=1) if a.json else fg.render(report, a.show_accepted, a.matches))
    return 1 if a.strict and (report["none"] or report["qualifier"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
