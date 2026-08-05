"""
Phase 1 probe: dump ground-truth data for the multi-section indicator so test
agents can verify `retrieval.group_sections` without each loading torch.

For each query it records, per source: the raw retrieved chunk indices (in rank
order) BEFORE grouping, and the grouped output (n_sections, primary chunk, extra
section chunks). An agent can recompute the expected grouping from the raw chunk
indices and compare.

    .venv/bin/python eval/section_probe.py > /tmp/phase1_probe.json
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import bot  # noqa: E402
from retrieval import group_sections  # noqa: E402

QUERIES = [
    "conveyance tax", "empty homes tax", "universal school meals",
    "SNAP", "housing affordability", "minimum wage", "HB1800",
]
N_RESULTS = 10


def main():
    coll = bot.index_documents(force=False)
    out = {}
    for q in QUERIES:
        raw = bot.retrieve(coll, q, N_RESULTS * 6, None, use_bm25=True, use_rerank=True)
        # raw chunk indices per source, in rank order
        raw_by_source = {}
        for rank, (_text, meta) in enumerate(raw):
            src = meta.get("source", "?")
            raw_by_source.setdefault(src, []).append(
                {"rank": rank, "chunk": int(meta.get("chunk", 0))}
            )
        grouped = group_sections(raw, N_RESULTS)
        results = [
            {
                "source": r["meta"].get("source", "?"),
                "primary_chunk": int(r["meta"].get("chunk", 0)),
                "n_sections": r["n_sections"],
                "extra_chunks": [e["chunk"] for e in r["extra_sections"]],
            }
            for r in grouped
        ]
        out[q] = {"results": results, "raw_by_source": raw_by_source}
    json.dump(out, sys.stdout, indent=1)


if __name__ == "__main__":
    main()
