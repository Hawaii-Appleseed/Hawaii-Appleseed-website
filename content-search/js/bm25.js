// BM25Okapi scoring over the precomputed stats in data/bm25.json.
//
// IDF and avgdl were computed in Python over the FULL corpus (incl. memory) and
// floored per the ATIRE variant; we only ship public-vocab IDF + public per-doc
// term-frequencies. Score formula matches rank_bm25.BM25Okapi.get_scores exactly:
//   score(d) = Σ_t idf[t] · tf · (k1+1) / (tf + k1·(1 − b + b·len_d/avgdl))
// Verified bit-for-bit against Python (test/run_all.mjs, build_static --verify).

export class BM25 {
  constructor(stats) {
    this.k1 = stats.k1;
    this.b = stats.b;
    this.avgdl = stats.avgdl;
    this.idf = stats.idf; // {term: float}
    this.docs = stats.docs; // [{len, tf:{term:count}}]
    this.n = this.docs.length;

    // Inverted index: term -> [docIdx, ...] so a query only touches docs that
    // actually contain one of its terms (the rest score exactly 0).
    this.postings = new Map();
    for (let i = 0; i < this.docs.length; i++) {
      for (const term of Object.keys(this.docs[i].tf)) {
        let arr = this.postings.get(term);
        if (!arr) {
          arr = [];
          this.postings.set(term, arr);
        }
        arr.push(i);
      }
    }
  }

  // Returns a Float64Array of length n with the BM25 score for every public doc.
  getScores(queryTokens) {
    const scores = new Float64Array(this.n);
    const { k1, b, avgdl } = this;
    for (const q of queryTokens) {
      const idf = this.idf[q];
      if (idf === undefined) continue;
      const posting = this.postings.get(q);
      if (!posting) continue;
      for (const i of posting) {
        const doc = this.docs[i];
        const tf = doc.tf[q] || 0;
        scores[i] +=
          idf * ((tf * (k1 + 1)) / (tf + k1 * (1 - b + (b * doc.len) / avgdl)));
      }
    }
    return scores;
  }

  // Mirror retrieval._bm25_search: argsort desc (stable), drop score<=0, apply
  // the where-filter, take top k. `matchesWhere(idx)` is supplied by the caller.
  search(queryTokens, k, matchesWhere) {
    const scores = this.getScores(queryTokens);
    const order = Array.from({ length: this.n }, (_, i) => i);
    // Stable sort by score desc; equal scores keep ascending index (matches
    // Python's stable `sorted(range(n), key=score, reverse=True)`).
    order.sort((a, c) => scores[c] - scores[a]);
    const out = [];
    for (const i of order) {
      if (scores[i] <= 0) break;
      if (!matchesWhere(i)) continue;
      out.push(i);
      if (out.length >= k) break;
    }
    return out;
  }
}
