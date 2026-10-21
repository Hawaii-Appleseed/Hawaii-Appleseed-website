// One chat turn: validate -> legal gate -> retrieve -> model -> clean up. Pure of
// Cloudflare specifics, so the dev server, the tests, and the eval harness all run
// the same code the Worker does. `client` is an Anthropic SDK client (or a fake).
import { matchCanned } from "./canned.js";
import { resolveStance } from "./stance.js";
import { resolver, takeChart } from "./charts.js";
import { pickGraphics, takeMarkers } from "./graphics.js";
import { handoffCause, handoffFor, takeStaffMarker } from "./handoff.js";
import { isLegalHelpRequest, LEGAL_REPLY, LEGAL_SENTINEL, LEGAL_SOURCES } from "./legal.js";
import { buildExcerpts, buildSystem } from "./prompt.js";
import { suggestResearch } from "./research.js";
import { queryFor, search } from "./retrieve.js";

export const LIMITS = { turns: 8, userChars: 800, assistantChars: 2400 };
export const DEFAULT_MODEL = "claude-sonnet-5-5";

export const FRIENDLY = {
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
    let text = m.content.replace(/\s+/g, " ").trim();
    // Citation numbers restart with every answer; left in history they collide with the new answer's numbers.
    if (m.role === "assistant") text = text.replace(/\s?\[(?:C\d+|\d+)\]/g, "").trim();
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
export function finalize(text, core, hits, pubs = {}) {
  const byId = new Map(core.map((s) => [s.id, s]));
  const order = [];
  const sources = [];
  const citedCore = [];
  const citedHits = new Set();
  const answer = text
    .replace(/https?:\/\/\S+/g, "")
    .replace(/\[(C\d+|\d+)\]/g, (_, id) => {
      const ref = id.startsWith("C") ? byId.get(id) : hits[Number(id) - 1];
      if (ref && !id.startsWith("C")) citedHits.add(id);
      const url = ref?.url ?? ref?.u; // core sections say url/title; retrieved chunks say u/t
      if (!url) return "";
      if (id.startsWith("C") && !citedCore.includes(id)) citedCore.push(id);
      let n = order.indexOf(url) + 1;
      if (!n) {
        order.push(url);
        n = order.length;
        const pub = pubs[url];
        sources.push({ n, title: pub?.t ?? ref.title ?? ref.t, url, year: pub?.y ?? null, pdf: pub?.p || null });
      }
      return `[${n}]`;
    })
    .replace(/[ \t]+([.,;:])/g, "$1")
    .replace(/[ \t]{2,}/g, " ")
    .trim();
  return { answer, sources, citedCore, citedHits: citedHits.size };
}

export async function handleChat({ messages: raw, index, client, env = {}, today = new Date().toISOString().slice(0, 10) }) {
  const messages = cleanMessages(raw);
  if (!messages) return { status: 400, body: { error: "bad_request" }, meta: { route: "bad_request" } };
  const last = messages[messages.length - 1].content;

  if (isLegalHelpRequest(last)) {
    return { status: 200, body: { answer: LEGAL_REPLY, sources: LEGAL_SOURCES, related: [], handoff: null, flags: { legal: true } }, meta: { route: "legal" } };
  }

  // The questions asked most get a reviewed answer straight away: no model, no cost, the same words every time.
  const canned = env.CANNED === "off" ? null : matchCanned(index, messages);
  if (canned) {
    console.log(JSON.stringify({ event: "canned", id: canned.id }));
    const graphics = pickGraphics(index, { attached: canned.graphic ? [canned.graphic] : [] });
    return { status: 200, body: { answer: canned.answer, sources: canned.sources, related: [], graphics, handoff: handoffFor(index, { cannedId: canned.id }), flags: { canned: canned.id } }, meta: { route: "canned", id: canned.id, graphics: graphics.map((g) => g.id), handoff: handoffCause(index, { cannedId: canned.id }) } };
  }

  // "What is your stance on X?": a position we hold is stated as written, a topic our work never touches is deferred
  // on with fixed words, and a topic only the excerpts touch goes to the model under the stance rules in the prompt.
  const stance = env.CANNED === "off" ? null : resolveStance(index, last);
  if (stance?.kind === "position") {
    const sec = stance.section;
    const related = (sec.research ?? []).map((u) => index.pubs?.[u] && { title: index.pubs[u].t, url: u, year: index.pubs[u].y, pdf: index.pubs[u].p || null }).filter(Boolean).slice(0, 3);
    console.log(JSON.stringify({ event: "stance", kind: "position", id: sec.id }));
    const graphics = pickGraphics(index, { attached: sec.graphics ?? [] });
    return { status: 200, body: { answer: `${sec.text.trim()} [1]`, sources: [{ n: 1, title: sec.title, url: sec.url, year: null, pdf: null }], related, graphics, handoff: null, flags: { canned: "stance", position: sec.title } }, meta: { route: "stance_position", position: sec.title, graphics: graphics.map((g) => g.id) } };
  }
  if (stance?.kind === "defer") {
    const d = (index.faq ?? []).find((e) => e.id === "no-position");
    if (d) {
      console.log(JSON.stringify({ event: "stance", kind: "defer" }));
      return { status: 200, body: { answer: d.answer, sources: d.sources, related: [], handoff: handoffFor(index, { cannedId: "no-position" }), flags: { canned: "no-position" } }, meta: { route: "stance_defer", handoff: "deferral" } };
    }
  }

  const hits = search(index, queryFor(messages));
  const model = env.MODEL || DEFAULT_MODEL;
  let resp;
  try {
    const params = {
      model,
      max_tokens: 1100,
      output_config: { effort: env.EFFORT || "low" },
      system: [
        { type: "text", text: buildSystem(index.core, index.graphics, { draw: env.DYNAMIC_GRAPHICS !== "0" }), cache_control: { type: "ephemeral", ttl: "1h" } },
        { type: "text", text: buildExcerpts(hits, today, { stance: stance?.kind === "excerpts" }) },
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
    return { status: 502, body: { error: "unavailable", answer: FRIENDLY.unavailable, sources: [] }, meta: { route: "upstream_error", upstream: err?.status ?? null } };
  }

  const usage = resp.usage ?? {};
  console.log(JSON.stringify({
    event: "chat", model, stop: resp.stop_reason, hits: hits.length, in: usage.input_tokens,
    cacheRead: usage.cache_read_input_tokens, cacheWrite: usage.cache_creation_input_tokens, out: usage.output_tokens,
  }));

  if (resp.stop_reason === "refusal") {
    return { status: 200, body: { answer: FRIENDLY.declined, sources: [], related: [], flags: { refusal: true } }, usage, model, meta: { route: "refusal" } };
  }
  const text = (resp.content ?? []).filter((b) => b.type === "text").map((b) => b.text).join("\n").trim();
  if (!text) return { status: 502, body: { error: "empty", answer: FRIENDLY.unavailable, sources: [] }, usage, model, meta: { route: "empty" } };
  if (text.startsWith(LEGAL_SENTINEL) || text.includes(LEGAL_SENTINEL)) {
    return { status: 200, body: { answer: LEGAL_REPLY, sources: LEGAL_SOURCES, related: [], handoff: null, flags: { legal: true } }, usage, model, meta: { route: "legal" } };
  }
  const staff = takeStaffMarker(text); // [[staff]]: the model says a person should look at this
  const marked = takeMarkers(staff.text, index);
  // A chart the model drew itself is shown only when no vetted graphic covers the question, and only if every figure in it
  // is quoted from the text the model was given (charts.js).
  const drawn = takeChart(marked.text, resolver(index.core, hits, index.pubs));
  const { answer, sources, citedCore, citedHits } = finalize(drawn.text, index.core, hits, index.pubs);
  const graphics = pickGraphics(index, { question: last, marked: marked.ids, answer });
  if (!graphics.length && drawn.chart && env.DYNAMIC_GRAPHICS !== "0") graphics.push(drawn.chart);
  const related = suggestResearch({
    index, query: queryFor(messages), hits, citedCoreIds: citedCore, fromHits: citedHits > 0, exclude: sources.map((s) => s.url),
  });
  // Counts only, never message text: "uncited" answers are where the knowledge base may have a gap.
  console.log(JSON.stringify({ event: "answer", cited: sources.length, related: related.length, graphics: graphics.length, drawn: Boolean(graphics[0]?.generated), uncited: sources.length === 0 }));
  const handoff = handoffFor(index, { asked: staff.asked, answer });
  // For the daily roll-up (stats.js): counts and codes only, never any text. What became of a chart the model drew.
  const shownDrawn = Boolean(graphics[0]?.generated);
  const drawnStatus = !drawn.offered ? null : env.DYNAMIC_GRAPHICS === "0" ? "disabled" : !drawn.chart ? `rejected:${drawn.why ?? "unknown"}` : shownDrawn ? "accepted" : "unused";
  const meta = {
    route: "model", cited: sources.length, related: related.length, graphics: graphics.filter((g) => !g.generated).map((g) => g.id),
    drawn: drawnStatus, handoff: handoffCause(index, { asked: staff.asked, answer }),
  };
  return { status: 200, body: { answer, sources, related, graphics, handoff, flags: {} }, usage, model, meta };
}
