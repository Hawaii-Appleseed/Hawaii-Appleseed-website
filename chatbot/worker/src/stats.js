// The daily roll-up: what the assistant did each day, as counts. No question, answer, email, or IP is ever kept here (only ids and
// titles of OUR content, codes, and numbers), so it can be shown to every staff member without a privacy review; the rated
// answers with their text are a separate, opt-in thing (the feedback ratings, in KV for 90 days).
//
// It answers the questions the pilot needs answered: how often is each route used (ready-made answers cost nothing; the model does),
// what does a day cost, how often does the assistant come up empty (uncited answers, "ask a person"), are the charts it draws being
// accepted or refused and why, which positions and graphics do people ask for, and how do people rate the answers.
//
// Saved in KV as one small JSON document per day (`stats:YYYY-MM-DD`, kept 400 days). KV is not atomic, so two answers finishing in the
// same instant can lose one count: treat the numbers as accurate to a few percent. It costs one KV write per request.
import { microDollars } from "./pricing.js";

export const STATS_TTL = 400 * 24 * 3600;
export const CHART_SAMPLE_PER_DAY = 20; // accepted model-drawn charts kept per day for a person to read
export const CHART_SAMPLE_TTL = 45 * 24 * 3600;
export const statsKey = (day) => `stats:${day}`;

export const emptyDay = () => ({
  n: 0, people: 0,
  route: {}, canned: {}, position: {}, graphics: {}, drawn: {}, handoff: {}, routed: {}, blocked: {},
  model: { answers: 0, uncited: 0, noRelated: 0, tokensIn: 0, tokensOut: 0, cacheRead: 0, cacheWrite: 0, microUsd: 0 },
  feedback: { up: 0, down: 0 },
});

const bump = (obj, key, by = 1) => { if (key) obj[key] = (obj[key] ?? 0) + by; };

/**
 * Fold one event into a day's counts (pure). An event is what handleChat returns as `meta` plus its `usage` and `model`:
 *   { route, id?, position?, graphics?, drawn?, handoff?, cited?, related?, usage?, model?, newPerson? }
 * or { blocked: "rate_limited" | "budget" | "verification_failed" } or { feedback: "up" | "down" }.
 */
export function tally(day, ev) {
  const d = day ?? emptyDay();
  if (ev.newPerson) d.people++;
  if (ev.blocked) { bump(d.blocked, ev.blocked); return d; }
  if (ev.feedback) { if (ev.feedback === "up" || ev.feedback === "down") d.feedback[ev.feedback]++; return d; }
  d.n++;
  bump(d.route, ev.route);
  if (ev.route === "canned") bump(d.canned, ev.id);
  if (ev.route === "stance_position") bump(d.position, ev.position);
  for (const g of ev.graphics ?? []) bump(d.graphics, g);
  bump(d.handoff, ev.handoff);
  for (const id of ev.routed ?? []) bump(d.routed, id);
  if (ev.usage) {
    const m = d.model, u = ev.usage;
    m.tokensIn += u.input_tokens ?? 0; m.tokensOut += u.output_tokens ?? 0;
    m.cacheRead += u.cache_read_input_tokens ?? 0; m.cacheWrite += u.cache_creation_input_tokens ?? 0;
    m.microUsd += microDollars(u, ev.model);
  }
  if (ev.route === "model") {
    d.model.answers++;
    if (!ev.cited) d.model.uncited++;
    if (!ev.related) d.model.noRelated++;
    bump(d.drawn, ev.drawn);
  }
  return d;
}

/** Save one event; returns the day's counts, or null. Never throws: a failed count must not fail an answer. When a chart the
 *  model drew is shown, the first CHART_SAMPLE_PER_DAY of the day are also kept (the chart only: its title, rows, quotes and
 *  sources, all text from our own publications; nothing the visitor typed) so staff can judge whether they are sensible. */
export async function record(kv, ev, now = new Date()) {
  if (!kv) return null;
  try {
    const date = now.toISOString().slice(0, 10);
    const key = statsKey(date);
    const have = await kv.get(key);
    const d = tally(have ? JSON.parse(have) : null, ev);
    await kv.put(key, JSON.stringify(d), { expirationTtl: STATS_TTL });
    if (ev.drawn === "accepted" && ev.chart && d.drawn.accepted <= CHART_SAMPLE_PER_DAY) {
      const { title, unit, type, rows, items, sources } = ev.chart;
      await kv.put(`chart:${date}:${d.drawn.accepted}`, JSON.stringify({ date, title, unit, type, rows, items, sources }), { expirationTtl: CHART_SAMPLE_TTL });
    }
    return d;
  } catch (err) {
    console.log(JSON.stringify({ event: "stats_error", name: err?.name }));
    return null;
  }
}

