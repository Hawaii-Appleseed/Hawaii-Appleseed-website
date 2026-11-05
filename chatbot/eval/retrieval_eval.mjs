// Does the right report reach the model? Plain-language questions -> BM25 top-6 -> expected report in the hits
// (by URL slug) or in the related-research list. Offline, no key.
//   node eval/retrieval_eval.mjs [--verbose]
import { readFileSync } from "node:fs";
import { suggestResearch } from "../worker/src/research.js";
import { queryFor, search } from "../worker/src/retrieve.js";

const here = new URL(".", import.meta.url);
const index = JSON.parse(readFileSync(new URL("../worker/src/index.json", here), "utf8"));
const cases = readFileSync(new URL("retrieval.jsonl", here), "utf8").trim().split("\n").map((l) => JSON.parse(l));
const verbose = process.argv.includes("--verbose");

let hit = 0;
const misses = [];
for (const c of cases) {
  const messages = [{ role: "user", content: c.q }];
  const hits = search(index, queryFor(messages));
  const urls = hits.map((h) => h.u ?? "").concat(suggestResearch({ index, query: c.q, hits, fromHits: true }).map((r) => r.url));
  const ok = c.any.some((slug) => urls.some((u) => u.includes(slug)));
  if (ok) hit++; else misses.push({ q: c.q, got: [...new Set(hits.map((h) => (h.u ?? h.t).split("/").pop()))].slice(0, 5) });
}
console.log(`retrieval: ${hit}/${cases.length} questions reach an expected report (${Math.round((100 * hit) / cases.length)}%)`);
for (const m of misses) console.log(`  MISS "${m.q}"${verbose ? `  got: ${m.got.join(", ")}` : ""}`);
process.exit(0);
