// Cloudflare Access gate for the internal pilot: the Worker checks the Access token itself and fails closed.
//
// Why not trust "it sits behind Access": a Worker is also reachable on other hostnames (workers.dev, preview URLs)
// that the Access application may not cover, and there the identity headers are whatever the caller typed. The staff
// hub learned this the hard way (staff-updates-internal README, "Verifying the gate from inside": a per-deployment
// URL outside the Access app handed over its contact store to an unauthenticated curl). So every route here requires
// a Cf-Access-Jwt-Assertion whose signature, issuer, expiry and audience check out against the team's published keys.
//
// Derived from staff-updates-internal/assets/access.js (same team, same checks), with one change of stance: that
// module stays open when nothing is configured; this one stays CLOSED.
//
//   REQUIRE_ACCESS="1"     turn the gate on (wrangler.toml)
//   ACCESS_TEAM_DOMAIN     the Zero Trust team: `lively-wildflower-989d` or the full `.cloudflareaccess.com` host
//   ACCESS_AUD             the Access application's Audience tag (Zero Trust > Access > Applications > this app).
//                          Required: a token minted for a different application on the team is refused.
//
// With REQUIRE_ACCESS on and either value missing, every request gets a 503 and nothing else runs.

const CERTS_TTL_MS = 60 * 60 * 1000;
const dec = new TextDecoder();
const enc = new TextEncoder();

/** `https://<team>.cloudflareaccess.com`, or null when not configured. */
export function teamIssuer(env) {
  const raw = env?.ACCESS_TEAM_DOMAIN ? String(env.ACCESS_TEAM_DOMAIN).trim() : "";
  if (!raw) return null;
  const host = raw.replace(/^https?:\/\//i, "").replace(/\/.*$/, "").toLowerCase();
  if (!/^[a-z0-9.-]+$/.test(host)) return null;
  return `https://${host.includes(".") ? host : host + ".cloudflareaccess.com"}`;
}

export function allowedAud(env) {
  return String(env?.ACCESS_AUD ?? "").split(",").map((s) => s.trim().toLowerCase()).filter(Boolean);
}

function unb64url(s) {
  const pad = s.length % 4 ? "=".repeat(4 - (s.length % 4)) : "";
  return Uint8Array.from(atob(String(s).replace(/-/g, "+").replace(/_/g, "/") + pad), (c) => c.charCodeAt(0));
}

function decodeJwt(token) {
  if (typeof token !== "string") return null;
  const parts = token.split(".");
  if (parts.length !== 3) return null;
  try {
    const header = JSON.parse(dec.decode(unb64url(parts[0])));
    const payload = JSON.parse(dec.decode(unb64url(parts[1])));
    if (!header || typeof header !== "object" || !payload || typeof payload !== "object") return null;
    return { header, payload, signingInput: `${parts[0]}.${parts[1]}`, signature: unb64url(parts[2]) };
  } catch {
    return null;
  }
}

// The team's signing keys, per isolate, for an hour. Cloudflare rotates them about every six weeks and publishes the
// next key ahead of time, so an unknown `kid` is answered by one refetch, not a refusal.
const cache = new Map(); // issuer -> { at, keys }
async function certs(issuer, f, force) {
  const have = cache.get(issuer);
  if (!force && have && Date.now() - have.at < CERTS_TTL_MS) return have.keys;
  try {
    const r = await f(`${issuer}/cdn-cgi/access/certs`, { headers: { accept: "application/json" } });
    if (!r.ok) throw new Error(`certs ${r.status}`);
    const body = await r.json();
    const keys = Array.isArray(body?.keys) ? body.keys.filter((k) => k?.kty === "RSA" && k.kid && k.n && k.e) : [];
    cache.set(issuer, { at: Date.now(), keys });
    return keys;
  } catch {
    return have ? have.keys : []; // stale keys beat none: a blip at Cloudflare must not lock staff out
  }
}

export function clearCertCache() {
  cache.clear();
}

async function verifyRs256(jwk, signingInput, signature) {
  const key = await crypto.subtle.importKey(
    "jwk", { kty: "RSA", n: jwk.n, e: jwk.e, alg: "RS256", ext: true },
    { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["verify"]);
  return crypto.subtle.verify("RSASSA-PKCS1-v1_5", key, signature, enc.encode(signingInput));
}

/** The token's claims when signed by this team, unexpired, and minted for one of our audiences; else null. */
export async function verifyAccessJwt(token, env, opts = {}) {
  const issuer = teamIssuer(env);
  const want = allowedAud(env);
  if (!issuer || !want.length) return null;
  const f = opts.fetch ?? fetch;
  const now = typeof opts.now === "number" ? opts.now : Math.floor(Date.now() / 1000);
  const t = decodeJwt(token);
  if (!t || t.header.alg !== "RS256" || typeof t.header.kid !== "string") return null;

  let jwk = (await certs(issuer, f, false)).find((k) => k.kid === t.header.kid);
  if (!jwk) jwk = (await certs(issuer, f, true)).find((k) => k.kid === t.header.kid);
  if (!jwk) return null;

  let ok = false;
  try { ok = await verifyRs256(jwk, t.signingInput, t.signature); } catch { ok = false; }
  if (!ok) return null;

  const p = t.payload;
  if (p.iss !== issuer) return null;
  if (typeof p.exp !== "number" || p.exp <= now) return null;
  if (typeof p.nbf === "number" && p.nbf > now + 60) return null;
  const have = (Array.isArray(p.aud) ? p.aud : [p.aud]).map((a) => String(a ?? "").toLowerCase());
  return have.some((a) => want.includes(a)) ? p : null;
}

/**
 * The gate. Returns { ok: true, email } to carry on (email is null when the gate is off), or
 * { ok: false, status, error } to answer with. Off unless REQUIRE_ACCESS is "1".
 */
export async function gate(request, env, opts = {}) {
  if (env?.REQUIRE_ACCESS !== "1") return { ok: true, email: null };
  if (!teamIssuer(env) || !allowedAud(env).length) return { ok: false, status: 503, error: "access_not_configured" };
  const claims = await verifyAccessJwt(request.headers.get("cf-access-jwt-assertion"), env, opts);
  if (!claims) return { ok: false, status: 401, error: "access_required" };
  const email = typeof claims.email === "string" && claims.email ? claims.email.toLowerCase() : null;
  if (!email) return { ok: false, status: 403, error: "person_required" }; // service tokens have no email; the pilot is for people
  return { ok: true, email };
}
