// BM25 lookup over the prebuilt postings in index.json (see build_index.py).
// The heavy work (tokenizing the corpus, document frequencies) happens at build
// time; a query only tokenizes itself and walks the postings of its own terms.
import { tokenize } from "./tokenize.js";

const K1 = 1.5;
const B = 0.75;

/** The text to search for: the latest question, plus the one before it when the
 *  latest is a short follow-up ("what about renters?"). */
export function queryFor(messages) {
  const users = messages.filter((m) => m.role === "user").map((m) => m.content);
  const last = users[users.length - 1] ?? "";
  if (tokenize(last).length < 4 && users.length > 1) return `${users[users.length - 2]} ${last}`;
  return last;
}

/** Top `k` chunks for `query`, at most `perDoc` from any one document. */
export function search(index, query, { k = 6, perDoc = 2 } = {}) {
  const { n, avgdl, dl, post } = index.bm25;
  const scores = new Map();
  for (const term of new Set(tokenize(query))) {
    const p = post[term];
    if (!p) continue;
    const df = p.length / 2;
    const idf = Math.log(1 + (n - df + 0.5) / (df + 0.5));
    for (let i = 0; i < p.length; i += 2) {
      const ci = p[i];
      const tf = p[i + 1];
      const s = (idf * tf * (K1 + 1)) / (tf + K1 * (1 - B + (B * dl[ci]) / avgdl));
      scores.set(ci, (scores.get(ci) ?? 0) + s);
    }
  }
  const ranked = [...scores.entries()]
    .map(([ci, s]) => {
      const c = index.chunks[ci];
      // A gentle lean toward recent writing: the organization's voice and the facts move on.
      return [ci, s * (1 + 0.03 * Math.max(0, (c.y ?? 2021) - 2021))];
    })
    .sort((a, b) => b[1] - a[1]);
  const hits = [];
  const perDocCount = new Map();
  for (const [ci, score] of ranked) {
    const c = index.chunks[ci];
    const key = c.u ?? c.t;
    if ((perDocCount.get(key) ?? 0) >= perDoc) continue;
    perDocCount.set(key, (perDocCount.get(key) ?? 0) + 1);
    hits.push({ ...c, score });
    if (hits.length >= k) break;
  }
  return hits;
}
