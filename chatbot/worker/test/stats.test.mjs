import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { handleRequest } from "../src/index.js";
import { CHART_SAMPLE_PER_DAY, chartsPage, emptyDay, readCharts, readDays, record, statsPage, summarize, tally } from "../src/stats.js";

const index = JSON.parse(readFileSync(new URL("../src/index.json", import.meta.url), "utf8"));
const kvStore = () => {
  const m = new Map();
  return { m, get: async (k) => m.get(k) ?? null, put: async (k, v) => void m.set(k, v) };
};
const day = new Date().toISOString().slice(0, 10);
const says = (text, usage = { input_tokens: 1000, output_tokens: 100 }) => ({ messages: { create: async () => ({ stop_reason: "end_turn", usage, content: [{ type: "text", text }] }) } });
const call = (env, deps, q, ip = "203.0.113.9") =>
  handleRequest(new Request("https://worker.test/chat", {
    method: "POST",
    headers: { origin: "https://hiappleseed.org", "content-type": "application/json", "cf-connecting-ip": ip },
    body: JSON.stringify({ messages: [{ role: "user", content: q }] }),
  }), env, deps);
const envFor = (RATE, extra = {}) => ({ RATE, PER_MINUTE: "99", PER_DAY: "99", DAILY_CAP: "99", ALLOWED_ORIGINS: "https://hiappleseed.org", MODEL: "claude-haiku-5-5", ...extra });
const today = (RATE) => JSON.parse(RATE.m.get(`stats:${day}`));

test("stats: tally counts routes, ids, charts, hand-offs, spend, ratings and turned-away requests", () => {
  let d = emptyDay();
  d = tally(d, { route: "canned", id: "mission", newPerson: true });
  d = tally(d, { route: "stance_position", position: "Capital gains tax", graphics: ["capital-gains-rates"] });
  d = tally(d, { route: "stance_defer", handoff: "deferral" });
  d = tally(d, { route: "model", cited: 2, related: 0, drawn: "rejected:mixed_units", handoff: null, usage: { input_tokens: 1000, output_tokens: 100 }, model: "claude-haiku-5-5" });
  d = tally(d, { route: "model", cited: 0, related: 1, drawn: "accepted", handoff: "marker", usage: { input_tokens: 1000, output_tokens: 100 }, model: "claude-haiku-5-5" });
  d = tally(d, { blocked: "rate_limited" });
  d = tally(d, { feedback: "down" });
  d = tally(d, { feedback: "sideways" });
  assert.equal(d.n, 5);
  assert.equal(d.people, 1);
  assert.deepEqual(d.route, { canned: 1, stance_position: 1, stance_defer: 1, model: 2 });
  assert.deepEqual([d.canned.mission, d.position["Capital gains tax"], d.graphics["capital-gains-rates"]], [1, 1, 1]);
  assert.deepEqual(d.drawn, { "rejected:mixed_units": 1, accepted: 1 });
  assert.deepEqual(d.handoff, { deferral: 1, marker: 1 });
  assert.equal(d.model.answers, 2);
  assert.equal(d.model.uncited, 1);
  assert.equal(d.model.microUsd, 2 * Math.round(1000 * 0.1 + 100 * 0.5));
  assert.deepEqual([d.blocked.rate_limited, d.feedback.up, d.feedback.down], [1, 0, 1]);
  const s = summarize([d]);
  assert.equal(s.readyMade, 3);
  assert.equal(s.drawnAccepted, 1);
  assert.equal(s.drawnRejected, 1);
  assert.equal(s.handoff, 2);
});

test("stats: saved per day in KV, read back newest first, and a broken store never breaks an answer", async () => {
  const RATE = kvStore();
  const now = new Date("2026-10-21T12:00:00Z");
  await record(RATE, { route: "canned", id: "mission" }, now);
  await record(RATE, { route: "canned", id: "mission" }, now);
  await record(RATE, { route: "legal" }, new Date("2026-10-20T12:00:00Z"));
  const days = await readDays(RATE, 3, now);
  assert.deepEqual(days.map((d) => [d.date, d.n]), [["2026-10-21", 2], ["2026-10-20", 1], ["2026-10-19", 0]]);
  RATE.m.set("stats:2026-10-19", "{not json");
  assert.equal((await readDays(RATE, 3, now))[2].n, 0, "a corrupt day reads as empty");
  await record({ get: async () => { throw new Error("kv down"); }, put: async () => { throw new Error("kv down"); } }, { route: "canned" });
  await record(undefined, { route: "canned" });
});

