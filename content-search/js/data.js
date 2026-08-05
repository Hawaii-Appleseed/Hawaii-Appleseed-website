// Data layer: fetch + assemble the in-memory search store.
// buildStore() is pure (no fetch) so the Node test harness can build the same
// store from local files; loadData() is the browser fetch wrapper.

import { BM25 } from "./bm25.js";
import { PositionsIndex } from "./positions.js";

// chunks, bm25Stats, docs, positions, topics: parsed JSON.
// embeddings: Float32Array (length n*dim). meta: embeddings.meta.json.
export function buildStore({ chunks, bm25Stats, docs, positions, topics, embeddings, meta }) {
  const dim = meta.dim;
  const n = chunks.length;
  if (embeddings.length !== n * dim) {
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

export async function loadData(base = "data") {
  const j = (p) => fetch(`${base}/${p}`).then((r) => {
    if (!r.ok) throw new Error(`fetch ${p}: ${r.status}`);
    return r.json();
  });
  const [chunks, bm25Stats, docs, positions, topics, meta] = await Promise.all([
    j("chunks.json"), j("bm25.json"), j("docs.json"),
    j("positions.json"), j("topics.json"), j("embeddings.meta.json"),
  ]);
  const buf = await fetch(`${base}/embeddings.bin`).then((r) => {
    if (!r.ok) throw new Error(`fetch embeddings.bin: ${r.status}`);
    return r.arrayBuffer();
  });
  const embeddings = new Float32Array(buf);
  return buildStore({ chunks, bm25Stats, docs, positions, topics, embeddings, meta });
}
