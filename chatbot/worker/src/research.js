// "Related research": reports to link under an answer whether or not the model cited them.
// Links are built from the catalog the index builder verified, never from model text.
//
// Candidates, in order: reports curated on the position sections the model cited, reports
// curated on the sections that best match the question (the model may have cited none),
// then publications the search found, but only when the answer itself cited a retrieved
// excerpt (`fromHits`). A score alone cannot tell "who is the director?" from a research
// question; the model's own citation can. Anything already shown as a source is skipped.
import { tokenize } from "./tokenize.js";

const K1 = 1.5;
const B = 0.75;
const MIN_SECTION_SCORE = 4; // below this a section is not really about the question
const MIN_HIT_SCORE = 6; // same for a retrieved publication chunk

const cache = new WeakMap();

function sectionIndex(index) {
  let s = cache.get(index);
  if (s) return s;
  const docs = index.core
    .filter((c) => c.research?.length)
    .map((c) => ({ c, tf: new Map(), len: 0 }));
  const df = new Map();
  for (const d of docs) {
    for (const t of tokenize(`${d.c.title} ${d.c.title} ${d.c.text}`)) {
      d.tf.set(t, (d.tf.get(t) ?? 0) + 1);
      d.len++;
    }
    for (const t of d.tf.keys()) df.set(t, (df.get(t) ?? 0) + 1);
  }
  s = { docs, df, avg: docs.reduce((a, d) => a + d.len, 0) / Math.max(docs.length, 1) };
  cache.set(index, s);
  return s;
}
/** The curated sections that best match a question, best first. */
export function matchSections(index, query, k = 2) {
  const { docs, df, avg } = sectionIndex(index);
  const n = docs.length;
  const scored = docs
    .map((d) => {
      let score = 0;
      for (const t of new Set(tokenize(query))) {
        const tf = d.tf.get(t);
        if (!tf) continue;
        const idf = Math.log(1 + (n - df.get(t) + 0.5) / (df.get(t) + 0.5));
        score += (idf * tf * (K1 + 1)) / (tf + K1 * (1 - B + (B * d.len) / avg));
      }
      return { section: d.c, score };
    })
    .filter((x) => x.score >= MIN_SECTION_SCORE)
    .sort((a, b) => b.score - a.score);
  return scored.slice(0, k);
}

export function suggestResearch({ index, query, hits = [], citedCoreIds = [], fromHits = false, exclude = [], limit = 3 }) {
  const urls = [];
  const byId = new Map(index.core.map((s) => [s.id, s]));
  for (const id of citedCoreIds) urls.push(...(byId.get(id)?.research ?? []));
  for (const m of matchSections(index, query)) urls.push(...m.section.research);
  const top = hits[0]?.score ?? 0;
  for (const h of fromHits ? hits : []) {
    if (h.k === "publication" && h.u && h.score >= MIN_HIT_SCORE && h.score >= 0.65 * top) urls.push(h.u);
  }
  const skip = new Set(exclude);
  const out = [];
  for (const u of urls) {
    const p = index.pubs?.[u];
    if (!p || skip.has(u) || out.some((o) => o.url === u)) continue;
    out.push({ title: p.t, url: u, year: p.y, pdf: p.p || null });
    if (out.length >= limit) break;
  }
  return out;
}