test("stats: every route through the Worker is counted, and nothing about the visitor or their words is kept", async () => {
  const RATE = kvStore();
  const env = envFor(RATE);
  const secret = "zyxwv-unique-question-words";
  await call(env, { client: says("x") }, "What is your mission?");                        // ready-made
  await call(env, { client: says("x") }, "What is your stance on the conveyance tax?");   // stated position
  await call(env, { client: says("x") }, "What is your position on cryptocurrency?");     // deferral
  await call(env, { client: says("x") }, "I need a lawyer for my eviction");              // legal
  await call(env, { client: says(`I don't have that information. [C1]\n[[staff]]`) }, `Is ${secret} open on Saturdays`);
  await call(env, { client: says(`Fine. [C1]\n[[chart: {"type":"bars","title":"T","rows":[]}]]`) }, "How does the budget compare with other budgets?");
  const d = today(RATE);
  assert.equal(d.n, 6);
  assert.equal(d.route.canned, 1);
  assert.equal(d.route.stance_position, 1);
  assert.equal(d.route.stance_defer, 1);
  assert.equal(d.route.legal, 1);
  assert.equal(d.route.model, 2);
  assert.equal(d.handoff.deferral, 1);
  assert.equal(d.handoff.marker, 1);
  assert.equal(d.drawn["rejected:rows"], 1, "a refused chart is counted with its reason");
  assert.ok(d.model.microUsd > 0);
  const raw = RATE.m.get(`stats:${day}`);
  for (const leak of [secret, "203.0.113.9", "@", "lawyer", "eviction", "cryptocurrency", "Saturdays"]) assert.ok(!raw.includes(leak), `the roll-up must not contain ${leak}`);
});

test("stats: people are counted once a day per person, and turned-away requests are counted too", async () => {
  const RATE = kvStore();
  const env = envFor(RATE, { PER_MINUTE: "2" });
  await call(env, { client: says("x") }, "What is your mission?", "203.0.113.1");
  await call(env, { client: says("x") }, "What is your mission?", "203.0.113.1");
  await call(env, { client: says("x") }, "What is your mission?", "203.0.113.2");
  const third = await call(env, { client: says("x") }, "What is your mission?", "203.0.113.1");
  assert.equal(third.status, 429);
  const d = today(RATE);
  assert.equal(d.people, 2);
  assert.equal(d.n, 3);
  assert.equal(d.blocked.rate_limited, 1);
});

test("stats: feedback ratings are counted without their text", async () => {
  const RATE = kvStore();
  const env = envFor(RATE, { FEEDBACK: "1" });
  const r = await handleRequest(new Request("https://worker.test/feedback", {
    method: "POST",
    headers: { origin: "https://hiappleseed.org", "content-type": "application/json", "cf-connecting-ip": "203.0.113.5" },
    body: JSON.stringify({ rating: "down", comment: "secret comment words", question: "a question", answer: "an answer" }),
  }), env);
  assert.equal(r.status, 200);
  const raw = RATE.m.get(`stats:${day}`);
  assert.equal(JSON.parse(raw).feedback.down, 1);
  assert.ok(!raw.includes("secret comment words") && !raw.includes("a question"));
});

