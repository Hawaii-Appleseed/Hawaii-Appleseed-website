"""
Phase 2 probe: dump the semantic-highlight selections so test agents can judge
relevance quality and verify integrity without each loading torch.

For each query, for each result document, records the chunk text and the
top sentences the cross-encoder chose to highlight. Also flags whether each
chosen sentence is an exact substring of the text (integrity) and the sentence
roundtrip (split_sentences reconstructs the text exactly).

    .venv/bin/python eval/sentence_probe.py > /tmp/phase2_probe.json
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import bot  # noqa: E402
from retrieval import group_sections, top_sentences, split_sentences  # noqa: E402

QUERIES = [
    "marginal conveyance tax rates that exempt local homeowners",
    "universal free school meals for keiki",
    "empty homes tax to address vacant units in Honolulu",
    "federal cuts to SNAP nutrition assistance",
    "just cause eviction protections for tenants",
    "paid family and medical leave for workers",
]
N_RESULTS = 6


def main():
    coll = bot.index_documents(force=False)
    out = {}
    for q in QUERIES:
        raw = bot.retrieve(coll, q, N_RESULTS * 6, None, use_bm25=True, use_rerank=True)
        results = group_sections(raw, N_RESULTS)
        rows = []
        for r in results:
            text = r["text"]
            tops = top_sentences(q, text, top_k=2)
            roundtrip_ok = "".join(b + d for b, d in split_sentences(text)) == text
            rows.append({
                "source": r["meta"].get("source", "?"),
                "text": text,
                "highlighted_sentences": tops,
                "all_substrings": all(s in text for s in tops),
                "roundtrip_ok": roundtrip_ok,
            })
        out[q] = rows
    json.dump(out, sys.stdout, indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
