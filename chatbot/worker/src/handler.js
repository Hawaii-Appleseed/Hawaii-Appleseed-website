// One chat turn: validate -> legal gate -> retrieve -> model -> clean up. Pure of
// Cloudflare specifics, so the dev server, the tests, and the eval harness all run
// the same code the Worker does. `client` is an Anthropic SDK client (or a fake).
import { isLegalHelpRequest, LEGAL_REPLY, LEGAL_SENTINEL } from "./legal.js";
import { buildExcerpts, buildSystem } from "./prompt.js";
import { queryFor, search } from "./retrieve.js";

export const LIMITS = { turns: 8, userChars: 800, assistantChars: 2400 };
const DEFAULT_MODEL = "claude-sonnet-5-5";

const FRIENDLY = {
  unavailable:
    "The assistant is unavailable right now. Please try again in a little while, or browse hiappleseed.org.",
  declined:
    "I can't answer that one. You can find Hawaiʻi Appleseed's research and positions at hiappleseed.org.",
};

/** Validate the browser's message list: alternating roles, ending on a user turn, bounded size. */
export function cleanMessages(raw) {
  if (!Array.isArray(raw) || raw.length === 0) return null;
  const msgs = [];
  for (const m of raw.slice(-LIMITS.turns)) {
    if (!m || (m.role !== "user" && m.role !== "assistant") || typeof m.content !== "string") return null;
    const text = m.content.replace(/\s+/g, " ").trim();
    const max = m.role === "user" ? LIMITS.userChars : LIMITS.assistantChars;
    if (!text || text.length > max) return null;
    msgs.push({ role: m.role, content: text });
  }
  while (msgs.length && msgs[0].role !== "user") msgs.shift();
  if (!msgs.length || msgs[msgs.length - 1].role !== "user") return null;
  for (let i = 1; i < msgs.length; i++) if (msgs[i].role === msgs[i - 1].role) return null;
  return msgs;
}

/** Resolve [C12] / [2] markers to numbered footnotes that point only at links we built. */
export function finalize(text, core, hits) {
  const byId = new Map(core.map((s) => [s.id, s]));
  const order = [];
  const sources = [];
  const answer = text
    .replace(/https?:\/\/\S+/g, "")
    .replace(/\[(C\d+|\d+)\]/g, (_, id) => {
      const ref = id.startsWith("C") ? byId.get(id) : hits[Number(id) - 1];
      const url = ref?.url ?? ref?.u; // core sections say url/title; retrieved chunks say u/t
      if (!url) return "";
      let n = order.indexOf(url) + 1;
      if (!n) {
        order.push(url);
        n = order.length;
        sources.push({ n, title: ref.title ?? ref.t, url });
      }
      return `[${n}]`;
    })
    .replace(/[ \t]+([.,;:])/g, "$1")
    .replace(/[ \t]{2,}/g, " ")
    .trim();
  return { answer, sources };
}

export async function handleChat({ messages: raw, index, client, env = {} }) {
  const messages = cleanMessages(raw);
  if (!messages) return { status: 400, body: { error: "bad_request" } };
  const last = messages[messages.length - 1].content;

  if (isLegalHelpRequest(last)) {
    return { status: 200, body: { answer: LEGAL_REPLY, sources: [], flags: { legal: true } } };
  }

  const hits = search(index, queryFor(messages));
  let resp;
  try {
    const params = {
      model: env.MODEL || DEFAULT_MODEL,
      max_tokens: 700,
      output_config: { effort: env.EFFORT || "low" },
      system: [
        { type: "text", text: buildSystem(index.core), cache_control: { type: "ephemeral", ttl: "1h" } },
        { type: "text", text: buildExcerpts(hits) },
      ],
      messages,
    };
    // Server-side refusal fallback is opt-in (FALLBACKS=default): it only reroutes cyber and
    // frontier-model declines, which this bot should never produce.
    resp =
      env.FALLBACKS === "default"
        ? await client.beta.messages.create({ ...params, betas: ["server-side-fallback-2026-07-01"], fallbacks: "default" })
        : await client.messages.create(params);
  } catch (err) {
    console.log(JSON.stringify({ event: "upstream_error", status: err?.status ?? null, name: err?.name }));
    return { status: 502, body: { error: "unavailable", answer: FRIENDLY.unavailable, sources: [] } };
  }

  const usage = resp.usage ?? {};
  console.log(JSON.stringify({
    event: "chat", stop: resp.stop_reason, hits: hits.length, in: usage.input_tokens,
    cacheRead: usage.cache_read_input_tokens, cacheWrite: usage.cache_creation_input_tokens, out: usage.output_tokens,
  }));

  if (resp.stop_reason === "refusal") {
    return { status: 200, body: { answer: FRIENDLY.declined, sources: [], flags: { refusal: true } } };
  }
  const text = (resp.content ?? []).filter((b) => b.type === "text").map((b) => b.text).join("\n").trim();
  if (!text) return { status: 502, body: { error: "empty", answer: FRIENDLY.unavailable, sources: [] } };
  if (text.startsWith(LEGAL_SENTINEL) || text.includes(LEGAL_SENTINEL)) {
    return { status: 200, body: { answer: LEGAL_REPLY, sources: [], flags: { legal: true } } };
  }
  const { answer, sources } = finalize(text, index.core, hits);
  return { status: 200, body: { answer, sources, flags: {} }, usage };
}
