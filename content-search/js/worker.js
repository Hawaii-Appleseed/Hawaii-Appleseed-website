// ML Web Worker: owns the bi-encoder (query embedding) and cross-encoder
// (reranking), loaded from the pinned Transformers.js CDN build and cached by
// the browser. Keeps the heavy tensor work off the UI thread.
//
// Same models + pipeline as the Python app (bit-parity was verified at fp32
// during the port; now q8 — see DTYPE below):
//   - bi-encoder  Xenova/all-MiniLM-L6-v2, mean-pooled + L2-normalized, 256-token
//     cap (matches Chroma's ONNX EF and the build-time embeddings.bin).
//   - cross-encoder Xenova/ms-marco-MiniLM-L-6-v2, RAW logits (no sigmoid) —
//     this is what sentence-transformers CrossEncoder.predict returns.

import {
  pipeline,
  AutoTokenizer,
  AutoModelForSequenceClassification,
  env,
} from "https://cdn.jsdelivr.net/npm/@huggingface/transformers@3.7.5";

// Pull weights from the HF Hub CDN; we ship no model files.
env.allowLocalModels = false;

const EMBED_MODEL = "Xenova/all-MiniLM-L6-v2";
const RERANK_MODEL = "Xenova/ms-marco-MiniLM-L-6-v2";
// q8 (model_quantized.onnx): 44 MB total download vs 173 MB at fp32, and
// quantized ops are faster on WASM. The original fp32 pin bought bit-parity
// with the Python app during the port; quality at q8 re-validated with
// tools/probe_quality.mjs. Embedder dtype MUST match tools/embed_corpus.mjs
// (query and corpus share one embedding space); the reranker has no
// corpus-side counterpart, so its dtype is free-standing.
const DTYPE = "q8";
const MAX_TOKENS = 256; // bi-encoder cap; keep in lockstep with embed_corpus.mjs

let extractor = null;
let rerankTok = null;
let rerankModel = null;
// Two-phase readiness: the embedder (22 MB) loads and warms first so hybrid
// dense+BM25 search works at the halfway point; the reranker (another 22 MB)
// follows serially — deliberately not in parallel, so it doesn't contend for
// bandwidth with the model that unlocks results sooner. `embed` calls await
// only embedderReady; `rerank` (and init's resolution) await full readiness.
let embedderReady = null;
let fullReady = null;

function progress(msg) {
  self.postMessage({ type: "progress", msg });
}

async function initEmbedder() {
  progress("Loading search model…");
  extractor = await pipeline("feature-extraction", EMBED_MODEL, {
    dtype: DTYPE,
    progress_callback: (p) => {
      if (p.status === "progress" && p.file && p.progress != null) {
        progress(`Downloading embedder ${p.file} ${Math.round(p.progress)}%`);
      }
    },
  });
  extractor.tokenizer.model_max_length = MAX_TOKENS;
  await embed("warm up");
  self.postMessage({ type: "phase", phase: "embedder" });
}

async function initReranker() {
  progress("Loading relevance model…");
  rerankTok = await AutoTokenizer.from_pretrained(RERANK_MODEL);
  rerankModel = await AutoModelForSequenceClassification.from_pretrained(RERANK_MODEL, {
    dtype: DTYPE,
    progress_callback: (p) => {
      if (p.status === "progress" && p.file && p.progress != null) {
        progress(`Downloading reranker ${p.file} ${Math.round(p.progress)}%`);
      }
    },
  });
  await rerank([["warm", "up"]]);
  progress("Ready");
  self.postMessage({ type: "phase", phase: "full" });
  self.postMessage({ type: "ready" });
}

function startInit() {
  if (!embedderReady) {
    embedderReady = initEmbedder();
    fullReady = embedderReady.then(initReranker);
  }
  return fullReady;
}

async function embed(text) {
  const res = await extractor(text, { pooling: "mean", normalize: true });
  return Float32Array.from(res.data);
}

const RERANK_BATCH = 32;

async function rerank(pairs) {
  if (pairs.length === 0) return [];
  const out = new Array(pairs.length);
  for (let i = 0; i < pairs.length; i += RERANK_BATCH) {
    const batch = pairs.slice(i, i + RERANK_BATCH);
    const queries = batch.map((p) => p[0]);
    const docs = batch.map((p) => p[1]);
    const inputs = rerankTok(queries, {
      text_pair: docs,
      padding: true,
      truncation: true,
    });
    const { logits } = await rerankModel(inputs);
    // Single-logit regression head -> one score per row (raw, no activation).
    const data = logits.data; // length batch.length * 1
    for (let j = 0; j < batch.length; j++) out[i + j] = Number(data[j]);
  }
  return out;
}

self.onmessage = async (e) => {
  const { id, type, payload } = e.data;
  try {
    if (type === "init") {
      await startInit();
      self.postMessage({ id, type: "result", payload: true });
      return;
    }
    startInit();
    if (type === "embed") {
      await embedderReady; // don't block queries on the reranker download
      const vec = await embed(payload.text);
      self.postMessage({ id, type: "result", payload: vec }, [vec.buffer]);
    } else if (type === "rerank") {
      await fullReady;
      const scores = await rerank(payload.pairs);
      self.postMessage({ id, type: "result", payload: scores });
    } else {
      throw new Error(`unknown message type: ${type}`);
    }
  } catch (err) {
    self.postMessage({ id, type: "error", error: String(err && err.stack || err) });
  }
};