test("stats: the page and its data are served, escaped, behind the same gate, and 404 without a store", async () => {
  const RATE = kvStore();
  const env = envFor(RATE);
  await call(env, { client: says("x") }, "What is your mission?");
  const page = await handleRequest(new Request("https://worker.test/stats"), env);
  assert.equal(page.status, 200);
  assert.match(page.headers.get("content-type"), /text\/html/);
  const html = await page.text();
  assert.match(html, /Usage, last 14 days/);
  assert.match(html, /mission/);
  assert.doesNotMatch(html, /<script/i);
  const data = await (await handleRequest(new Request("https://worker.test/stats.json?days=3"), env)).json();
  assert.equal(data.days.length, 3);
  assert.equal(data.days[0].n, 1);
  assert.equal((await handleRequest(new Request("https://worker.test/stats"), { ...env, RATE: undefined })).status, 404);
  const locked = await handleRequest(new Request("https://worker.test/stats"), { ...env, REQUIRE_ACCESS: "1" });
  assert.equal(locked.status, 503, "the gate answers first: not configured means closed");
  const evil = statsPage([{ date: "2026-10-21", ...emptyDay(), n: 1, position: { "<img src=x onerror=alert(1)>": 3 } }]);
  assert.ok(!evil.includes("<img src=x"));
  assert.match(evil, /&lt;img src=x/);
});

test("stats: the first accepted charts of a day are kept for a person to read, with no visitor text, and shown on /stats/charts", async () => {
  const RATE = kvStore();
  const env = envFor(RATE);
  const conv = index.core.find((c) => c.title === "Conveyance tax modernization").id;
  const chart = JSON.stringify({ type: "bars", title: "Prison budget and Hawaiian Home Lands", unit: "annual budget, in millions of dollars", rows: [
    { label: "Prison budget", value: 300, display: "$300 million", quote: "a $300 million prison budget", ref: conv },
    { label: "Hawaiian Home Lands (DHHL)", value: 185, display: "$185 million", quote: "$185 million for DHHL", ref: conv }] });
  const secret = "qqzz-visitor-words-about-prisons";
  const r = await call(env, { client: says(`Prisons cost more. [${conv}]\n[[chart: ${chart}]]`) }, `${secret} How does it compare?`);
  assert.equal(r.status, 200);
  assert.equal((await r.json()).graphics[0].generated, true);
  const sample = JSON.parse(RATE.m.get(`chart:${day}:1`));
  assert.equal(sample.title, "Prison budget and Hawaiian Home Lands");
  assert.equal(sample.rows[0].quote, "a $300 million prison budget");
  assert.ok(!JSON.stringify(sample).includes(secret) && !JSON.stringify(sample).includes("203.0.113.9"));
  const page = await (await handleRequest(new Request("https://worker.test/stats/charts"), env)).text();
  assert.match(page, /Prison budget and Hawaiian Home Lands/);
  assert.match(page, /\$185 million for DHHL/);
  const data = await (await handleRequest(new Request("https://worker.test/stats/charts.json"), env)).json();
  assert.equal(data.charts.length, 1);
  assert.equal((await handleRequest(new Request("https://worker.test/stats/charts"), { ...env, RATE: undefined })).status, 404);
  assert.equal((await handleRequest(new Request("https://worker.test/stats/charts"), { ...env, REQUIRE_ACCESS: "1" })).status, 503, "behind the same gate");
});

test("stats: no more than the day's quota of charts is kept, and a refused or unused chart is never kept", async () => {
  const RATE = kvStore();
  const ev = (drawn) => ({ route: "model", cited: 1, related: 1, drawn, chart: { title: "T", type: "bars", unit: "u", rows: [{ label: "a", display: "1", quote: "q" }], sources: [] } });
  for (let i = 0; i < CHART_SAMPLE_PER_DAY + 5; i++) await record(RATE, ev("accepted"));
  await record(RATE, ev("rejected:mixed_units"));
  await record(RATE, ev("unused"));
  const kept = [...RATE.m.keys()].filter((k) => k.startsWith("chart:"));
  assert.equal(kept.length, CHART_SAMPLE_PER_DAY);
  assert.equal((await readCharts(RATE, 3)).length, CHART_SAMPLE_PER_DAY);
  assert.ok(!chartsPage([{ date: "2026-10-21", type: "bars", title: "<img src=x onerror=alert(1)>", rows: [{ label: "<b>", display: "1", quote: "q" }], sources: [] }]).includes("<img src=x"));
});
