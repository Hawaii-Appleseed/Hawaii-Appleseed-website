#!/usr/bin/env python3
"""
Drive the real search.py Streamlit app headlessly via Streamlit's AppTest and
emit structured JSON about what rendered. This is the actual app code path
(widgets, filtering, dedup, highlight, source links, expanders) — not a
re-implementation — so it's a faithful "spin" of the UI without a browser.

Forces LOCAL embeddings (unsets OPENAI_API_KEY) to match run_search.sh.

Single query:
  .venv/bin/python eval/ui_probe.py --query "conveyance tax" [--doc-type publication]
      [--topic housing] [--year-min 2024] [--n 8] [--no-bm25] [--no-rerank]

Batch (one model load for the whole list — preferred for many queries):
  .venv/bin/python eval/ui_probe.py --scenarios scenarios.json
    where scenarios.json is a JSON list of objects with keys:
      query (required), doc_type, topic, year_min, n, no_bm25, no_rerank

Output: one line beginning `PROBE_RESULT:` (single) or `PROBE_RESULTS:` (batch),
followed by JSON. Grep that prefix to ignore any model-load noise on stdout.
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Silence model-load progress + force local embeddings BEFORE importing anything heavy.
os.environ.pop("OPENAI_API_KEY", None)
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
os.environ["TQDM_DISABLE"] = "1"
os.environ["TRANSFORMERS_NO_ADVISORY_WARNINGS"] = "1"

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "search.py"

from streamlit.testing.v1 import AppTest  # noqa: E402


def _texts(elements):
    out = []
    for el in elements:
        v = getattr(el, "value", None)
        if isinstance(v, str):
            out.append(v)
    return out


def probe(scenario: dict, timeout: int = 180) -> dict:
    q = scenario["query"]
    doc_type = scenario.get("doc_type", "(any)")
    topic = scenario.get("topic", "(any)")
    year_min = int(scenario.get("year_min", 2016))
    n = int(scenario.get("n", 10))
    no_bm25 = bool(scenario.get("no_bm25", False))
    no_rerank = bool(scenario.get("no_rerank", False))

    report = {
        "query": q,
        "filters": {"doc_type": doc_type, "topic": topic, "year_min": year_min,
                    "n": n, "bm25": not no_bm25, "rerank": not no_rerank},
        "ok": False,
    }
    try:
        at = AppTest.from_file(str(APP), default_timeout=timeout)
        at.run()
        if doc_type != "(any)":
            at.selectbox[0].set_value(doc_type)
        if topic != "(any)":
            at.selectbox[1].set_value(topic)
        at.number_input[0].set_value(year_min)
        at.slider[0].set_value(n)
        at.checkbox[0].set_value(not no_bm25)
        at.checkbox[1].set_value(not no_rerank)
        at.text_input[0].set_value(q)
        at.run()

        markdowns = _texts(at.markdown)
        captions = _texts(at.caption)
        snippet_blocks = [m for m in markdowns if "background:#f6f6f4" in m]
        source_caps = [c for c in captions
                       if any(seg in c for seg in ("blog-posts/", "publications/", "testimony/", "reference/"))]
        link_blocks = [m for m in markdowns if ("Live page" in m or "PDF" in m)]

        report.update({
            "ok": True,
            "exceptions": [str(getattr(e, "value", e)) for e in at.exception],
            "rendered_result_count": len(snippet_blocks),
            "sources_in_order": source_caps,
            "distinct_sources": len(source_caps) == len(set(source_caps)),
            "any_highlight_marks": any("<mark>" in m for m in snippet_blocks),
            "result_blocks_with_links": len(link_blocks),
            "info_messages": _texts(at.info),
            "warning_messages": _texts(at.warning),
            "expander_count": len(at.expander),
        })
    except Exception as e:
        report["error"] = f"{type(e).__name__}: {e}"
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--query")
    ap.add_argument("--scenarios", help="path to JSON list of scenario objects")
    ap.add_argument("--doc-type", default="(any)")
    ap.add_argument("--topic", default="(any)")
    ap.add_argument("--year-min", type=int, default=2016)
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--no-bm25", action="store_true")
    ap.add_argument("--no-rerank", action="store_true")
    ap.add_argument("--timeout", type=int, default=180)
    args = ap.parse_args()

    if args.scenarios:
        scenarios = json.loads(Path(args.scenarios).read_text())
        results = [probe(s, args.timeout) for s in scenarios]
        print("PROBE_RESULTS:" + json.dumps(results, ensure_ascii=False))
        bad = any(r.get("exceptions") or r.get("error") for r in results)
        sys.exit(1 if bad else 0)

    if not args.query and args.query != "":
        ap.error("provide --query or --scenarios")
    s = {"query": args.query, "doc_type": args.doc_type, "topic": args.topic,
         "year_min": args.year_min, "n": args.n,
         "no_bm25": args.no_bm25, "no_rerank": args.no_rerank}
    r = probe(s, args.timeout)
    print("PROBE_RESULT:" + json.dumps(r, ensure_ascii=False))
    sys.exit(1 if (r.get("exceptions") or r.get("error")) else 0)


if __name__ == "__main__":
    main()
