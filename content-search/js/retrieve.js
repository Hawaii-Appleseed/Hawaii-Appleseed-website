// Hybrid retrieval orchestrator — JS port of retrieval.hybrid_retrieve +
// bot.retrieve's public-only filtering, plus search.do_search's pre/post filter
// split. Dense embedding and cross-encoder scoring are delegated to async
// callbacks (the worker); everything else (RRF, bill boost, recency, ordering)
// runs here deterministically and matches Python.

import { tokenize, expandQuery, billTokens, isPureBillQuery } from "./tokenize.js";

const RRF_K = 60;
const BILL_TOKEN_RE = /^[hs][br]\d{2,5}$/;

// ---- dense search: cosine over the in-memory embedding matrix --------------
// Embeddings are L2-normalized at build time, so cosine == dot product, and
// ranking by dot product == Chroma's L2 ranking on normalized vectors.
export function denseSearch(queryVec, store, k, matchesWhere) {
  const { embeddings, dim, n } = store;
  const scores = new Float64Array(n);
  for (let i = 0; i < n; i++) {
    let s = 0;
    const off = i * dim;
    for (let d = 0; d < dim; d++) s += queryVec[d] * embeddings[off + d];
    scores[i] = s;
  }
  const order = Array.from({ length: n }, (_, i) => i);
  order.sort((a, c) => scores[c] - scores[a]);
  const out = [];
  for (const i of order) {
    if (!matchesWhere(i)) continue;
    out.push(i);
    if (out.length >= k) break;
  }
  return out;
}

// Reciprocal Rank Fusion over ranked lists of chunk indices. Returns indices
// ordered by fused score desc, deduped, stable for ties (insertion order of
// first appearance — matching Python's payload.values() iteration order).
function rrf(rankings) {
  const score = new Map();
  const firstSeen = [];
  const seen = new Set();
  for (const ranked of rankings) {
    ranked.forEach((id, rank) => {
      score.set(id, (score.get(id) || 0) + 1.0 / (RRF_K + rank + 1));
      if (!seen.has(id)) {
        seen.add(id);
        firstSeen.push(id);
      }
    });
  }
  // Stable sort first-seen-ordered ids by fused score desc (ties keep first-seen
  // order, matching Python's payload.values() iteration).
  return firstSeen.slice().sort((a, b) => score.get(b) - score.get(a));
}

// _apply_bill_boost: when the query names a bill, float docs about it to the
// top — filename matches first, then text mentions, then the rest. Stable
// within each group.
function applyBillBoost(query, ids, store) {
  const bills = billTokens(query);
  if (bills.size === 0) return ids;
  const fname = [], text = [], rest = [];
  for (const id of ids) {
    const chunk = store.chunks[id];
    const srcTokens = new Set(tokenize(chunk.source || ""));
    let inFname = false;
    for (const b of bills) if (srcTokens.has(b)) { inFname = true; break; }
    if (inFname) { fname.push(id); continue; }
    const docTokens = new Set(tokenize(chunk.text));
    let inText = false;
    for (const b of bills) if (docTokens.has(b)) { inText = true; break; }
    if (inText) text.push(id); else rest.push(id);
  }
  return [...fname, ...text, ...rest];
}

// Main entry. opts:
//   query, store, whereMatches(idx)->bool, n,
//   useBm25, useRerank, denseK, bm25K, rerankK, recencyWeight,
//   embed(text)->Promise<Float32Array>, rerank(pairs)->Promise<number[]>
// Returns ordered array of chunk indices (length ≤ n).
export async function hybridRetrieve(opts) {
  const {
    query, store, whereMatches, n,
    useBm25 = true, useRerank = true,
    denseK = 80, bm25K = 80, rerankK = 40, recencyWeight = 0.05,
    embed, rerank,
  } = opts;

  const expanded = expandQuery(query);
  const queryVec = await embed(expanded);
  const denseIds = denseSearch(queryVec, store, denseK, whereMatches);

  const rankings = [denseIds];
  if (useBm25) {
    const bm25Ids = store.bm25.search(tokenize(expanded), bm25K, whereMatches);
    rankings.push(bm25Ids);
  }

  let fused = rrf(rankings);

  if (fused.length === 0 && opts._hasWhere) {
    // Filter too narrow — retry with no filter (matches hybrid_retrieve).
    return hybridRetrieve({ ...opts, whereMatches: () => true, _hasWhere: false });
  }

  // Cross-encoder rerank against the ORIGINAL query (not the expanded one),
  // only the top rerankK; the tail keeps RRF order. Skipped for pure-bill
  // queries (bill boost overrides order anyway).
  if (useRerank && !isPureBillQuery(query)) {
    const head = rerankK !== null && fused.length > rerankK ? fused.slice(0, rerankK) : fused;
    const tail = rerankK !== null && fused.length > rerankK ? fused.slice(rerankK) : [];
    const pairs = head.map((id) => [query, store.chunks[id].text]);
    const scores = await rerank(pairs);
    const boosted = head.map((id, j) => {
      const year = store.chunks[id].year;
      const bump = Number.isInteger(year) ? recencyWeight * Math.max(0, year - 2022) : 0;
      return { id, score: scores[j] + bump };
    });
    boosted.sort((a, b) => b.score - a.score);
    fused = [...boosted.map((x) => x.id), ...tail];
  }

  fused = applyBillBoost(query, fused, store);
  return fused.slice(0, n);
}
