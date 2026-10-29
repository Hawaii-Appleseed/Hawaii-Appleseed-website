import assert from "node:assert/strict";
import { test } from "node:test";
import { handleRequest } from "../src/index.js";

const kv = () => { const m = new Map(); return { m, get: async (k) => m.get(k) ?? null, put: async (k, v) => void m.set(k, v) }; };
const base = { FEEDBACK: "1", MODEL: "claude-haiku-5-5", PER_MINUTE: "99", PER_DAY: "99", DAILY_CAP: "99" };
const post = (env, body, headers = {}) =>
  handleRequest(new Request("https://ha-ask.example.workers.dev/feedback", {
    method: "POST", headers: { origin: "https://ha-ask.example.workers.dev", "content-type": "application/json", "cf-connecting-ip": "203.0.113.7", ...headers },
    body: typeof body === "string" ? body : JSON.stringify(body),
  }), env, {});
const good = { rating: "down", comment: "It said the bill passed, but it did not.", question: "Did HB1850 pass?", answer: "Yes it passed [1].", sources: ["https://hiappleseed.org/taxes-budget"] };

test("feedback: a rating is saved with the question, answer, comment, model and a 90-day expiry", async () => {
  const RATE = kv(); const puts = [];
  const env = { ...base, RATE: { ...RATE, put: async (k, v, o) => { puts.push(o); return RATE.put(k, v); } } };
  const r = await post(env, good);
  assert.equal(r.status, 200);
  const [key] = [...RATE.m.keys()].filter((k) => k.startsWith("fb:"));
  const e = JSON.parse(RATE.m.get(key));
  assert.deepEqual({ rating: e.rating, question: e.question, answer: e.answer, comment: e.comment, model: e.model, email: e.email }, { rating: "down", question: good.question, answer: good.answer, comment: good.comment, model: "claude-haiku-5-5", email: null });
  assert.deepEqual(e.sources, good.sources);
  assert.ok(puts.some((o) => o?.expirationTtl === 90 * 24 * 3600));
  assert.match(key, /^fb:\d{4}-\d\d-\d\dT/);
});

test("feedback: off unless FEEDBACK=1 and a KV store exists; bad input and bad origins are refused", async () => {
  assert.equal((await post({ ...base, FEEDBACK: "0", RATE: kv() }, good)).status, 404);
  assert.equal((await post({ ...base }, good)).status, 404);
  const env = { ...base, RATE: kv() };
  assert.equal((await post(env, "not json")).status, 400);
  assert.equal((await post(env, { ...good, rating: "meh" })).status, 400);
  assert.equal((await post(env, { ...good, question: "" })).status, 400);
  assert.equal((await post(env, good, { origin: "https://evil.example" })).status, 403);
  assert.equal([...env.RATE.m.keys()].filter((k) => k.startsWith("fb:")).length, 0);
});

test("feedback: long text is clipped, and a person is limited to FEEDBACK_PER_DAY ratings a day", async () => {
  const env = { ...base, RATE: kv(), FEEDBACK_PER_DAY: "2" };
  assert.equal((await post(env, { ...good, comment: "x".repeat(5000), answer: "y".repeat(9000) })).status, 200);
  const e = JSON.parse(env.RATE.m.get([...env.RATE.m.keys()].find((k) => k.startsWith("fb:"))));
  assert.equal(e.comment.length, 500);
  assert.equal(e.answer.length, 2400);
  assert.equal((await post(env, good)).status, 200);
  assert.equal((await post(env, good)).status, 429);
});

const listable = () => {
  const s = kv();
  s.list = async ({ prefix }) => ({ keys: [...s.m.keys()].filter((k) => k.startsWith(prefix)).sort().map((name) => ({ name })), list_complete: true });
  return s;
};
const getFlags = (env, path = "/flags.json") => handleRequest(new Request(`https://ha-ask.example.workers.dev${path}`), env, {});

test("flags: a flag keeps the earlier conversation, and /flags lists only flagged answers, newest first", async () => {
  const env = { ...base, RATE: listable() };
  const context = [{ role: "user", content: "What is the conveyance tax?" }, { role: "assistant", content: "A tax on property sales [1]." }, { role: "system", content: "drop me" }];
  assert.equal((await post(env, { ...good, question: "Tell me more about that.", context })).status, 200);
  assert.equal((await post(env, { ...good, rating: "up", question: "Who runs Appleseed?" })).status, 200);
  await new Promise((r) => setTimeout(r, 5));
  assert.equal((await post(env, { ...good, question: "Second flag" })).status, 200);
  const { flags } = await (await getFlags(env)).json();
  assert.deepEqual(flags.map((f) => f.question), ["Second flag", "Tell me more about that."]);
  assert.deepEqual(flags[1].context.map((m) => m.role), ["user", "assistant"]);
  const page = await (await getFlags(env, "/flags")).text();
  assert.match(page, /Flagged answers/);
  assert.match(page, /It said the bill passed/);
  assert.match(page, /What is the conveyance tax\?/);
  assert.doesNotMatch(page, /Who runs Appleseed/);
});

test("flags: REVIEWERS limits who may read them, and the page escapes what staff typed", async () => {
  const env = { ...base, RATE: listable(), REVIEWERS: "lead@example.org" };
  await post(env, { ...good, comment: "<script>alert(1)</script>" });
  assert.equal((await getFlags(env)).status, 403); // the gate is off in tests, so there is no email
  const open = { ...env, REVIEWERS: "" };
  const page = await (await getFlags(open, "/flags")).text();
  assert.doesNotMatch(page, /<script>alert/);
  assert.match(page, /&lt;script&gt;/);
  assert.equal((await getFlags({ ...base, FEEDBACK: "0", RATE: listable() })).status, 404);
});
