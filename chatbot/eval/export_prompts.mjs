// Writes the exact prompts the Worker would send (rules + knowledge once, then one excerpts block
// and question per case) to a file, so a model can be run on them without an API key, e.g. through
// subagents on a Claude subscription. Grade the saved answers with: run_eval.mjs --replay answers.json
//   node eval/export_prompts.mjs --ids a,b,c --out prompts.md
import { readFileSync, writeFileSync } from "node:fs";
import { buildExcerpts, buildSystem } from "../worker/src/prompt.js";
import { queryFor, search } from "../worker/src/retrieve.js";

const opt = (n) => process.argv[process.argv.indexOf(`--${n}`) + 1];
const ids = opt("ids").split(",");
const here = new URL(".", import.meta.url);
const index = JSON.parse(readFileSync(new URL("../worker/src/index.json", here), "utf8"));
const cases = readFileSync(new URL("golden.jsonl", here), "utf8").trim().split("\n").map((l) => JSON.parse(l));

let out = `# SYSTEM PROMPT (applies to every case)\n\n${buildSystem(index.core)}\n\n`;
for (const id of ids) {
  const c = cases.find((x) => x.id === id);
  if (!c) throw new Error(`no case ${id}`);
  const hits = search(index, queryFor([{ role: "user", content: c.q }]));
  out += `\n=====================\n# CASE ${id}\n\n${buildExcerpts(hits)}\n\n# VISITOR QUESTION\n\n${c.q}\n`;
}
writeFileSync(opt("out"), out);
console.log(`wrote ${opt("out")}: ${ids.length} cases, ${Math.round(out.length / 4)} approx tokens`);
