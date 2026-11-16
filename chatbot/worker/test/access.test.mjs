import assert from "node:assert/strict";
import { beforeEach, test } from "node:test";
import { clearCertCache, gate, verifyAccessJwt } from "../src/access.js";
import { handleRequest } from "../src/index.js";

const TEAM = "test-team";
const ISS = `https://${TEAM}.cloudflareaccess.com`;
const AUD = "aud-tag-123";
const env = { REQUIRE_ACCESS: "1", ACCESS_TEAM_DOMAIN: TEAM, ACCESS_AUD: AUD };
const NOW = 1_800_000_000;

const b64 = (b) => Buffer.from(b).toString("base64url");
const keypair = await crypto.subtle.generateKey({ name: "RSASSA-PKCS1-v1_5", modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: "SHA-256" }, true, ["sign", "verify"]);
const jwk = { ...(await crypto.subtle.exportKey("jwk", keypair.publicKey)), kid: "k1" };
const other = await crypto.subtle.generateKey({ name: "RSASSA-PKCS1-v1_5", modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: "SHA-256" }, true, ["sign", "verify"]);

async function token(claims = {}, { header = {}, key = keypair.privateKey } = {}) {
  const h = b64(JSON.stringify({ alg: "RS256", kid: "k1", typ: "JWT", ...header }));
  const p = b64(JSON.stringify({ iss: ISS, aud: [AUD], exp: NOW + 600, email: "Staff@HiAppleseed.org", ...claims }));
  const sig = await crypto.subtle.sign("RSASSA-PKCS1-v1_5", key, new TextEncoder().encode(`${h}.${p}`));
  return `${h}.${p}.${b64(sig)}`;
}
let fetches = 0;
const opts = { now: NOW, fetch: async () => { fetches++; return { ok: true, json: async () => ({ keys: [jwk] }) }; } };
beforeEach(() => { clearCertCache(); fetches = 0; });

test("access: a token signed by the team, unexpired, for our audience is accepted", async () => {
  const p = await verifyAccessJwt(await token(), env, opts);
  assert.equal(p.email, "Staff@HiAppleseed.org");
});

test("access: refused when the audience, issuer, expiry, not-before, algorithm, or signature is wrong", async () => {
  const bad = {
    "wrong audience": await token({ aud: ["someone-elses-app"] }),
    "wrong issuer": await token({ iss: "https://evil.cloudflareaccess.com" }),
    expired: await token({ exp: NOW - 1 }),
    "not yet valid": await token({ nbf: NOW + 3600 }),
    "alg none": await token({}, { header: { alg: "none" } }),
    "alg HS256": await token({}, { header: { alg: "HS256" } }),
    "signed by another key": await token({}, { key: other.privateKey }),
    "unknown kid": await token({}, { header: { kid: "nope" } }),
    garbage: "not.a.jwt",
  };
  for (const [name, t] of Object.entries(bad)) assert.equal(await verifyAccessJwt(t, env, opts), null, name);
  assert.equal(await verifyAccessJwt(null, env, opts), null);
  // a payload edited after signing fails the signature check
  const [h, , s] = (await token()).split(".");
  const forged = `${h}.${b64(JSON.stringify({ iss: ISS, aud: [AUD], exp: NOW + 600, email: "boss@hiappleseed.org" }))}.${s}`;
  assert.equal(await verifyAccessJwt(forged, env, opts), null);
});

test("access: keys are cached, and an unknown kid costs exactly one refetch", async () => {
  await verifyAccessJwt(await token(), env, opts);
  await verifyAccessJwt(await token(), env, opts);
  assert.equal(fetches, 1);
  await verifyAccessJwt(await token({}, { header: { kid: "rotated" } }), env, opts);
  assert.equal(fetches, 2);
});

test("gate: off unless REQUIRE_ACCESS=1; on but unconfigured is a 503; no or bad token is a 401", async () => {
  const req = (t) => new Request("https://w.test/", { headers: t ? { "cf-access-jwt-assertion": t } : {} });
  assert.deepEqual(await gate(req(), {}), { ok: true, email: null });
  for (const partial of [{ REQUIRE_ACCESS: "1" }, { REQUIRE_ACCESS: "1", ACCESS_TEAM_DOMAIN: TEAM }, { REQUIRE_ACCESS: "1", ACCESS_AUD: AUD }]) {
    assert.deepEqual(await gate(req(await token()), partial, opts), { ok: false, status: 503, error: "access_not_configured" });
  }
  assert.equal((await gate(req(), env, opts)).status, 401);
  assert.equal((await gate(req("junk"), env, opts)).status, 401);
  const g = await gate(req(await token()), env, opts);
  assert.deepEqual(g, { ok: true, email: "staff@hiappleseed.org" });
});