/** The kept sample of accepted model-drawn charts, newest first. */
export async function readCharts(kv, days = 7, now = new Date()) {
  const keys = [];
  for (let i = 0; i < days; i++) {
    const date = new Date(now.getTime() - i * 86400000).toISOString().slice(0, 10);
    for (let n = CHART_SAMPLE_PER_DAY; n >= 1; n--) keys.push(`chart:${date}:${n}`);
  }
  const got = await Promise.all(keys.map(async (k) => { try { const raw = await kv.get(k); return raw ? JSON.parse(raw) : null; } catch { return null; } }));
  return got.filter(Boolean);
}

/** The last `n` days, newest first, each { date, ...counts } (an unrecorded day is all zeros). */
export async function readDays(kv, n = 14, now = new Date()) {
  const days = [];
  for (let i = 0; i < n; i++) days.push(new Date(now.getTime() - i * 86400000).toISOString().slice(0, 10));
  return Promise.all(days.map(async (date) => {
    let d = null;
    try { const raw = await kv.get(statsKey(date)); d = raw ? JSON.parse(raw) : null; } catch { /* a corrupt day reads as empty */ }
    return { date, ...emptyDay(), ...(d ?? {}) };
  }));
}

const sum = (days, pick) => days.reduce((n, d) => n + (pick(d) ?? 0), 0);
const sumKeys = (days, field) => days.reduce((acc, d) => { for (const [k, v] of Object.entries(d[field] ?? {})) acc[k] = (acc[k] ?? 0) + v; return acc; }, {});

/** Totals and rates over a set of days. */
export function summarize(days) {
  const n = sum(days, (d) => d.n);
  const route = sumKeys(days, "route");
  const drawn = sumKeys(days, "drawn");
  const handoff = sumKeys(days, "handoff");
  const answers = sum(days, (d) => d.model.answers);
  const usd = sum(days, (d) => d.model.microUsd) / 1e6;
  const asked = (k) => route[k] ?? 0;
  const handoffTotal = Object.values(handoff).reduce((a, b) => a + b, 0);
  return {
    answers: n, people: sum(days, (d) => d.people),
    readyMade: asked("canned") + asked("stance_position") + asked("stance_defer") + asked("legal"),
    model: answers, usd, usdPerModelAnswer: answers ? usd / answers : 0,
    uncited: sum(days, (d) => d.model.uncited), handoff: handoffTotal, handoffBy: handoff,
    drawn, drawnAccepted: drawn.accepted ?? 0, drawnRejected: Object.entries(drawn).filter(([k]) => k.startsWith("rejected:")).reduce((a, [, v]) => a + v, 0),
    problems: asked("refusal") + asked("upstream_error") + asked("empty"),
    blocked: sumKeys(days, "blocked"), route,
    feedback: { up: sum(days, (d) => d.feedback.up), down: sum(days, (d) => d.feedback.down) },
    canned: sumKeys(days, "canned"), position: sumKeys(days, "position"), graphics: sumKeys(days, "graphics"), routed: sumKeys(days, "routed"),
  };
}

// ----------------------------------------------------------------------------------------------- the page
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const pct = (a, b) => (b ? `${Math.round((100 * a) / b)}%` : "–");
const usd = (x) => `$${x < 0.1 ? x.toFixed(4) : x.toFixed(2)}`;
const top = (obj, limit = 8) => Object.entries(obj).sort((a, b) => b[1] - a[1]).slice(0, limit);

function list(title, entries, note = "") {
  if (!entries.length) return `<section><h2>${esc(title)}</h2><p class="m">Nothing yet.</p></section>`;
  return `<section><h2>${esc(title)}</h2>${note ? `<p class="m">${esc(note)}</p>` : ""}<table><tbody>${entries.map(([k, v]) => `<tr><td>${esc(k)}</td><td class="r">${v}</td></tr>`).join("")}</tbody></table></section>`;
}

