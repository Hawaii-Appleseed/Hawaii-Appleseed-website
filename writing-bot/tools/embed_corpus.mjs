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
// Reuse (storage-audit item 14): rows are keyed by sha256(chunk text). Chunks
// whose text is unchanged keep their previous vector byte for byte; only new
// text is embedded (see embed_reuse.mjs). The previous bundle is read from git
// HEAD of the repo that holds content-search/data (in CI: the `hub` checkout,
// reached through the content-search symlink), NOT from the working tree,
// because build_static.py has already overwritten chunks.json there. Reuse is
// off for a forced run (EMBED_FORCE=1 or --force) and whenever the previous
// meta's model/dtype/dim/max_tokens/transformers.js version differ.
//
// Usage:  node tools/embed_corpus.mjs [--force]
// Test:   node tools/embed_reuse.test.mjs   (model-free)

import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { readFileSync, realpathSync, writeFileSync } from "node:fs";
import { cacheKey, parsePrev, reuseOrEmbed } from "./embed_reuse.mjs";
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

// Read one file of the previous bundle from git HEAD of the repo containing
// DATA. Returns null if anything goes wrong (not a repo, no such commit, ...).
function gitShow(name, encoding) {
  try {
    const buf = execFileSync(
      "git",
      ["-C", realpathSync(DATA), "show", `HEAD:./${name}`],
      { maxBuffer: 256 * 1024 * 1024, stdio: ["ignore", "pipe", "ignore"] }
    );
    return encoding ? buf.toString(encoding) : buf;
  } catch {
    return null;
  }
}

async function main() {
  const force =
    process.argv.includes("--force") ||
    ["1", "true"].includes(String(process.env.EMBED_FORCE || "").toLowerCase());
  const chunks = JSON.parse(readFileSync(resolve(DATA, "chunks.json"), "utf-8"));
  const texts = chunks.map((c) => c.text);

  const key = {
    model: MODEL,
    dtype: DTYPE,
    dim: DIM,
    max_tokens: MAX_TOKENS,
    transformersjs_version: TJS_VERSION,
  };
  let prev = null;
  let reason;
  if (!force) {
    ({ prev, reason } = parsePrev(
      {
        metaText: gitShow("embeddings.meta.json", "utf-8"),
        chunksText: gitShow("chunks.json", "utf-8"),
        binBuf: gitShow("embeddings.bin"),
      },
      key
    ));
  }
  console.log(`Embedding ${texts.length} chunks with ${MODEL} (${DTYPE})…`);

  // Loaded lazily: a run that reuses every row never touches the model.
  let extractor = null;
  const embedFn = async (todo) => {
    const { pipeline } = await import("@huggingface/transformers");
    extractor = await pipeline("feature-extraction", MODEL, { dtype: DTYPE });
    // Force the 256-token cap (Chroma/sentence-transformers parity).
    extractor.tokenizer.model_max_length = MAX_TOKENS;
    const o = new Float32Array(todo.length * DIM);
    for (let i = 0; i < todo.length; i += BATCH) {
      const batch = todo.slice(i, i + BATCH);
      const res = await extractor(batch, { pooling: "mean", normalize: true });
      // res.data is a flat Float32Array of [batch.length x DIM].
      o.set(res.data, i * DIM);
      if (i % (BATCH * 8) === 0) {
        process.stdout.write(`  ${Math.min(i + BATCH, todo.length)}/${todo.length}\r`);
      }
    }
    return o;
  };

  const res = await reuseOrEmbed({ texts, key, prev, force, embedFn, reason });
  const out = res.out;
  console.log(
    `\n  done: reused ${res.reused}, embedded ${res.embedded}` +
      (res.reused === 0 && res.reason ? ` (no reuse: ${res.reason})` : "")
  );

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
    max_tokens: MAX_TOKENS,
  };
  if (cacheKey(meta) !== cacheKey(key)) throw new Error("meta/cache-key drift");
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
