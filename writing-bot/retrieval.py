"""
Hybrid retrieval for the Hawaiʻi Appleseed bot.

Combines:
  - Dense retrieval via ChromaDB (top-`dense_k`)
  - BM25 keyword retrieval via rank_bm25 (top-`bm25_k`)
  - Reciprocal Rank Fusion (RRF) over both ranked lists
  - Cross-encoder rerank over the fused candidates (top-`n`)
  - Optional linear recency boost on the rerank score

Public API:
    hybrid_retrieve(collection, query, n, where, *, dense_k=30, bm25_k=30,
                    use_bm25=True, use_rerank=True, recency_weight=0.05) -> list[(text, meta)]

The BM25 index over the chunked corpus is cached at `.chroma/bm25.pkl`,
keyed by collection size; it rebuilds automatically when the index changes.
The cross-encoder model loads lazily and is held in a module-level cache.
"""

from __future__ import annotations

import os
import pickle
import re
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).parent
BM25_CACHE = ROOT / ".chroma" / "bm25.pkl"
RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

_rerank_model = None
_bm25_cache: dict | None = None


def _enable_offline_if_cached() -> None:
    """If the rerank model is already in the local HF cache, force offline mode
    so loading skips the HF Hub revision check (~6s of the ~12s cold start ->
    ~0.6s). MUST run before transformers/huggingface_hub are imported, which read
    these env vars at import time. A fresh machine (model not cached) is left
    online so it can download on first run."""
    if os.environ.get("HF_HUB_OFFLINE") is not None:
        return  # respect an explicit external setting
    hf_home = os.environ.get("HF_HOME") or os.path.join(os.path.expanduser("~"), ".cache", "huggingface")
    cached = os.path.join(hf_home, "hub", "models--" + RERANK_MODEL.replace("/", "--"))
    if os.path.isdir(cached):
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"


_enable_offline_if_cached()


# ---------------------------------------------------------------------------
# Tokenization (cheap, shared by indexing and querying)
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")

# Bill-form normalization. The corpus mixes three conventions for the same bill:
# "HB1779" (compact, common in queries), "HB 1779" (spaced, common in testimony),
# and "House Bill 1779" / "house-bill-1779" (long form, used in titles and
# filenames like blog-posts/2026/highlights-from-house-bill-1800.txt). Without
# normalization, a query "HB1800" never matches a filename "house-bill-1800",
# so `_apply_bill_boost` can't pull the canonical doc to the top.
_BILL_SPACE_RE = re.compile(r"\b([HShs][BRbr])\s+(\d)")
_BILL_LONG_RE = re.compile(r"\b(House|Senate)[\s\-]+(Bill|Resolution)[\s\-]+(\d+)", re.IGNORECASE)


def _normalize_bills(text: str) -> str:
    def _long_sub(m: re.Match) -> str:
        chamber = "H" if m.group(1).lower() == "house" else "S"
        kind = "B" if m.group(2).lower() == "bill" else "R"
        return f"{chamber}{kind}{m.group(3)}"
    text = _BILL_LONG_RE.sub(_long_sub, text)
    text = _BILL_SPACE_RE.sub(r"\1\2", text)
    return text


# Bump when _tokenize logic changes — invalidates the on-disk BM25 cache so it
# rebuilds with the new tokenization instead of silently reusing stale tokens.
TOKENIZER_VERSION = 3

# A tiny stoplist — full English stopwords aren't needed; BM25 IDF down-weights
# common words automatically. We just strip a handful that produce noise in
# bill-heavy queries.
_STOP = frozenset("the a an of and or to in on for with by is are was were be been from this that these those it as at our we their".split())


def _tokenize(text: str) -> list[str]:
    text = _normalize_bills(text)
    return [t.lower() for t in _TOKEN_RE.findall(text) if t.lower() not in _STOP]


