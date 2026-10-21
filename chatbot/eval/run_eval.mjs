// Eval for the public Q&A assistant. Reads eval/golden.jsonl.
//
//   node eval/run_eval.mjs --offline          no model, no key: the legal gate and retrieval only
//   node eval/run_eval.mjs                    live: every case through the real handler and model
//   node eval/run_eval.mjs --model claude-haiku-5-5   compare models
//   node eval/run_eval.mjs --case legal       only cases whose id contains "legal"
//   node eval/run_eval.mjs --show             print each live answer
//   node eval/run_eval.mjs --cat org,position,outcome,nopos   only those categories (typical questions)
//   node eval/run_eval.mjs --replay answers.json   grade saved answers ({case id: text}) with the real checks; no API call
//   node eval/run_eval.mjs --dry              no API call: builds every real prompt and ESTIMATES tokens and cost
//                                             (chars/4, 260 output tokens); add --model to price a model
//
// Live runs spend credits: about 56 requests. The key comes from ANTHROPIC_API_KEY or ~/.anthropic_api_key.
import { existsSync, readFileSync } from "node:fs";
import { homedir } from "node:os";
import { handleChat } from "../worker/src/handler.js";
import { isLegalHelpRequest } from "../worker/src/legal.js";
import { suggestResearch } from "../worker/src/research.js";
import { queryFor, search } from "../worker/src/retrieve.js";

const args = process.argv.slice(2);
const flag = (n) => args.includes(`--${n}`);
const opt = (n) => (args.includes(`--${n}`) ? args[args.indexOf(`--${n}`) + 1] : undefined);
const offline = flag("offline");
const dry = flag("dry");
const replayFile = opt("replay");
let _replay;
function replayAnswers() { return (_replay ??= JSON.parse(readFileSync(replayFile, "utf8"))); }
const only = opt("case");
const model = opt("model");
const here = new URL(".", import.meta.url);
const index = JSON.parse(readFileSync(new URL("../worker/src/index.json", here), "utf8"));
const cases = readFileSync(new URL("golden.jsonl", here), "utf8").trim().split("\n").map((l) => JSON.parse(l))
  .filter((c) => !only || c.id.includes(only))
  .filter((c) => !replayFile || c.id in replayAnswers())
  .filter((c) => !opt("cat") || opt("cat").split(",").includes(c.cat));

// $ per million tokens, first-party list prices (API skill table, cached 2026-10-06; re-check before relying on them).
// Cache reads are 0.1x input; cache writes use the 1-hour TTL the handler requests, 2x input.
const PRICES = { "claude-sonnet-5-5": { in: 2, out: 10 }, "claude-haiku-5-5": { in: 0.1, out: 0.5 } };
const priced = model ?? "claude-sonnet-5-5";
function dollars(t) {
  const p = PRICES[priced];
  if (!p) return null;
  return (t.in * p.in + t.cacheRead * p.in * 0.1 + t.cacheWrite * p.in * 2 + t.out * p.out) / 1e6;
}

const lc = (s) => s.toLowerCase();
const has = (text, needle) => lc(text).includes(lc(needle));

