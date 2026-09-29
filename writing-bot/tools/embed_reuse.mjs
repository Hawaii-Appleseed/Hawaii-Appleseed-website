// Pure reuse logic for embed_corpus.mjs (no model, no filesystem, no git).
//
// Why: embeddings.bin is 63% of the hub's packed git history. Re-embedding every
// chunk on each rebuild shifts every vector (q8 batch composition), so the file
// never deltas (~2.9 MB per rebuild). Instead, key each row by sha256(text) and
// re-embed only chunks whose text is new; copy the rest from the previous
// bundle, byte for byte.
//
// Everything here is deterministic and testable with fake vectors:
// see embed_reuse.test.mjs.

import { createHash } from "node:crypto";

// Fields that define an embedding space. A previous bundle is reusable only if
// ALL of them match the current run. (`count` and `sha256` describe the file,
// not the space, so they are not part of the key.) A previous meta written
// before max_tokens was recorded has max_tokens undefined and so never matches:
// the first run after that change is one full re-embed.
export const KEY_FIELDS = [
  "model",
  "dtype",
  "dim",
  "max_tokens",
  "transformersjs_version",
];

export function textHash(text) {
  return createHash("sha256").update(text, "utf-8").digest("hex");
}

export function cacheKey(meta) {
  return KEY_FIELDS.map((f) => `${f}=${JSON.stringify(meta?.[f])}`).join("|");
}

// Turn the three raw files of the previous bundle into {rows: Map<hash,
// Float32Array(dim)>, meta} or {prev: null, reason}. Never throws: any
// missing/corrupt/inconsistent input means "no reuse".
//   metaText, chunksText: strings (or null/undefined if unavailable)
//   binBuf: Buffer/Uint8Array (or null/undefined)
export function parsePrev({ metaText, chunksText, binBuf }, key) {
  const none = (reason) => ({ prev: null, reason });
  if (metaText == null || chunksText == null || binBuf == null) {
    return none("previous bundle unavailable");
  }
  let meta, chunks;
  try {
    meta = JSON.parse(metaText);
    chunks = JSON.parse(chunksText);
  } catch (e) {
    return none(`previous bundle unparseable (${e.message})`);
  }
  if (!meta || typeof meta !== "object" || !Array.isArray(chunks)) {
    return none("previous bundle malformed");
  }
  if (cacheKey(meta) !== cacheKey(key)) {
    const diff = KEY_FIELDS.filter((f) => meta[f] !== key[f]).join(", ");
    return none(`cache key mismatch (${diff})`);
  }
  const dim = key.dim;
  if (
    !Number.isInteger(meta.count) ||
    meta.count !== chunks.length ||
    binBuf.byteLength !== meta.count * dim * 4
  ) {
    return none("previous chunks/embeddings/meta counts disagree");
  }
  if (
    typeof meta.sha256 !== "string" ||
    createHash("sha256").update(binBuf).digest("hex") !== meta.sha256
  ) {
    return none("previous embeddings.bin does not match its meta sha256");
  }
  // Copy into an aligned buffer (a Buffer slice may sit at an odd byteOffset).
  const all = new Float32Array(
    binBuf.buffer.slice(binBuf.byteOffset, binBuf.byteOffset + binBuf.byteLength)
  );
  const rows = new Map();
  for (let i = 0; i < chunks.length; i++) {
    const t = chunks[i]?.text;
    if (typeof t !== "string") return none("previous chunk without text");
    const h = textHash(t);
    // Duplicate texts: first occurrence wins (any copy is a valid vector).
    if (!rows.has(h)) rows.set(h, all.subarray(i * dim, (i + 1) * dim));
  }
  return { prev: { rows, meta } };
}

// Build the full [texts.length x dim] matrix, embedding only what is not
// available from `prev`.
//   texts:   string[] in output order
//   key:     current {model,dtype,dim,max_tokens,transformersjs_version}
//   prev:    result of parsePrev().prev, or null
//   force:   true disables reuse entirely
//   embedFn: async (texts: string[]) => Float32Array(texts.length * dim)
//            (called at most once, with unique texts not found in prev)
// Returns {out, reused, embedded, reason}.
export async function reuseOrEmbed({ texts, key, prev, force, embedFn, reason }) {
  const dim = key.dim;
  const out = new Float32Array(texts.length * dim);
  let usable = prev;
  if (force) {
    usable = null;
    reason = "forced run";
  } else if (usable && cacheKey(usable.meta) !== cacheKey(key)) {
    // Defense in depth: parsePrev already checks this.
    usable = null;
    reason = "cache key mismatch";
  }

  const todoTexts = []; // unique texts to embed, first-seen order
  const todoIndex = new Map(); // hash -> index into todoTexts
  const pending = []; // [outputRow, todoIdx]
  let reused = 0;
  for (let i = 0; i < texts.length; i++) {
    const h = textHash(texts[i]);
    const old = usable?.rows.get(h);
    if (old) {
      out.set(old, i * dim);
      reused++;
      continue;
    }
    let ti = todoIndex.get(h);
    if (ti === undefined) {
      ti = todoTexts.length;
      todoTexts.push(texts[i]);
      todoIndex.set(h, ti);
    }
    pending.push([i, ti]);
  }

  if (todoTexts.length > 0) {
    const vecs = await embedFn(todoTexts);
    if (vecs.length !== todoTexts.length * dim) {
      throw new Error(
        `embedFn returned ${vecs.length} floats, expected ${todoTexts.length * dim}`
      );
    }
    for (const [row, ti] of pending) {
      out.set(vecs.subarray(ti * dim, (ti + 1) * dim), row * dim);
    }
  }
  return { out, reused, embedded: pending.length, uniqueEmbedded: todoTexts.length, reason };
}
