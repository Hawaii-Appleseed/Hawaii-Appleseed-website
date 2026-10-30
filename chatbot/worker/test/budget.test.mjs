import assert from "node:assert/strict";
import { test } from "node:test";
import { handleRequest } from "../src/index.js";
import { microDollars } from "../src/pricing.js";

const kvStore = () => {
  const m = new Map();
  return { m, get: async (k) => m.get(k) ?? null, put: async (k, v) => void m.set(k, v) };
};
const call = (env, deps, q = "What is the Budget Primer?") =>
  handleRequest(
    new Request("https://worker.test/chat", {
      method: "POST",
      headers: { origin: "https://hiappleseed.org", "content-type": "application/json", "cf-connecting-ip": "203.0.113.9" },
      body: JSON.stringify({ messages: [{ role: "user", content: q }] }),
    }),
    env,
    deps,
  );
const client = (usage) => ({ messages: { create: async () => ({ stop_reason: "end_turn", usage, content: [{ type: "text", text: "ok" }] }) } });
const day = new Date().toISOString().slice(0, 10);

test("pricing: micro-dollars from usage, per model, with cache read and 1-hour write", () => {
  const u = { input_tokens: 1000, output_tokens: 100, cache_read_input_tokens: 5000, cache_creation_input_tokens: 0 };
  assert.equal(microDollars(u, "claude-sonnet-5-5"), 1000 * 2 + 5000 * 0.2 + 100 * 10); // 4000 micro-dollars = $0.004
  assert.equal(microDollars(u, "claude-haiku-5-5"), 1000 * 0.1 + 5000 * 0.01 + 100 * 0.5);
  assert.equal(microDollars({ cache_creation_input_tokens: 1000 }, "claude-sonnet-5-5"), 1000 * 2 * 2);
  assert.equal(microDollars(u, "some-future-model"), microDollars(u, "claude-sonnet-5-5"));
});

test("budget: spend accumulates from real usage and the day's ceiling stops further calls", async () => {
  const RATE = kvStore();
  const env = { RATE, DAILY_BUDGET_USD: "0.01", PER_MINUTE: "99", PER_DAY: "99", DAILY_CAP: "99", ALLOWED_ORIGINS: "https://hiappleseed.org" };
  const usage = { input_tokens: 1000, output_tokens: 300, cache_read_input_tokens: 6000, cache_creation_input_tokens: 0 }; // about $0.0062 on Sonnet
  const r1 = await call(env, { client: client(usage) });
  assert.equal(r1.status, 200);
  assert.equal(Number(RATE.m.get(`usd:${day}`)), microDollars(usage, "claude-sonnet-5-5"));
  const r2 = await call(env, { client: client(usage) });
  assert.equal(r2.status, 200);
  const r3 = await call(env, { client: { messages: { create: async () => assert.fail("model must not be called over budget") } } });
  assert.equal(r3.status, 429);
  assert.equal((await r3.json()).error, "budget");
});

test("budget: a legal-gate reply costs nothing", async () => {
  const RATE = kvStore();
  const env = { RATE, PER_MINUTE: "99", PER_DAY: "99", DAILY_CAP: "99", ALLOWED_ORIGINS: "https://hiappleseed.org" };
  const r = await call(env, { client: client({}) }, "I need a lawyer");
  assert.equal(r.status, 200);
  assert.equal(RATE.m.get(`usd:${day}`) ?? "0", "0");
});

test("rate limits: per-visitor minute limit trips and answers 429 with a friendly message", async () => {
  const RATE = kvStore();
  const env = { RATE, PER_MINUTE: "2", PER_DAY: "99", DAILY_CAP: "99", ALLOWED_ORIGINS: "https://hiappleseed.org" };
  const c = { client: client({ input_tokens: 10, output_tokens: 10 }) };
  assert.equal((await call(env, c)).status, 200);
  assert.equal((await call(env, c)).status, 200);
  const r = await call(env, c);
  assert.equal(r.status, 429);
  assert.match((await r.json()).answer, /try again/i);
});

test("cors: an origin that is not allowed gets 403, and the visitor is never counted", async () => {
  const RATE = kvStore();
  const r = await handleRequest(
    new Request("https://worker.test/chat", { method: "POST", headers: { origin: "https://evil.example" }, body: "{}" }),
    { RATE, ALLOWED_ORIGINS: "https://hiappleseed.org" },
    { client: client({}) },
  );
  assert.equal(r.status, 403);
  assert.equal(RATE.m.size, 0);
});
