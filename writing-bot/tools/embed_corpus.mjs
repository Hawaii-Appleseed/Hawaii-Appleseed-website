// Build-time corpus embedding for the static Appleseed Source Search.
//
// Reads static-search/data/chunks.json and embeds every chunk with the EXACT
// model + dtype the browser uses at query time (Xenova/all-MiniLM-L6-v2, fp32,
// mean-pooled + L2-normalized). Writing the corpus with the same Transformers.js
// realization the browser runs guarantees query and corpus share one embedding
// space — no Python-ONNX-vs-JS drift (see plan, decision D1).
//
// Output:
//   static-search/data/embeddings.bin       Float32 LE, row-major [n x 384]
//   static-search/data/embeddings.meta.json {model, dtype, dim, count, sha256, version}
//
// Usage:  node tools/embed_corpus.mjs

import { pipeline } from "@huggingface/transformers";
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
// __dirname is writing-bot/tools/; the app + data live at <site root>/content-search/.
const DATA = resolve(__dirname, "..", "..", "content-search", "data");

const MODEL = "Xenova/all-MiniLM-L6-v2";
// q8 (model_quantized.onnx) cuts the browser's embedder download 86→22 MB.
// Retrieval quality validated against fp32 with tools/probe_quality.mjs
// (top-10 overlap on the probe query set). Keep in lockstep with
// js/worker.js DTYPE — query and corpus must share one embedding space.
const DTYPE = "q8";
const DIM = 384;
// sentence-transformers / Chroma's ONNX EF truncates all-MiniLM-L6-v2 at 256
// tokens (NOT the model's 512 default). The browser query embedder MUST use the
// same cap, and so must this build step, or query/corpus land in different
// spaces for any chunk longer than 256 tokens. Keep this in lockstep with
// js/worker.js MAX_TOKENS.
const MAX_TOKENS = 256;
// Keep in lockstep with the worker's import URL pin.
const TJS_VERSION = "3.7.5";

const BATCH = 64;

async function main() {
  const chunks = JSON.parse(readFileSync(resolve(DATA, "chunks.json"), "utf-8"));
  const texts = chunks.map((c) => c.text);
  console.log(`Embedding ${texts.length} chunks with ${MODEL} (${DTYPE})…`);

  const extractor = await pipeline("feature-extraction", MODEL, { dtype: DTYPE });
  // Force the 256-token cap (Chroma/sentence-transformers parity).
  extractor.tokenizer.model_max_length = MAX_TOKENS;

  const out = new Float32Array(texts.length * DIM);
  for (let i = 0; i < texts.length; i += BATCH) {
    const batch = texts.slice(i, i + BATCH);
    const res = await extractor(batch, { pooling: "mean", normalize: true });
    // res.data is a flat Float32Array of [batch.length x DIM].
    const data = res.data;
    out.set(data, i * DIM);
    if (i % (BATCH * 8) === 0) {
      process.stdout.write(`  ${Math.min(i + BATCH, texts.length)}/${texts.length}\r`);
    }
  }
  console.log(`\n  done embedding.`);

  const buf = Buffer.from(out.buffer, out.byteOffset, out.byteLength);
  writeFileSync(resolve(DATA, "embeddings.bin"), buf);

  const sha256 = createHash("sha256").update(buf).digest("hex");
  const meta = {
    model: MODEL,
    dtype: DTYPE,
    dim: DIM,
    count: texts.length,
    sha256,
    transformersjs_version: TJS_VERSION,
  };
  writeFileSync(
    resolve(DATA, "embeddings.meta.json"),
    JSON.stringify(meta, null, 2)
  );
  console.log(
    `Wrote embeddings.bin (${(buf.byteLength / 1e6).toFixed(2)} MB) + meta.`
  );
  console.log(`  sha256=${sha256.slice(0, 16)}…`);

  // Patch the embeddings entry into the polling manifest build_static.py wrote.
  const apiPath = resolve(DATA, "..", "api.json");
  const api = JSON.parse(readFileSync(apiPath, "utf-8"));
  api.files["embeddings.bin"] = { path: "data/embeddings.bin", sha256 };
  api.files["embeddings.meta.json"] = { path: "data/embeddings.meta.json" };
  api.model = { embed: MODEL, dtype: DTYPE, dim: DIM };
  writeFileSync(apiPath, JSON.stringify(api, null, 2));
  console.log("  patched api.json with embeddings info");
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