# Query-side acronym expansion. Corpus tends to spell things out; queries from
# staff often use the acronym. We append the expansion to the query so both
# BM25 and the dense embedder see the canonical phrase. Cheap and additive —
# the original tokens remain, so this never hurts a query that already uses
# the long form.
ALIASES: dict[str, list[str]] = {
    "get": ["general excise tax"],
    "tat": ["transient accommodations tax"],
    "ctc": ["child tax credit"],
    "eitc": ["earned income tax credit"],
    "snap": ["food stamps", "nutrition assistance"],
    "tanf": ["temporary assistance for needy families"],
    "ada": ["americans with disabilities act"],
    "lih": ["low income housing"],
    "lihtc": ["low income housing tax credit"],
    "tod": ["transit oriented development"],
    "pfml": ["paid family medical leave"],
}

_ALIAS_TOKEN_RE = re.compile(r"\b([A-Za-z]{2,6})\b")


def _expand_query(query: str) -> str:
    """Append canonical expansions for acronyms found in `query`. Idempotent
    when the expansion is already present (BM25/dense don't double-count it
    meaningfully, but we still skip to keep queries tidy)."""
    extras: list[str] = []
    seen: set[str] = set()
    lower_q = query.lower()
    for m in _ALIAS_TOKEN_RE.finditer(query):
        key = m.group(1).lower()
        for expansion in ALIASES.get(key, []):
            if expansion in seen or expansion in lower_q:
                continue
            seen.add(expansion)
            extras.append(expansion)
    return f"{query} {' '.join(extras)}" if extras else query


# ---------------------------------------------------------------------------
# BM25 index — built lazily from the collection's chunks
# ---------------------------------------------------------------------------

def _load_bm25(collection):
    """Return a dict with bm25, ids, metas, docs. Rebuild if collection has changed."""
    global _bm25_cache
    expected_count = collection.count()

    if (_bm25_cache is not None and _bm25_cache["count"] == expected_count
            and _bm25_cache.get("tok_version") == TOKENIZER_VERSION):
        return _bm25_cache

    if BM25_CACHE.exists():
        try:
            with open(BM25_CACHE, "rb") as f:
                cached = pickle.load(f)
            if cached.get("count") == expected_count and cached.get("tok_version") == TOKENIZER_VERSION:
                _bm25_cache = cached
                return cached
        except Exception:
            pass  # rebuild

    from rank_bm25 import BM25Okapi

    # Pull every chunk out of Chroma. Cheap at this scale (~2K chunks).
    page = collection.get(include=["documents", "metadatas"])
    ids = page["ids"]
    docs = page["documents"]
    metas = page["metadatas"]
    tokenized = [_tokenize(d) for d in docs]
    bm25 = BM25Okapi(tokenized)

    cache = {"bm25": bm25, "ids": ids, "docs": docs, "metas": metas,
             "count": expected_count, "tok_version": TOKENIZER_VERSION}
    BM25_CACHE.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(BM25_CACHE, "wb") as f:
            pickle.dump(cache, f)
    except Exception:
        pass
    _bm25_cache = cache
    return cache


def _bm25_search(collection, query: str, k: int, where: dict | None) -> list[tuple[str, str, dict]]:
    cache = _load_bm25(collection)
    scores = cache["bm25"].get_scores(_tokenize(query))
    # Argsort descending, then filter by `where`.
    order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    out = []
    for i in order:
        if scores[i] <= 0:
            break
        meta = cache["metas"][i] or {}
        if not _matches_where(meta, where):
            continue
        out.append((cache["ids"][i], cache["docs"][i], meta))
        if len(out) >= k:
            break
    return out


def _matches_where(meta: dict, where: dict | None) -> bool:
    """Minimal Chroma-style filter evaluator: supports {"k":"v"}, {"k":{"$gte":N}},
    {"k":{"$ne":v}}, {"k":{"$in":[...]}}, and {"$and":[...]}."""
    if not where:
        return True
    if "$and" in where:
        return all(_matches_where(meta, sub) for sub in where["$and"])
    for k, v in where.items():
        if isinstance(v, dict):
            for op, operand in v.items():
                if op == "$gte" and not (meta.get(k) is not None and meta[k] >= operand):
                    return False
                elif op == "$lte" and not (meta.get(k) is not None and meta[k] <= operand):
                    return False
                elif op == "$eq" and meta.get(k) != operand:
                    return False
                elif op == "$ne" and meta.get(k) == operand:
                    return False
                elif op == "$in" and meta.get(k) not in operand:
                    return False
        else:
            if meta.get(k) != v:
                return False
    return True


