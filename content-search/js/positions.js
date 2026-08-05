// HA position matching — port of positions_index.PositionsIndex.match().
// A bill number in the query wins outright; otherwise the cross-encoder ranks
// the entries' match_text (scoring delegated to the worker).
//
// NOTE the case-SENSITIVE bill regex here (\b([HS][BR])\s?(\d{3,5})\b) — this is
// distinct from retrieval's case-insensitive bill handling; preserve it.

const BILL_RE = /\b([HS][BR])\s?(\d{3,5})\b/g;

export class PositionsIndex {
  constructor(entries) {
    this.entries = entries; // [{title, section, position, core_argument, standard_ask, bills, match_text}]
    this.billIndex = new Map();
    for (const e of entries) {
      for (const b of e.bills) {
        if (!this.billIndex.has(b.bill)) this.billIndex.set(b.bill, e);
      }
    }
  }

  // rerank(pairs)->Promise<number[]>; minScore mirrors the Python default 0.0.
  async match(query, rerank, minScore = 0.0) {
    BILL_RE.lastIndex = 0;
    let m;
    while ((m = BILL_RE.exec(query)) !== null) {
      const key = `${m[1].toUpperCase()}${m[2]}`;
      const e = this.billIndex.get(key);
      if (e) return e;
    }
    if (this.entries.length === 0) return null;
    let scores;
    try {
      scores = await rerank(this.entries.map((e) => [query, e.match_text]));
    } catch {
      return null;
    }
    let bestI = 0;
    for (let i = 1; i < scores.length; i++) if (scores[i] > scores[bestI]) bestI = i;
    return scores[bestI] >= minScore ? this.entries[bestI] : null;
  }
}
