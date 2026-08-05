#!/usr/bin/env python3
"""
Dump the Python app's search output for the probe query set, so the static port
can be compared against it (Phase 6 end-to-end parity).

Reproduces search.do_search exactly: public-only hybrid retrieval (dense_k=80,
bm25_k=80, rerank_k=40, pool=180), post-filter, group_sections(30). Emits, per
query, the ranked top-N (source, n_sections) plus the matched position title and
the key-figure sentences.

    python eval/static_parity.py > /tmp/py_parity.json
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import bot               # noqa: E402
import retrieval         # noqa: E402
import sources           # noqa: E402
import positions_index   # noqa: E402

MEMORY = bot.MEMORY_DOC_TYPE
POOL_CAP = 30

PROBE_QUERIES = [
    "conveyance tax", "empty homes tax", "universal school meals",
    "SNAP", "housing affordability", "minimum wage", "HB1800",
    "GET on groceries", "earned income tax credit", "HB 2049",
]


def effective_stance(meta):
    src = meta.get("source")
    return (
        (sources.document_stance(src) if src else None)
        or positions_index.get_index().stance_for_bill(meta.get("bill"))
        or (sources.infer_stance(src) if src else None)
    )


def main():
    with contextlib.redirect_stdout(io.StringIO()):
        collection = bot.index_documents(force=False)
        retrieval._load_bm25(collection)

    out = {}
    for q in PROBE_QUERIES:
        where = {"doc_type": {"$ne": MEMORY}}
        raw = retrieval.hybrid_retrieve(collection, q, POOL_CAP * 6, where,
                                        use_bm25=True, use_rerank=True,
                                        dense_k=80, bm25_k=80, rerank_k=40)
        filtered = [(t, m) for (t, m) in raw if m.get("doc_type") != MEMORY]
        from retrieval import group_sections, stat_sentences
        results = group_sections(filtered, POOL_CAP)
        top = [{"source": r["meta"].get("source"), "n_sections": r["n_sections"]}
               for r in results[:10]]

        # key figures (top 6)
        key_figures = []
        cand, seen = [], set()
        for r in results[:6]:
            for s in stat_sentences(q, r["text"], top_k=2):
                if s not in seen:
                    seen.add(s)
                    cand.append(s)
        if cand:
            scores = retrieval._get_reranker().predict([(q, s) for s in cand])
            key_figures = [s for s, _ in sorted(zip(cand, scores),
                                                key=lambda x: x[1], reverse=True)[:6]]

        pos = positions_index.get_index().match(q)
        out[q] = {
            "top": top,
            "n_results": len(results),
            "position": pos.title if pos else None,
            "key_figures": key_figures,
        }

    json.dump(out, sys.stdout, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