# ---------------------------------------------------------------------------
# Dense retrieval (delegates to Chroma)
# ---------------------------------------------------------------------------

def _dense_search(collection, query: str, k: int, where: dict | None) -> list[tuple[str, str, dict]]:
    kwargs = {"query_texts": [query], "n_results": k}
    if where:
        kwargs["where"] = where
    res = collection.query(**kwargs)
    ids = res["ids"][0] if res["ids"] else []
    docs = res["documents"][0] if res["documents"] else []
    metas = res["metadatas"][0] if res["metadatas"] else []
    return list(zip(ids, docs, metas))


# ---------------------------------------------------------------------------
# Reciprocal Rank Fusion
# ---------------------------------------------------------------------------

def _rrf(rankings: Iterable[list[tuple[str, str, dict]]], k: int = 60) -> list[tuple[str, str, dict, float]]:
    """Merge ranked lists by RRF score = Σ 1 / (k + rank). Returns deduped by id, sorted by score desc."""
    score: dict[str, float] = {}
    payload: dict[str, tuple[str, str, dict]] = {}
    for ranked in rankings:
        for rank, (cid, doc, meta) in enumerate(ranked):
            score[cid] = score.get(cid, 0.0) + 1.0 / (k + rank + 1)
            if cid not in payload:
                payload[cid] = (cid, doc, meta)
    fused = sorted(payload.values(), key=lambda r: score[r[0]], reverse=True)
    return [(cid, doc, meta, score[cid]) for (cid, doc, meta) in fused]


# ---------------------------------------------------------------------------
# Cross-encoder rerank
# ---------------------------------------------------------------------------

def _get_reranker():
    """Load the cross-encoder once. Offline mode (set at module import by
    _enable_offline_if_cached) makes this ~0.6s instead of ~6s by skipping the
    HF Hub revision check."""
    global _rerank_model
    if _rerank_model is None:
        # Import the submodule directly — `from sentence_transformers import …`
        # runs the package __init__ which eagerly pulls in SentenceTransformer
        # and a pile of model classes we never use (~1.4s of dead weight).
        from sentence_transformers.cross_encoder import CrossEncoder
        _rerank_model = CrossEncoder(RERANK_MODEL)
    return _rerank_model


_BILL_TOKEN_RE = re.compile(r"^[hs][br]\d{2,5}$")


def _bill_tokens(query: str) -> set[str]:
    """Normalized bill tokens in the query, e.g. 'HB1779'/'HB 1779' → {'hb1779'}."""
    return {t for t in _tokenize(query) if _BILL_TOKEN_RE.match(t)}


def _is_pure_bill_query(query: str) -> bool:
    """True when the query reduces to bill references only (modulo stopwords).
    On these, cross-encoder rerank is waste motion: _apply_bill_boost overrides
    the rerank order anyway by floating filename-matching docs to the top, so
    paying ~1.5s to score 40 candidates against "HB1800" buys nothing."""
    bills = _bill_tokens(query)
    return bool(bills) and set(_tokenize(query)) == bills


def _apply_bill_boost(query: str, candidates: list[tuple[str, str, dict, float]]) -> list[tuple[str, str, dict, float]]:
    """When the query names a bill, float docs about that bill to the top. Bill
    lookup is exact-match by nature; the semantic reranker must not bury an exact
    hit. Ordering: docs whose *filename* carries the bill (the canonical docs for
    it) first, then docs that merely *mention* it, then the rest — relative order
    preserved within each group.
    """
    bills = _bill_tokens(query)
    if not bills:
        return candidates
    fname_match, text_match, rest = [], [], []
    for c in candidates:
        if bills & set(_tokenize(c[2].get("source", ""))):
            fname_match.append(c)
        elif bills & set(_tokenize(c[1])):
            text_match.append(c)
        else:
            rest.append(c)
    return fname_match + text_match + rest


