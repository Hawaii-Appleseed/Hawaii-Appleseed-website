#!/usr/bin/env python3
"""
Build the content-search data bundle from the live corpus + Chroma/BM25 index.

Exports everything the static (GitHub Pages) port needs to reproduce the
Streamlit search app's retrieval BIT-FOR-BIT — minus the in-browser ML, which
runs against `embeddings.bin` (written separately by tools/embed_corpus.mjs).

Design notes (see plan):
  - BM25 stats are pulled straight from the SAME BM25 object the app uses
    (retrieval._load_bm25), so IDF / avgdl / per-chunk term-frequencies are
    computed over the FULL 2594-chunk corpus (incl. relationship-memory) exactly
    as Python does, then we ship only the PUBLIC chunks' tf maps + the IDF table
    restricted to public vocabulary. Bit-identical scores, no memory text leaks.
  - Chunk order is taken FROM the BM25 cache (= Chroma storage order), so
    chunks.json[i] aligns with the exported bm25.docs[i] AND with the embedding
    row embed_corpus.mjs will write for the same text.
  - Stance / title / source-ref are precomputed here (Python regex stack) so the
    JS side never reimplements them.
  - relationship-memory must NEVER appear in any exported artifact; we assert it.

Usage:
    python tools/build_static.py            # writes content-search/data/*
    python tools/build_static.py --verify   # also run sanity checks
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import bot                # noqa: E402
import retrieval          # noqa: E402
import sources            # noqa: E402
import positions_index    # noqa: E402

# ROOT is writing-bot/ (the engine); the static app lives at the site repo's
# top level so GitHub Pages serves it at /content-search/.
OUT = ROOT.parent / "content-search" / "data"
CORPUS_OUT = OUT / "corpus"
MEMORY_DOC_TYPE = bot.MEMORY_DOC_TYPE


def effective_stance(meta: dict) -> str | None:
    """Replicate search.effective_stance: explicit doc stance, else the curated
    positions.md stance for the bill, else a gated first-person inference."""
    src = meta.get("source")
    return (
        (sources.document_stance(src) if src else None)
        or positions_index.get_index().stance_for_bill(meta.get("bill"))
        or (sources.infer_stance(src) if src else None)
    )


def is_public(meta: dict) -> bool:
    if meta.get("doc_type") == MEMORY_DOC_TYPE:
        return False
    src = meta.get("source", "")
    return not src.replace("\\", "/").startswith("relationship-memory/")


def build():
    OUT.mkdir(parents=True, exist_ok=True)

    print("Opening index + BM25 (same objects the app uses)…")
    collection = bot.index_documents(force=False)
    cache = retrieval._load_bm25(collection)   # {bm25, ids, docs, metas, count, ...}
    bm25 = cache["bm25"]
    ids, docs, metas = cache["ids"], cache["docs"], cache["metas"]
    n_total = len(ids)
    print(f"  full corpus: {n_total} chunks")

    # ---- public chunk selection (order preserved = BM25 doc order) ----------
    public_idx = [i for i in range(n_total) if is_public(metas[i] or {})]
    print(f"  public chunks: {len(public_idx)}")

    # Hard guard: nothing from relationship-memory may survive into the bundle.
    for i in public_idx:
        src = (metas[i] or {}).get("source", "")
        assert not src.replace("\\", "/").startswith("relationship-memory/"), src
        assert (metas[i] or {}).get("doc_type") != MEMORY_DOC_TYPE, src

    # ---- chunks.json --------------------------------------------------------
    chunk_records = []
    for i in public_idx:
        m = metas[i] or {}
        rec = {"id": ids[i], "text": docs[i], "source": m.get("source"),
               "doc_type": m.get("doc_type"), "chunk": int(m.get("chunk", 0))}
        for k in ("topic", "year", "bill", "pub_date", "is_sample"):
            if m.get(k) is not None:
                rec[k] = m[k]
        chunk_records.append(rec)
    (OUT / "chunks.json").write_text(json.dumps(chunk_records, ensure_ascii=False))
    print(f"  wrote chunks.json ({len(chunk_records)} records)")

    # ---- bm25.json ----------------------------------------------------------
    # doc_freqs[i] is a dict term->count; doc_len[i] is that chunk's token count.
    # IDF & avgdl come from the full-corpus BM25 (already floored per ATIRE).
    public_docs = [bm25.doc_freqs[i] for i in public_idx]
    public_lens = [int(bm25.doc_len[i]) for i in public_idx]
    public_vocab = set()
    for d in public_docs:
        public_vocab.update(d.keys())
    idf_public = {t: bm25.idf[t] for t in public_vocab if t in bm25.idf}
    bm25_out = {
        "k1": bm25.k1, "b": bm25.b, "epsilon": bm25.epsilon,
        "avgdl": bm25.avgdl, "N": bm25.corpus_size,
        "idf": idf_public,
        "docs": [{"len": public_lens[j], "tf": dict(public_docs[j])}
                 for j in range(len(public_idx))],
    }
    (OUT / "bm25.json").write_text(json.dumps(bm25_out, ensure_ascii=False))
    print(f"  wrote bm25.json (vocab={len(idf_public)}, avgdl={bm25.avgdl:.4f}, "
          f"N={bm25.corpus_size})")

    # ---- docs.json (per source file) ---------------------------------------
    # Stance/title/ref are per-document, so compute once per unique source.
    by_source: dict[str, dict] = {}
    for i in public_idx:
        m = metas[i] or {}
        src = m.get("source")
        if src in by_source:
            continue
        ref = sources.source_ref(src)
        by_source[src] = {
            "source": src,
            "title": sources.source_title(src),
            "stance": effective_stance(m),
            "doc_type": m.get("doc_type"),
            "ref": {"url": ref.get("url"), "pdf": ref.get("pdf"),
                    "kind": ref.get("kind")},
        }
        for k in ("topic", "year", "bill", "pub_date"):
            if m.get(k) is not None:
                by_source[src][k] = m[k]
    (OUT / "docs.json").write_text(
        json.dumps(by_source, ensure_ascii=False))
    print(f"  wrote docs.json ({len(by_source)} documents)")

    # ---- positions.json -----------------------------------------------------
    idx = positions_index.get_index()
    pos_out = []
    for e in idx.entries:
        pos_out.append({
            "title": e.title,
            "section": e.section,
            "position": e.position,
            "core_argument": e.core_argument,
            "standard_ask": e.standard_ask,
            "bills": e.bills,           # [{"bill","stance"}]
            "match_text": e.match_text(),
        })
    (OUT / "positions.json").write_text(json.dumps(pos_out, ensure_ascii=False))
    print(f"  wrote positions.json ({len(pos_out)} entries)")

    # ---- topics.json (testimony subdirs) ------------------------------------
    tdir = ROOT / "testimony"
    topics = sorted(p.name for p in tdir.iterdir() if p.is_dir()) if tdir.exists() else []
    (OUT / "topics.json").write_text(json.dumps(topics, ensure_ascii=False))
    print(f"  wrote topics.json ({len(topics)} topics)")

    # ---- corpus/<rel> full texts (for the modal) ----------------------------
    if CORPUS_OUT.exists():
        shutil.rmtree(CORPUS_OUT)
    n_files = 0
    for src in by_source:
        assert not src.replace("\\", "/").startswith("relationship-memory/")
        text = sources.read_source(src)
        dest = CORPUS_OUT / src
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")
        n_files += 1
    print(f"  wrote corpus/ ({n_files} source files)")

    # ---- tokenizer_fixture.json (test-only) ---------------------------------
    samples = [
        "HB1779", "HB 1779", "House Bill 1800", "house-bill-1800",
        "SB3125 CD1", "conveyance tax marginal rates", "GET on groceries",
        "TAT and the EITC", "universal school meals HB1779",
        "empty homes tax", "ADA compliance", "LIHTC and TOD",
        "the SNAP benefits", "We support HB2049 (2026)", "ʻohana housing",
        "Honolulu's $880 million", "minimum wage 2026", "PFML paid leave",
        "Senate Resolution 12", "hb 2049 conveyance",
    ]
    fixture = {
        "tokenize": {s: retrieval._tokenize(s) for s in samples},
        "expand_query": {s: retrieval._expand_query(s) for s in samples},
        "is_pure_bill": {s: retrieval._is_pure_bill_query(s) for s in samples},
        "bill_tokens": {s: sorted(retrieval._bill_tokens(s)) for s in samples},
    }
    (OUT / "tokenizer_fixture.json").write_text(
        json.dumps(fixture, ensure_ascii=False, indent=2))
    print(f"  wrote tokenizer_fixture.json ({len(samples)} samples)")

    # ---- api.json (public polling manifest) ---------------------------------
    # Small, stable endpoint other projects poll to detect a new bundle and
    # discover the data files. embeddings entry is patched in afterward by
    # embed_corpus.mjs (which runs after this script and rewrites the sha).
    import hashlib
    from datetime import datetime, timezone

    def _sha(p):
        return hashlib.sha256(p.read_bytes()).hexdigest()

    api = {
        "name": "hawaii-appleseed-content-search",
        "version": 1,
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "counts": {"documents": len(by_source), "chunks": len(chunk_records),
                   "positions": len(pos_out), "topics": len(topics)},
        "files": {
            name: {"path": f"data/{name}", "sha256": _sha(OUT / name)}
            for name in ("docs.json", "chunks.json", "bm25.json",
                          "positions.json", "topics.json")
        },
        "app": "index.html",
    }
    (OUT.parent / "api.json").write_text(json.dumps(api, indent=2))
    print("  wrote api.json (polling manifest)")

    print("Done.")
    return {"n_public": len(public_idx), "n_total": n_total,
            "n_docs": len(by_source)}


def verify():
    import math
    print("\nVerifying…")
    chunks = json.loads((OUT / "chunks.json").read_text())
    bm = json.loads((OUT / "bm25.json").read_text())
    assert len(chunks) == len(bm["docs"]), "chunks/bm25 length mismatch"

    # No relationship-memory anywhere.
    for c in chunks:
        s = (c["source"] or "").replace("\\", "/")
        assert not s.startswith("relationship-memory/"), s
        assert c["doc_type"] != MEMORY_DOC_TYPE, s
    assert not (CORPUS_OUT / "relationship-memory").exists()
    print("  ✓ no relationship-memory in bundle")

    # BM25 scores reproduce Python for a probe query, using exported stats only.
    collection = bot.index_documents(force=False)
    cache = retrieval._load_bm25(collection)
    py_bm25 = cache["bm25"]
    # Map exported docs back by chunk id to a public-index lookup.
    public_idx = [i for i in range(len(cache["ids"]))
                  if cache["metas"][i] and cache["metas"][i].get("doc_type") != MEMORY_DOC_TYPE
                  and not (cache["metas"][i].get("source", "")
                           ).replace("\\", "/").startswith("relationship-memory/")]
    for q in ["conveyance tax", "universal school meals", "HB1800"]:
        toks = retrieval._tokenize(q)
        py_scores = py_bm25.get_scores(toks)
        # Recompute with exported stats (the JS formula).
        for local_j, i in enumerate(public_idx[:50]):
            d = bm["docs"][local_j]
            s = 0.0
            for t in toks:
                tf = d["tf"].get(t, 0)
                if tf == 0:
                    continue
                idf = bm["idf"].get(t, 0.0)
                s += idf * (tf * (bm["k1"] + 1) /
                            (tf + bm["k1"] * (1 - bm["b"] + bm["b"] * d["len"] / bm["avgdl"])))
            assert abs(s - py_scores[i]) < 1e-9, (q, local_j, s, py_scores[i])
    print("  ✓ BM25 scores bit-match Python (probe queries, first 50 public docs)")

    docs = json.loads((OUT / "docs.json").read_text())
    n_stance = sum(1 for d in docs.values() if d["stance"])
    print(f"  ✓ docs.json: {len(docs)} docs, {n_stance} with a stance")
    print("Verify OK.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args()
    build()
    if args.verify:
        verify()
