// Quality probe for a dtype change to the static search models.
//
// Compares dense retrieval in two embedding spaces (e.g. fp32 vs q8): each
// space = corpus embeddings.bin built at that dtype + query embedded at the
// same dtype. Reports top-K overlap and top-1 agreement per probe query, plus
// cross-encoder score-ordering agreement between the two dtypes on the same
// candidate pairs. Used to validate the fp32 -> q8 switch (see js/worker.js).
//
// Usage:
//   node tools/probe_quality.mjs --bin-a <fp32.bin> --dtype-a fp32 \
//                                --bin-b <q8.bin>   --dtype-b q8
//   (bin-b defaults to content-search/data/embeddings.bin, dtype-b q8)

import { pipeline, AutoTokenizer, AutoModelForSequenceClassification } from "@huggingface/transformers";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const DATA = resolve(__dirname, "..", "..", "content-search", "data");

const EMBED_MODEL = "Xenova/all-MiniLM-L6-v2";
const RERANK_MODEL = "Xenova/ms-marco-MiniLM-L-6-v2";
const MAX_TOKENS = 256;
const DIM = 384;
const TOP_K = 10;

// Mirrors eval/static_dump.py PROBE_QUERIES.
const QUERIES = [
  "conveyance tax", "empty homes tax", "universal school meals",
  "SNAP", "housing affordability", "minimum wage", "HB1800",
  "GET on groceries", "earned income tax credit", "HB 2049",
];

function arg(name, dflt) {
  const i = process.argv.indexOf(name);
  return i > -1 ? process.argv[i + 1] : dflt;
}

function loadBin(path, n) {
  const buf = readFileSync(path);
  const arr = new Float32Array(buf.buffer, buf.byteOffset, buf.byteLength / 4);
  if (arr.length !== n * DIM) throw new Error(`${path}: ${arr.length} floats != ${n}x${DIM}`);
  return arr;
}

function topK(queryVec, corpus, n, k) {
  const scores = new Array(n);
  for (let i = 0; i < n; i++) {
    let dot = 0;
    const off = i * DIM;
    for (let d = 0; d < DIM; d++) dot += queryVec[d] * corpus[off + d];
    scores[i] = [i, dot];
  }
  scores.sort((a, b) => b[1] - a[1]);
  return scores.slice(0, k).map(([i]) => i);
}

async function makeEmbedder(dtype) {
  const ex = await pipeline("feature-extraction", EMBED_MODEL, { dtype });
  ex.tokenizer.model_max_length = MAX_TOKENS;
  return async (text) => {
    const res = await ex(text, { pooling: "mean", normalize: true });
    return Float32Array.from(res.data);
  };
}

async function makeReranker(dtype) {
  const tok = await AutoTokenizer.from_pretrained(RERANK_MODEL);
  const model = await AutoModelForSequenceClassification.from_pretrained(RERANK_MODEL, { dtype });
  return async (pairs) => {
    const inputs = tok(pairs.map((p) => p[0]), {
      text_pair: pairs.map((p) => p[1]),
      padding: true, truncation: true,
    });
    const out = await model(inputs);
    return Array.from(out.logits.data);
  };
}

function spearman(a, b) {
  const rank = (xs) => {
    const idx = xs.map((v, i) => [v, i]).sort((p, q) => q[0] - p[0]);
    const r = new Array(xs.length);
    idx.forEach(([, i], pos) => (r[i] = pos));
    return r;
  };
  const ra = rank(a), rb = rank(b), n = a.length;
  let d2 = 0;
  for (let i = 0; i < n; i++) d2 += (ra[i] - rb[i]) ** 2;
  return 1 - (6 * d2) / (n * (n * n - 1));
}

async function main() {
  const chunks = JSON.parse(readFileSync(resolve(DATA, "chunks.json"), "utf-8"));
  const n = chunks.length;

  const binA = arg("--bin-a"), dtypeA = arg("--dtype-a", "fp32");
  const binB = arg("--bin-b", resolve(DATA, "embeddings.bin")), dtypeB = arg("--dtype-b", "q8");
  if (!binA) { console.error("need --bin-a <path to baseline embeddings.bin>"); process.exit(2); }

  const corpusA = loadBin(binA, n), corpusB = loadBin(binB, n);
  console.log(`space A: ${dtypeA} (${binA})`);
  console.log(`space B: ${dtypeB} (${binB})\n`);

  const embedA = await makeEmbedder(dtypeA);
  const embedB = await makeEmbedder(dtypeB);

  let overlapSum = 0, top1Agree = 0;
  console.log(`dense top-${TOP_K} per query:`);
  for (const q of QUERIES) {
    const ta = topK(await embedA(q), corpusA, n, TOP_K);
    const tb = topK(await embedB(q), corpusB, n, TOP_K);
    const inter = ta.filter((i) => tb.includes(i)).length;
    overlapSum += inter;
    if (ta[0] === tb[0]) top1Agree++;
    console.log(`  ${inter}/${TOP_K} overlap, top1 ${ta[0] === tb[0] ? "same" : "DIFFERS"}  ${JSON.stringify(q)}`);
  }
  console.log(`\nmean overlap: ${(overlapSum / QUERIES.length).toFixed(1)}/${TOP_K}, top-1 agreement: ${top1Agree}/${QUERIES.length}`);

  // Reranker: same candidate pairs, scores at both dtypes, rank correlation.
  const rerankA = await makeReranker(dtypeA);
  const rerankB = await makeReranker(dtypeB);
  console.log(`\nreranker rank-correlation over dense-top-${TOP_K} candidates:`);
  let rhoSum = 0, head1 = 0;
  for (const q of QUERIES) {
    const cands = topK(await embedA(q), corpusA, n, TOP_K).map((i) => [q, chunks[i].text]);
    const sa = await rerankA(cands), sb = await rerankB(cands);
    const rho = spearman(sa, sb);
    rhoSum += rho;
    const argmax = (xs) => xs.indexOf(Math.max(...xs));
    if (argmax(sa) === argmax(sb)) head1++;
    console.log(`  rho=${rho.toFixed(3)}, best ${argmax(sa) === argmax(sb) ? "same" : "DIFFERS"}  ${JSON.stringify(q)}`);
  }
  console.log(`\nmean rho: ${(rhoSum / QUERIES.length).toFixed(3)}, best-candidate agreement: ${head1}/${QUERIES.length}`);
}

main().catch((e) => { console.error(e); process.exit(1); });
