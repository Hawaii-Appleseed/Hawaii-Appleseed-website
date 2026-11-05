// Pull the ratings staff left in the internal pilot, newest last, so "what is wrong with it" is data.
//   node eval/pull_feedback.mjs              # writes chatbot/feedback.jsonl and prints a summary
//   node eval/pull_feedback.mjs --cases      # also writes feedback-cases.jsonl: a skeleton eval case per "No"
// Reads the Worker's KV store (the namespace id in worker/wrangler.toml) with your wrangler login.
// The output holds staff emails and their questions: it is git-ignored. Do not commit or share it.
import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";

const here = new URL(".", import.meta.url);
const worker = new URL("../worker/", here).pathname;
const toml = readFileSync(`${worker}wrangler.toml`, "utf8");
const ns = /\[\[kv_namespaces\]\][^\[]*?id\s*=\s*"([0-9a-f]{32})"/s.exec(toml)?.[1];
if (!ns) { console.error("no KV namespace id in worker/wrangler.toml"); process.exit(2); }
const wrangler = (...a) => execFileSync("npx", ["wrangler", ...a, "--namespace-id", ns, "--remote"], { cwd: worker, encoding: "utf8", maxBuffer: 64e6, env: { ...process.env, WRANGLER_SEND_METRICS: "false", CI: "1" } });

const names = JSON.parse(wrangler("kv", "key", "list", "--prefix", "fb:")).map((k) => k.name).sort();
const entries = names.map((n) => ({ key: n, ...JSON.parse(wrangler("kv", "key", "get", n)) }));
const out = new URL("../feedback.jsonl", here);
writeFileSync(out, entries.map((e) => JSON.stringify(e)).join("\n") + (entries.length ? "\n" : ""));

const down = entries.filter((e) => e.rating === "down");
console.log(`${entries.length} ratings (${entries.length - down.length} helpful, ${down.length} not) -> chatbot/feedback.jsonl`);
for (const e of down) console.log(`\n NO  ${e.ts.slice(0, 16)}  "${e.question}"\n     said: ${e.answer.slice(0, 160)}${e.answer.length > 160 ? "..." : ""}\n     why:  ${e.comment || "(no comment)"}`);

if (process.argv.includes("--cases")) {
  const cases = down.map((e, i) => ({ id: `fb-${e.ts.slice(0, 10)}-${i + 1}`, cat: "feedback", q: e.question, note: e.comment || "rated not helpful", bad_answer: e.answer, include_any: [], exclude: [] }));
  writeFileSync(new URL("../feedback-cases.jsonl", here), cases.map((c) => JSON.stringify(c)).join("\n") + (cases.length ? "\n" : ""));
  console.log(`\n${cases.length} skeleton case(s) -> chatbot/feedback-cases.jsonl (fill in include_any / exclude, then move into eval/golden.jsonl)`);
}