function voiceProblems(text) {
  const out = [];
  if (text.includes("!")) out.push("exclamation point");
  if (/\d\s?%/.test(text)) out.push("uses % instead of 'percent'");
  if (/\bHawaii\b/.test(text)) out.push("Hawaii without ʻokina");
  if (/https?:\/\//.test(text)) out.push("raw URL in answer");
  return out;
}

function checkOffline(c) {
  const fails = [];
  const messages = [{ role: "user", content: c.q }];
  if ("legal" in c && c.legal_gate !== false && isLegalHelpRequest(c.q) !== c.legal) fails.push(`legal gate said ${!c.legal}`);
  if (c.legal_gate === false && isLegalHelpRequest(c.q)) fails.push("legal gate caught a case marked model-only");
  if (c.retrieve_any) {
    const hits = search(index, queryFor(messages));
    const blob = lc(hits.map((h) => `${h.t} ${h.u ?? ""}`).join(" | "));
    if (!c.retrieve_any.some((s) => blob.includes(lc(s)))) fails.push(`retrieval missed [${c.retrieve_any}] in: ${hits.map((h) => h.t.slice(0, 40)).join(" | ")}`);
  }
  if (c.related_any || c.related_none) {
    // Offline there is no model citation, so a topical question is assumed to cite an excerpt.
    const hits = search(index, queryFor(messages));
    const rel = suggestResearch({ index, query: c.q, hits, fromHits: !c.related_none });
    fails.push(...relatedProblems(c, rel));
  }
  return fails;
}

function relatedProblems(c, rel) {
  const out = [];
  if (c.related_any && !c.related_any.some((s) => rel.some((r) => r.url.includes(s)))) out.push(`no related research with [${c.related_any}]; got: ${rel.map((r) => r.title).join(" | ") || "none"}`);
  if (c.related_none && rel.length) out.push(`related research on a non-research question: ${rel.map((r) => r.title).join(" | ")}`);
  return out;
}

function checkLive(c, body) {
  const fails = [];
  const text = body.answer ?? "";
  if ("legal" in c && Boolean(body.flags?.legal) !== c.legal) fails.push(`legal flag ${Boolean(body.flags?.legal)}, expected ${c.legal}`);
  if (c.legal) return fails; // canned text; nothing else to grade
  for (const s of c.include ?? []) if (!has(text, s)) fails.push(`missing "${s}"`);
  for (const group of c.include_any ?? []) if (!group.some((s) => has(text, s))) fails.push(`none of [${group.slice(0, 4)}]`);
  for (const s of c.exclude ?? []) if (has(text, s)) fails.push(`contains "${s}"`);
  for (const r of c.regex_exclude ?? []) if (new RegExp(r, "i").test(text)) fails.push(`matches /${r}/`);
  const links = [...(body.sources ?? []), ...(body.related ?? [])];
  if (c.related_any && !c.related_any.some((s) => links.some((x) => x.url.includes(s)))) fails.push(`no source or related research with [${c.related_any}]`);
  if (c.related_none && (body.related ?? []).length) fails.push(`related research on a non-research question: ${body.related.map((r) => r.title).join(" | ")}`);
  if (["position", "outcome"].includes(c.cat) && !links.length) fails.push("research question answered with no source or research link");
  if (c.source_any && !c.source_any.some((s) => body.sources.some((x) => x.url.includes(s)))) fails.push(`no source url with [${c.source_any}]`);
  fails.push(...voiceProblems(text).map((p) => `voice: ${p}`));
  return fails;
}

let client;
let calls = 0, firstCallCost = null;
if (replayFile) {
  // Answers produced elsewhere (no API): look up by the visitor's question.
  const byQuestion = Object.fromEntries(cases.map((c) => [c.q.replace(/\s+/g, " ").trim(), replayAnswers()[c.id]]));
  client = { messages: { async create(params) {
    const q = params.messages[params.messages.length - 1].content;
    return { stop_reason: "end_turn", usage: {}, content: [{ type: "text", text: byQuestion[q] ?? "" }] };
  } } };
} else if (dry) {
  // Stand-in for the SDK: estimates usage from the real request, and models the 1-hour prompt cache
  // (the first call writes the cached system block, later calls read it).
  let cached = false;
  client = {
    messages: {
      async create(params) {
        const cacheable = Math.round(params.system[0].text.length / 4);
        const rest = Math.round((params.system[1].text.length + params.messages.reduce((n, m) => n + m.content.length, 0)) / 4);
        const usage = { input_tokens: rest, output_tokens: 260, cache_read_input_tokens: cached ? cacheable : 0, cache_creation_input_tokens: cached ? 0 : cacheable };
        cached = true;
        return { stop_reason: "end_turn", usage, content: [{ type: "text", text: "dry run" }] };
      },
    },
  };
} else if (!offline && !dry && !replayFile) {
  const key = process.env.ANTHROPIC_API_KEY ?? (existsSync(`${homedir()}/.anthropic_api_key`) ? readFileSync(`${homedir()}/.anthropic_api_key`, "utf8").trim() : null);
  if (!key) { console.error("No API key. Use --offline, or put a key in ~/.anthropic_api_key."); process.exit(2); }
  // Resolved from worker/node_modules: this folder has no package.json of its own.
  const { default: Anthropic } = await import(new URL("../worker/node_modules/@anthropic-ai/sdk/index.mjs", here));
  client = new Anthropic({ apiKey: key });
}

const results = [];
let tokens = { in: 0, out: 0, cacheRead: 0, cacheWrite: 0 };
const quiet = console.log;
async function run(c) {
  if (offline) {
    if (!("legal" in c) && !c.retrieve_any && !c.related_any && !c.related_none) return { c, fails: [], skipped: true };
    return { c, fails: checkOffline(c) };
  }
  console.log = () => {}; // the handler logs one line per request
  const r = await handleChat({ messages: [{ role: "user", content: c.q }], index, client, env: { MODEL: model } });
  console.log = quiet;
  const u = r.usage ?? {};
  if (r.usage) {
    calls++;
    if (calls === 1) firstCallCost = dollars({ in: u.input_tokens ?? 0, out: u.output_tokens ?? 0, cacheRead: u.cache_read_input_tokens ?? 0, cacheWrite: u.cache_creation_input_tokens ?? 0 });
  }
  tokens.in += u.input_tokens ?? 0; tokens.out += u.output_tokens ?? 0;
  tokens.cacheRead += u.cache_read_input_tokens ?? 0; tokens.cacheWrite += u.cache_creation_input_tokens ?? 0;
  const fails = dry ? [] : r.status === 200 ? checkLive(c, r.body) : [`HTTP ${r.status}`];
  return { c, fails, answer: r.body.answer };
}

const pool = 1; // one at a time: the prompt-cache cold/warm split in the cost line only means something sequentially
const queue = [...cases];
await Promise.all(Array.from({ length: pool }, async () => {
  for (let c; (c = queue.shift()); ) results.push(await run(c));
}));
results.sort((a, b) => cases.indexOf(a.c) - cases.indexOf(b.c));

let failed = 0, skipped = 0;
const byCat = {};
for (const { c, fails, answer, skipped: sk } of results) {
  if (sk) { skipped++; continue; }
  byCat[c.cat] ??= { pass: 0, total: 0 };
  byCat[c.cat].total++;
  if (!fails.length) byCat[c.cat].pass++; else failed++;
  if (fails.length) console.log(`FAIL ${c.id}: ${fails.join("; ")}${answer ? `\n     > ${answer.slice(0, 220).replace(/\n/g, " ")}` : ""}`);
  else if (flag("show")) console.log(`ok   ${c.id}\n     > ${(answer ?? "").slice(0, 300).replace(/\n/g, " ")}`);
}
console.log(dry ? `\nDRY RUN, ESTIMATED (${priced}): ${results.length - skipped} questions priced, nothing graded` : `\n${offline ? "OFFLINE (gate + retrieval)" : replayFile ? `REPLAY of ${replayFile.split("/").pop()}` : `LIVE ${model ?? "default model"}`}: ${results.length - skipped - failed} passed, ${failed} failed${skipped ? `, ${skipped} not applicable offline` : ""}`);
for (const [k, v] of Object.entries(byCat)) console.log(`  ${k.padEnd(11)} ${v.pass}/${v.total}`);
if (!offline && !replayFile) {
  console.log(`tokens: ${tokens.in} in (${tokens.cacheRead} cache-read, ${tokens.cacheWrite} cache-write), ${tokens.out} out`);
  const total = dollars(tokens);
  if (total != null && calls) {
    const warm = calls > 1 ? (total - firstCallCost) / (calls - 1) : total;
    console.log(`cost (${priced}${dry ? ", estimated" : ""}): $${total.toFixed(4)} over ${calls} model calls | first call (cache cold) $${firstCallCost.toFixed(4)} | later calls avg $${warm.toFixed(4)} | per 1,000 questions at warm rate $${(warm * 1000).toFixed(2)}`);
  }
}
process.exit(failed ? 1 : 0);
