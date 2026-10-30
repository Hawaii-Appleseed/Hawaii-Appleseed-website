// Runs the real Worker bundle in workerd (Cloudflare's runtime) via wrangler, with simulated KV.
// Nothing here calls a model: the legal gate answers before any API request.
//   npm run test:workerd
import assert from "node:assert/strict";
import { after, before, test } from "node:test";
import { unstable_dev } from "wrangler";

let worker;
before(async () => {
  worker = await unstable_dev("src/index.js", {
    config: "wrangler.test.toml",
    local: true,
    persist: false,
    logLevel: "error",
    experimental: { disableExperimentalWarning: true, disableDevRegistry: true },
  });
});
after(async () => { await worker?.stop(); });

const chat = (q, headers = {}) =>
  worker.fetch("/chat", {
    method: "POST",
    headers: { origin: "https://hiappleseed.org", "content-type": "application/json", "cf-connecting-ip": "198.51.100.7", ...headers },
    body: JSON.stringify({ messages: [{ role: "user", content: q }] }),
  });

test("health: the index loads in the Workers runtime", async () => {
  const r = await worker.fetch("/health");
  assert.equal(r.status, 200);
  const j = await r.json();
  assert.ok(j.chunks > 2000, `chunks ${j.chunks}`);
});

test("cors: preflight from the site is allowed, from anywhere else is not", async () => {
  const ok = await worker.fetch("/chat", { method: "OPTIONS", headers: { origin: "https://hiappleseed.org" } });
  assert.equal(ok.status, 204);
  assert.equal(ok.headers.get("access-control-allow-origin"), "https://hiappleseed.org");
  const bad = await worker.fetch("/chat", { method: "OPTIONS", headers: { origin: "https://evil.example" } });
  assert.equal(bad.status, 403);
  assert.equal((await chat("hi", { origin: "https://evil.example" })).status, 403);
});

test("legal: the fixed reply and its referral come back without any model call", async () => {
  const r = await chat("I'm being evicted, can you represent me?");
  assert.equal(r.status, 200);
  const j = await r.json();
  assert.equal(j.flags.legal, true);
  assert.equal(j.sources[0].url, "https://hsba.org/HSBA_2020/Public/Legal_Assistance.aspx");
});

test("rate limit: the fourth request in a minute from one visitor is refused (KV in workerd)", async () => {
  const headers = { "cf-connecting-ip": "198.51.100.99" };
  for (let i = 0; i < 3; i++) assert.equal((await chat("I need a lawyer", headers)).status, 200, `request ${i + 1}`);
  const r = await chat("I need a lawyer", headers);
  assert.equal(r.status, 429);
  assert.equal((await r.json()).error, "rate_limited");
});

test("page: GET / serves the widget with the staff notice and a locked-down CSP", async () => {
  const r = await worker.fetch("/");
  assert.equal(r.status, 200);
  assert.match(r.headers.get("content-security-policy"), /frame-ancestors 'none'/);
  const html = await r.text();
  assert.match(html, /data-endpoint="\/chat"/);
  assert.match(html, /Staff pilot/);
  assert.equal(r.headers.get("cache-control"), "no-store");
});