def _rerank(query: str, candidates: list[tuple[str, str, dict, float]], *, recency_weight: float) -> list[tuple[str, str, dict, float]]:
    if not candidates:
        return []
    model = _get_reranker()
    pairs = [(query, doc) for (_cid, doc, _m, _s) in candidates]
    scores = model.predict(pairs)
    boosted = []
    for (cid, doc, meta, _rrf_s), s in zip(candidates, scores):
        year = meta.get("year")
        bump = recency_weight * max(0, (year - 2022)) if isinstance(year, int) else 0.0
        boosted.append((cid, doc, meta, float(s) + bump))
    boosted.sort(key=lambda r: r[3], reverse=True)
    return boosted


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def hybrid_retrieve(
    collection,
    query: str,
    n: int,
    where: dict | None,
    *,
    dense_k: int = 30,
    bm25_k: int = 30,
    use_bm25: bool = True,
    use_rerank: bool = True,
    recency_weight: float = 0.05,
    rerank_k: int | None = None,
) -> list[tuple[str, dict]]:
    """Return up to `n` (text, metadata) pairs.

    `rerank_k` caps how many top RRF-fused candidates the cross-encoder scores
    (the rest keep their RRF order). The cross-encoder is the slow step, so for a
    large `n` (paginated pools) capping it cuts seconds without changing the top
    results — they come from the head anyway. None = rerank everything.

    Falls back to no-filter when the filtered retrieval yields zero — matches
    bot.retrieve's prior behavior.
    """
    expanded = _expand_query(query)
    dense = _dense_search(collection, expanded, dense_k, where)
    rankings = [dense]
    if use_bm25:
        try:
            rankings.append(_bm25_search(collection, expanded, bm25_k, where))
        except Exception as e:
            # BM25 should never silently break retrieval — fall through to dense only.
            print(f"  (BM25 disabled this query: {e})")

    fused = _rrf(rankings)
    if not fused and where:
        # Filter was too narrow — retry with no filter.
        return hybrid_retrieve(
            collection, query, n, None,
            dense_k=dense_k, bm25_k=bm25_k,
            use_bm25=use_bm25, use_rerank=use_rerank,
            recency_weight=recency_weight, rerank_k=rerank_k,
        )

    if use_rerank and not _is_pure_bill_query(query):
        # Rerank against the ORIGINAL query — the cross-encoder is a relevance
        # judge for the user's intent, not for our expanded synonym salad. Only
        # the top `rerank_k` are scored; the tail stays in RRF order.
        if rerank_k is not None and len(fused) > rerank_k:
            fused = _rerank(query, fused[:rerank_k], recency_weight=recency_weight) + fused[rerank_k:]
        else:
            fused = _rerank(query, fused, recency_weight=recency_weight)

    # Exact bill-number matches win regardless of semantic score.
    fused = _apply_bill_boost(query, fused)

    return [(doc, meta) for (_cid, doc, meta, _s) in fused[:n]]


# Split on sentence-ending punctuation (+ trailing quotes/brackets/space) OR a
# blank-line paragraph break. NOT on bare single newlines: PDF-extracted
# publications wrap mid-sentence with hard newlines, and splitting there yields
# truncated fragments ("…recommends a flat tax of") instead of whole sentences.
_SENT_DELIM_RE = re.compile(r"([.!?]+['\")\]]*\s+|\n\s*\n+)")


def split_sentences(text: str) -> list[tuple[str, str]]:
    """Split into (body, trailing_delimiter) pairs such that ''.join(b+d) == text.
    Cheap and good enough for highlighting (not linguistically perfect)."""
    parts = _SENT_DELIM_RE.split(text)
    pairs = []
    for i in range(0, len(parts), 2):
        body = parts[i]
        delim = parts[i + 1] if i + 1 < len(parts) else ""
        if body or delim:
            pairs.append((body, delim))
    return pairs