/** The staff page: counts only, no scripts. */
export function statsPage(days, { budgetUsd = null, spentToday = null, built = "" } = {}) {
  const s = summarize(days);
  const cards = [
    ["Answers", s.answers, `${s.people} ${s.people === 1 ? "person-day" : "person-days"}`],
    ["Answered without the model", pct(s.readyMade, s.answers), "ready-made, stated positions, legal"],
    ["Spend", usd(s.usd), s.model ? `${usd(s.usdPerModelAnswer)} per model answer` : "no model answers"],
    ["Came up empty", pct(s.uncited, s.model), "model answers with no source"],
    ["Offered “ask a person”", s.handoff, Object.entries(s.handoffBy).map(([k, v]) => `${v} ${k}`).join(", ") || "never"],
    ["Charts the model drew", `${s.drawnAccepted} shown`, `${s.drawnRejected} refused`],
    ["Helpful / Flagged", `${s.feedback.up} / ${s.feedback.down}`, "ratings from the pilot"],
  ];
  const head = ["Day", "Answers", "People", "Ready-made", "Model", "Spend", "Empty", "Person", "Charts ok/refused", "Yes/No", "Blocked"];
  const rows = days.map((d) => {
    const ready = (d.route.canned ?? 0) + (d.route.stance_position ?? 0) + (d.route.stance_defer ?? 0) + (d.route.legal ?? 0);
    const drawnRej = Object.entries(d.drawn).filter(([k]) => k.startsWith("rejected:")).reduce((a, [, v]) => a + v, 0);
    const blocked = Object.values(d.blocked).reduce((a, b) => a + b, 0);
    const handoff = Object.values(d.handoff).reduce((a, b) => a + b, 0);
    return [d.date, d.n, d.people, ready, d.model.answers, usd(d.model.microUsd / 1e6), d.model.uncited, handoff, `${d.drawn.accepted ?? 0}/${drawnRej}`, `${d.feedback.up}/${d.feedback.down}`, blocked || ""];
  });
  const rejected = Object.entries(s.drawn).filter(([k]) => k.startsWith("rejected:")).map(([k, v]) => [k.slice(9).replace(/_/g, " "), v]);
  const blocked = Object.entries(s.blocked).map(([k, v]) => [k.replace(/_/g, " "), v]);
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex">
<title>Ask Hawaiʻi Appleseed: usage</title><link href="https://fonts.googleapis.com/css2?family=Manrope:wght@700;800&family=Poppins:wght@400;500&display=swap" rel="stylesheet">
<style>
 body{margin:0;background:#F4F7F4;color:#2F3E46;font:15px/1.5 Poppins,Arial,sans-serif}
 main{max-width:1000px;margin:0 auto;padding:32px 20px 64px}
 h1,h2{font-family:Manrope,Arial,sans-serif;font-weight:800;letter-spacing:-.01em;margin:0 0 6px}
 h1{font-size:28px} h2{font-size:18px;margin-top:28px}
 .eyebrow{font:700 11px Manrope,Arial,sans-serif;letter-spacing:.22em;text-transform:uppercase;color:#3F5F57;margin:0 0 6px}
 .m{color:rgba(47,62,70,.74);font-size:13px;margin:2px 0 8px}
 .cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-top:16px}
 .card{background:#fff;border:1px solid rgba(53,79,82,.14);border-left:4px solid #52796F;border-radius:6px;padding:10px 12px}
 .card b{display:block;font:800 22px Manrope,Arial,sans-serif} .card span{font-size:12px;color:rgba(47,62,70,.74)}
 table{border-collapse:collapse;width:100%;background:#fff;border:1px solid rgba(53,79,82,.14);font-variant-numeric:tabular-nums;font-size:13px}
 th,td{padding:6px 8px;border-top:1px solid rgba(53,79,82,.14);text-align:left} th{background:#E5E9E2;border-top:0} .r{text-align:right}
 .wrap{overflow-x:auto} section{margin-top:4px} a{color:#3F5F57}
</style></head><body><main>
<p class="eyebrow">Ask Hawaiʻi Appleseed</p><h1>Usage, last ${days.length} days</h1>
<p class="m">Counts only: no question, answer, email, or address is kept here. Numbers are accurate to a few percent (saved with Cloudflare KV, which can lose a count when two answers finish together).${built ? ` Content built ${esc(built)}.` : ""}${budgetUsd != null ? ` Today: ${usd((spentToday ?? 0) / 1e6)} of the ${usd(budgetUsd)} daily budget.` : ""}</p>
<div class="cards">${cards.map(([t, v, sub]) => `<div class="card"><span>${esc(t)}</span><b>${esc(v)}</b><span>${esc(sub)}</span></div>`).join("")}</div>
<h2>By day</h2><div class="wrap"><table><thead><tr>${head.map((h, i) => `<th${i ? ' class="r"' : ""}>${esc(h)}</th>`).join("")}</tr></thead><tbody>
${rows.map((r) => `<tr>${r.map((c, i) => `<td${i ? ' class="r"' : ""}>${esc(c)}</td>`).join("")}</tr>`).join("\n")}</tbody></table></div>
${list("Ready-made answers asked for", top(s.canned))}
${list("Positions asked for", top(s.position))}
${list("Charts shown with an answer", top(s.graphics))}
${list("Staff the assistant pointed people to", top(s.routed), "Counts of who was named under an answer, by id; nothing about the question.")}
${list("Why charts the model drew were refused", rejected, "A refused chart is dropped and the answer stands without it.")}
${list("Turned away", blocked, "Over a limit, over the day's budget, or failed verification.")}
${list("Where answers came from", top(s.route, 12))}
<p class="m" style="margin-top:28px">Raw data: <a href="/stats.json">/stats.json</a>. <a href="/flags">Read the flagged answers</a>. <a href="/stats/charts">Read a sample of the charts the model drew</a>. Source: chatbot/worker/src/stats.js.</p>
</main></body></html>`;
}

/** The staff page for reading the kept sample of model-drawn charts: are they sensible, or misleading? */
export function chartsPage(charts) {
  const one = (c) => {
    const rows = c.rows ?? c.items ?? [];
    const head = c.type === "bars" ? ["Item", "Value", "Quoted from the source"] : c.type === "stats" ? ["Figure", "What it is", "Quoted from the source"] : ["When", "What", "Quoted from the source"];
    const cells = (r) => c.type === "bars" ? [r.label, r.display, r.quote] : c.type === "stats" ? [r.value, r.label, r.quote] : [r.when, r.what, r.quote];
    return `<section><h2>${esc(c.title)}</h2><p class="m">${esc(c.date)} · ${esc(c.type)}${c.unit ? ` · ${esc(c.unit)}` : ""} · ${(c.sources ?? []).map((s) => esc(s.title)).join("; ")}</p>
<div class="wrap"><table><thead><tr>${head.map((h) => `<th>${esc(h)}</th>`).join("")}</tr></thead><tbody>${rows.map((r) => `<tr>${cells(r).map((x) => `<td>${esc(x)}</td>`).join("")}</tr>`).join("")}</tbody></table></div></section>`;
  };
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex">
<title>Ask Hawaiʻi Appleseed: charts the model drew</title><link href="https://fonts.googleapis.com/css2?family=Manrope:wght@700;800&family=Poppins:wght@400;500&display=swap" rel="stylesheet">
<style>body{margin:0;background:#F4F7F4;color:#2F3E46;font:15px/1.5 Poppins,Arial,sans-serif}main{max-width:1000px;margin:0 auto;padding:32px 20px 64px}
h1,h2{font-family:Manrope,Arial,sans-serif;font-weight:800;margin:0 0 6px}h1{font-size:28px}h2{font-size:17px;margin-top:26px}.m{color:rgba(47,62,70,.74);font-size:13px;margin:2px 0 8px}
table{border-collapse:collapse;width:100%;background:#fff;border:1px solid rgba(53,79,82,.14);font-size:13px}th,td{padding:6px 8px;border-top:1px solid rgba(53,79,82,.14);text-align:left;vertical-align:top}th{background:#E5E9E2;border-top:0}.wrap{overflow-x:auto}a{color:#3F5F57}</style></head><body><main>
<h1>Charts the model drew</h1>
<p class="m">The first ${CHART_SAMPLE_PER_DAY} a day that passed every check, kept 45 days. Each figure is quoted from our own publications; no visitor text is kept. For each, ask: would a reader take away something the sources do not say? If a pattern of misleading charts shows up, set DYNAMIC_GRAPHICS to "0" and tell the team what it was. <a href="/stats">Back to usage</a></p>
${charts.length ? charts.map(one).join("\n") : '<p class="m">None kept yet.</p>'}
</main></body></html>`;
}
