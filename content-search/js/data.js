// Data layer: fetch + assemble the in-memory search store.
// buildStore() is pure (no fetch) so the Node test harness can build the same
// store from local files; loadData() is the browser fetch wrapper.

import { BM25 } from "./bm25.js";
import { PositionsIndex } from "./positions.js";

// chunks, bm25Stats, docs, positions, topics: parsed JSON.
// embeddings: Float32Array (length n*dim), or null — keyword (BM25) search
// works without it, so the browser attaches it later via loadEmbeddings().
// meta: embeddings.meta.json.
export function buildStore({ chunks, bm25Stats, docs, positions, topics, embeddings = null, meta }) {
  const dim = meta.dim;
  const n = chunks.length;
  if (embeddings && embeddings.length !== n * dim) {
    throw new Error(`embeddings length ${embeddings.length} != ${n}*${dim}`);
  }
  if (meta.count !== n) {
    throw new Error(`meta.count ${meta.count} != chunks ${n}`);
  }
  return {
    chunks,
    embeddings,
    dim,
    n,
    bm25: new BM25(bm25Stats),
    docs,              // {source: {title, stance, ref, ...}}
    positions: new PositionsIndex(positions),
    topics,
    meta,
  };
}

// Per-chunk effective stance, resolved via the precomputed per-document table.
export function chunkStance(store, chunk) {
  const d = store.docs[chunk.source];
  return d ? d.stance : null;
}

// Loads ONLY what keyword search needs (~1.8 MB gzipped). embeddings.bin is
// another 2.7 MB — 60% of the bundle — and is useless until the embedder model
// arrives, so it is deliberately NOT on this path; the app fetches it via
// loadEmbeddings() once the corpus is in and the model download has started.
export async function loadData(base = "data") {
  const j = (p) => fetch(`${base}/${p}`).then((r) => {
    if (!r.ok) throw new Error(`fetch ${p}: ${r.status}`);
    return r.json();
  });
  const [chunks, bm25Stats, docs, positions, topics, meta] = await Promise.all([
    j("chunks.json"), j("bm25.json"), j("docs.json"),
    j("positions.json"), j("topics.json"), j("embeddings.meta.json"),
  ]);
  return buildStore({ chunks, bm25Stats, docs, positions, topics, meta });
}

// Fetch the embedding matrix and attach it to an existing store. Runs
// concurrently with the model download (different host: Pages vs the HF CDN),
// so dense search becomes available as soon as the slower of the two lands.
export async function loadEmbeddings(store, base = "data") {
  if (store.embeddings) return store;
  const buf = await fetch(`${base}/embeddings.bin`).then((r) => {
    if (!r.ok) throw new Error(`fetch embeddings.bin: ${r.status}`);
    return r.arrayBuffer();
  });
  const embeddings = new Float32Array(buf);
  if (embeddings.length !== store.n * store.dim) {
    throw new Error(`embeddings length ${embeddings.length} != ${store.n}*${store.dim}`);
  }
  store.embeddings = embeddings;
  return store;
}