def top_sentences(query: str, text: str, *, top_k: int = 2, min_len: int = 40,
                  max_candidates: int = 400) -> list[str]:
    """Return the stripped bodies of the `top_k` sentences in `text` most relevant
    to `query`, scored by the cross-encoder. Used to highlight the passage that
    actually answers the query — not just literal term matches. Sentences shorter
    than `min_len` chars are skipped (headers, fragments); scoring is capped at
    `max_candidates` sentences to bound cost on long documents."""
    cand = [b.strip() for b, _ in split_sentences(text) if len(b.strip()) >= min_len]
    cand = cand[:max_candidates]
    if not cand:
        return []
    model = _get_reranker()
    scores = model.predict([(query, b) for b in cand])
    ranked = sorted(zip(cand, scores), key=lambda x: x[1], reverse=True)
    return [b for b, _ in ranked[:top_k]]


_FIGURE_RE = re.compile(
    r"\d+(?:\.\d+)?\s?%"            # 12% / 5.4 %
    r"|\$\s?\d[\d,]*"               # $880 / $17B-ish ($ + digits)
    r"|\b\d{1,3}(?:,\d{3})+\b"      # 160,000
    r"|\b\d+(?:\.\d+)?\s?(?:million|billion|percent|x)\b"  # 71 million / 2x
    r"|\b\d{3,}\b",                 # 6000, 2030
    re.IGNORECASE,
)


def stat_sentences(query: str, text: str, *, top_k: int = 3, min_len: int = 30,
                   max_candidates: int = 400) -> list[str]:
    """Like top_sentences, but restricted to sentences that carry a figure
    (percent, dollar amount, large/grouped number). For surfacing the concrete
    statistics most relevant to the query."""
    cand = [b.strip() for b, _ in split_sentences(text)
            if len(b.strip()) >= min_len and _FIGURE_RE.search(b)]
    cand = cand[:max_candidates]
    if not cand:
        return []
    model = _get_reranker()
    scores = model.predict([(query, b) for b in cand])
    ranked = sorted(zip(cand, scores), key=lambda x: x[1], reverse=True)
    return [b for b, _ in ranked[:top_k]]


def group_sections(hits: list[tuple[str, dict]], limit: int) -> list[dict]:
    """Collapse a rank-ordered list of (text, meta) chunks into one entry per
    source document, surfacing how many distinct relevant *sections* each has.

    `hits` is already filtered and ordered best-first. Chunks of the same source
    are grouped; runs of adjacent `chunk` indices (i, i+1, …) merge into a single
    section, since the 1500-char/150-overlap windows are mechanical and a passage
    can straddle a boundary. Each section is represented by its best-ranked chunk.

    Returns up to `limit` dicts (source order preserved = best-rank first):
        {text, meta, n_sections, extra_sections: [{chunk, text}, ...]}
    where `text`/`meta` are the document's top-ranked chunk and `extra_sections`
    are the remaining sections in best-rank order.
    """
    from collections import OrderedDict

    groups: "OrderedDict[str, list]" = OrderedDict()
    for rank, (text, meta) in enumerate(hits):
        src = meta.get("source", "?")
        groups.setdefault(src, []).append((rank, int(meta.get("chunk", 0)), text, meta))

    out: list[dict] = []
    for items in groups.values():
        by_idx = sorted(items, key=lambda x: x[1])
        runs = [[by_idx[0]]]
        for it in by_idx[1:]:
            if it[1] == runs[-1][-1][1] + 1:
                runs[-1].append(it)
            else:
                runs.append([it])
        sections = []
        for run in runs:
            best = min(run, key=lambda x: x[0])  # best (lowest) rank in the run
            sections.append({"rank": best[0], "chunk": best[1], "text": best[2], "meta": best[3]})
        sections.sort(key=lambda s: s["rank"])
        primary = sections[0]
        out.append({
            "text": primary["text"],
            "meta": primary["meta"],
            "n_sections": len(sections),
            "extra_sections": [{"chunk": s["chunk"], "text": s["text"]} for s in sections[1:]],
        })
    return out[:limit]


def invalidate_bm25_cache():
    """Drop the in-process BM25 cache and the on-disk pickle. Call after reindex."""
    global _bm25_cache
    _bm25_cache = None
    try:
        BM25_CACHE.unlink()
    except FileNotFoundError:
        pass
