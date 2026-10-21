// Cloudflare Worker entry: CORS, abuse controls, then handleChat.
//
// Secrets and vars (wrangler secret put / wrangler.toml):
//   ANTHROPIC_API_KEY   required
//   TURNSTILE_SECRET    when set, every /chat call must carry a valid Turnstile token
//   ALLOWED_ORIGINS     comma-separated; defaults to the production site
//   MODEL, EFFORT       optional model and effort overrides
//   PER_MINUTE, PER_DAY per-visitor limits (KV binding RATE required); DAILY_CAP is the
//                       whole-site daily ceiling that bounds spend
//   FALLBACKS           "default" turns on server-side refusal fallback (off by default)
import Anthropic from "@anthropic-ai/sdk";
import index from "./index.json" with { type: "json" };
import { handleChat } from "./handler.js";

const DEFAULT_ORIGINS = "https://hiappleseed.org,https://www.hiappleseed.org";
const MAX_BODY = 12_000;

const json = (body, status, extra = {}) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json", ...extra } });

function corsHeaders(request, env) {
  const origin = request.headers.get("origin");
  const allowed = (env.ALLOWED_ORIGINS || DEFAULT_ORIGINS).split(",").map((s) => s.trim());
  if (!origin || !allowed.includes(origin)) return null;
  return { "access-control-allow-origin": origin, vary: "origin", "access-control-allow-headers": "content-type", "access-control-allow-methods": "POST, GET, OPTIONS" };
}

async function sha(text) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(buf)].slice(0, 8).map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function verifyTurnstile(token, ip, env) {
  if (!token) return false;
  const form = new FormData();
  form.append("secret", env.TURNSTILE_SECRET);
  form.append("response", token);
  if (ip) form.append("remoteip", ip);
  const r = await fetch("https://challenges.cloudflare.com/turnstile/v0/siteverify", { method: "POST", body: form });
  return Boolean((await r.json()).success);
}

/** Count a hit in KV; returns true when the visitor is over `limit`. Approximate by design
 *  (KV is eventually consistent); a Cloudflare rate-limiting rule is the hard backstop. */
async function overLimit(kv, key, limit, ttl) {
  const n = Number((await kv.get(key)) ?? 0) + 1;
  await kv.put(key, String(n), { expirationTtl: ttl });
  return n > limit;
}

export async function handleRequest(request, env, deps = {}) {
  const url = new URL(request.url);
  const cors = corsHeaders(request, env);
  if (request.method === "OPTIONS") return new Response(null, { status: cors ? 204 : 403, headers: cors ?? {} });
  if (url.pathname === "/health") return json({ ok: true, built: index.built, public: index.public, chunks: index.chunks.length }, 200);
  if (url.pathname !== "/chat" || request.method !== "POST") return json({ error: "not_found" }, 404);
  if (!cors) return json({ error: "forbidden" }, 403);

  if (Number(request.headers.get("content-length") ?? 0) > MAX_BODY) return json({ error: "too_large" }, 413, cors);
  let payload;
  try {
    payload = await request.json();
  } catch {
    return json({ error: "bad_request" }, 400, cors);
  }

  const ip = request.headers.get("cf-connecting-ip") ?? "";
  if (env.TURNSTILE_SECRET && !(await verifyTurnstile(payload.turnstileToken, ip, env))) {
    return json({ error: "verification_failed", answer: "Please reload the page and try again." }, 403, cors);
  }
  if (env.RATE) {
    const day = new Date().toISOString().slice(0, 10);
    const who = await sha(`${ip}|${env.RATE_SALT ?? "ha"}`);
    const tooMany =
      (await overLimit(env.RATE, `m:${who}:${Math.floor(Date.now() / 60000)}`, Number(env.PER_MINUTE ?? 8), 120)) ||
      (await overLimit(env.RATE, `d:${who}:${day}`, Number(env.PER_DAY ?? 60), 90000)) ||
      (await overLimit(env.RATE, `all:${day}`, Number(env.DAILY_CAP ?? 2000), 90000));
    if (tooMany) {
      return json({ error: "rate_limited", answer: "That's a lot of questions at once. Please try again a little later, or browse hiappleseed.org." }, 429, cors);
    }
  }

  const client = deps.client ?? new Anthropic({ apiKey: env.ANTHROPIC_API_KEY });
  const { status, body } = await handleChat({ messages: payload.messages, index, client, env });
  return json(body, status, cors);
}

export default { fetch: (request, env) => handleRequest(request, env) };