test("gate: a service token (no email) is refused; the pilot is for people", async () => {
  const req = new Request("https://w.test/", { headers: { "cf-access-jwt-assertion": await token({ email: undefined, common_name: "svc" }) } });
  assert.equal((await gate(req, env, opts)).status, 403);
});

const kv = () => { const m = new Map(); return { m, get: async (k) => m.get(k) ?? null, put: async (k, v) => void m.set(k, v) }; };
const ok = { stop_reason: "end_turn", usage: {}, content: [{ type: "text", text: "ok" }] };
const model = { messages: { create: async () => ok } };
const call = async (path, { method = "GET", t, origin, body } = {}, e = env) =>
  handleRequest(new Request(`https://ha-ask.example.workers.dev${path}`, {
    method,
    headers: { ...(t ? { "cf-access-jwt-assertion": t } : {}), ...(origin ? { origin } : {}), "content-type": "application/json", "cf-connecting-ip": "203.0.113.5" },
    body: body && JSON.stringify(body),
  }), e, { client: model, access: opts });

test("worker: unconfigured Access fails closed on every route and never reaches the model", async () => {
  const locked = { REQUIRE_ACCESS: "1" };
  const t = await token();
  for (const [path, method] of [["/", "GET"], ["/health", "GET"], ["/chat", "POST"], ["/favicon.ico", "GET"]]) {
    const r = await handleRequest(new Request(`https://x.test${path}`, { method, headers: { "cf-access-jwt-assertion": t }, body: method === "POST" ? "{}" : undefined }), locked, { client: { messages: { create: async () => assert.fail("model must not run") } }, access: opts });
    assert.equal(r.status, 503, path);
    assert.equal((await r.json()).error, "access_not_configured");
  }
});

test("worker: with a valid token GET / serves the widget with a locked-down CSP, and /chat works same-origin", async () => {
  const t = await token();
  const page = await call("/", { t });
  assert.equal(page.status, 200);
  const html = await page.text();
  assert.match(html, /id="ha-ask"/);
  assert.match(html, /data-endpoint="\/chat"/);
  assert.match(html, /Staff pilot/);
  assert.match(page.headers.get("content-security-policy"), /frame-ancestors 'none'/);
  assert.match(page.headers.get("content-security-policy"), /connect-src 'self'/);
  assert.equal(page.headers.get("cache-control"), "no-store");
  const r = await call("/chat", { method: "POST", t, origin: "https://ha-ask.example.workers.dev", body: { messages: [{ role: "user", content: "What is the Budget Primer?" }] } });
  assert.equal(r.status, 200);
  assert.equal((await r.json()).answer, "ok");
  // another site cannot call it from a browser even with a token in hand
  const x = await call("/chat", { method: "POST", t, origin: "https://evil.example", body: { messages: [{ role: "user", content: "hi" }] } });
  assert.equal(x.status, 403);
});

test("worker: no token, no service: 401 without any CORS headers or detail", async () => {
  const r = await call("/chat", { method: "POST", origin: "https://ha-ask.example.workers.dev", body: { messages: [{ role: "user", content: "hi" }] } });
  assert.equal(r.status, 401);
  assert.equal(r.headers.get("access-control-allow-origin"), null);
  assert.deepEqual(await r.json(), { error: "access_required" });
});

test("worker: rate limits count per signed-in person, not per shared office IP", async () => {
  const RATE = kv();
  const e = { ...env, RATE, PER_MINUTE: "1", PER_DAY: "99", DAILY_CAP: "99" };
  const q = { method: "POST", origin: "https://ha-ask.example.workers.dev", body: { messages: [{ role: "user", content: "What is the Budget Primer?" }] } };
  const a = await token({ email: "a@hiappleseed.org" });
  const b = await token({ email: "b@hiappleseed.org" });
  assert.equal((await call("/chat", { ...q, t: a }, e)).status, 200);
  assert.equal((await call("/chat", { ...q, t: a }, e)).status, 429); // same person, same IP
  assert.equal((await call("/chat", { ...q, t: b }, e)).status, 200); // a colleague on the same IP is not penalized
});
