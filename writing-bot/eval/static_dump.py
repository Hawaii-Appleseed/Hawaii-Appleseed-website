#!/usr/bin/env python3
"""
Dump model-free ground truth for the static port's Node unit tests.

Covers the deterministic, embedding-independent stages so they can be asserted
bit-for-bit in JS without loading any ML model:
  - BM25 public search (top-k chunk ids per probe query)
  - group_sections (given a fixed id-ordered hit list -> grouped output)

The tokenizer fixture is already emitted by build_static.py. Embedding/rerank
parity is checked separately (with models, tolerance-based) in Phase 6.

    python eval/static_dump.py > content-search/test/fixtures.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import contextlib       # noqa: E402
import io                # noqa: E402

import bot               # noqa: E402
import retrieval         # noqa: E402

PROBE_QUERIES = [
    "conveyance tax", "empty homes tax", "universal school meals",
    "SNAP", "housing affordability", "minimum wage", "HB1800",
    "GET on groceries", "earned income tax credit", "HB 2049",
]
MEMORY = bot.MEMORY_DOC_TYPE


def main():
    # bot.index_documents prints to stdout — keep stdout clean for the JSON dump.
    with contextlib.redirect_stdout(io.StringIO()):
        collection = bot.index_documents(force=False)
        cache = retrieval._load_bm25(collection)

    # --- BM25 public search: ordered chunk ids per query --------------------
    bm25_cases = {}
    for q in PROBE_QUERIES:
        where = {"doc_type": {"$ne": MEMORY}}
        hits = retrieval._bm25_search(collection, q, 100, where)
        bm25_cases[q] = [cid for (cid, _doc, _meta) in hits]

    # --- group_sections: a fixed id-ordered hit list -> grouped output ------
    # Build the input from a dense+bm25 (no rerank) retrieval so the list is
    # realistic; JS will reconstruct the SAME list by id and group it, so the
    # grouping comparison is model-free regardless of how the list was made.
    group_cases = []
    from retrieval import group_sections
    page = collection.get(include=["documents", "metadatas"])
    id_by_text_meta = {}  # (source, chunk) -> id
    for cid, meta in zip(page["ids"], page["metadatas"]):
        m = meta or {}
        id_by_text_meta[(m.get("source"), int(m.get("chunk", 0)))] = cid

    for q in ["conveyance tax", "universal school meals", "HB1800"]:
        where = {"doc_type": {"$ne": MEMORY}}
        raw = retrieval.hybrid_retrieve(collection, q, 180, where,
                                        use_bm25=True, use_rerank=False,
                                        dense_k=80, bm25_k=80)
        # ordered chunk ids of the input
        input_ids = [id_by_text_meta[(m.get("source"), int(m.get("chunk", 0)))]
                     for (_t, m) in raw]
        grouped = group_sections(raw, 30)
        expected = [{
            "source": g["meta"].get("source"),
            "n_sections": g["n_sections"],
            "primary_chunk": int(g["meta"].get("chunk", 0)),
            "extra_chunks": [s["chunk"] for s in g["extra_sections"]],
        } for g in grouped]
        group_cases.append({"query": q, "input_ids": input_ids, "expected": expected})

    json.dump({"bm25": bm25_cases, "group_sections": group_cases},
              sys.stdout, ensure_ascii=False)


if __name__ == "__main__":
    main()
