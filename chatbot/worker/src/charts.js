// Charts the model drafts itself, for questions none of the vetted graphics (graphics.js) covers.
//
// The model may end an answer with  [[chart: {json}]]. It never gets to put a number on the page unchecked: every row
// must carry a `quote` copied word for word from the one KNOWLEDGE section or excerpt named by `ref`, every number the row
// shows must be in that quote, a bar's label must say its value, and bars may only compare values of one kind and scale
// ("$300 million" next to "$185 million", never "66 percent" next to "$5.68 billion"). A chart that fails any check is
// dropped and the answer stands without it; the page only ever receives the checked, plain-data result and draws it
// with text nodes, so nothing the model writes can run as code. Switched off with DYNAMIC_GRAPHICS=0.

const MARK = /\[\[\s*chart\s*:\s*(\{[\s\S]*?\})\s*\]\]/g;
const STRAY = /\[+\s*chart\s*:[\s\S]*$/i; // a marker that never closed (cut off) or did not parse: drop it, keep the answer

const NUM = /\d[\d,]*(?:\.\d+)?/g;
const TENS = { twenty: 20, thirty: 30, forty: 40, fifty: 50, sixty: 60, seventy: 70, eighty: 80, ninety: 90 };
const ONES = { one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7, eight: 8, nine: 9 };
const SPELLED = new RegExp(`\\b(${Object.keys(TENS).join("|")})(?:-(${Object.keys(ONES).join("|")}))?\\b`, "gi");
const SCALE = /^\s*(thousand|million|billion|trillion)\b/i;

export const LIMITS = { title: 100, unit: 100, label: 120, display: 30, what: 140, quote: 400, minQuote: 12, bars: [2, 8], stats: [1, 4], timeline: [2, 8] };

/** Numbers in a string, as digits ("$1,000" -> 1000; a spelled-out "Sixty-six" -> 66). */
export function numbers(s) {
  const out = new Set();
  for (const m of String(s).matchAll(NUM)) out.add(m[0].replace(/,+$/, "").replace(/,/g, ""));
  for (const m of String(s).matchAll(SPELLED)) out.add(String(TENS[m[1].toLowerCase()] + (m[2] ? ONES[m[2].toLowerCase()] : 0)));
  return out;
}

/** Whitespace, case, quote marks, okina, dashes and markdown stars set aside, so a copied quote still matches. */
export const squash = (s) =>
  String(s).normalize("NFKC").toLowerCase().replace(/[ʻ’‘'`"“”*_]/g, "").replace(/[‐‑–—−]/g, "-").replace(/\s+/g, " ").trim();

/** The scale words ("million", or "" for none) that follow `num` wherever it stands alone in `text` ("20" is not "2017"). */
function scalesAfter(text, num) {
  const flat = String(text).replace(/(\d),(?=\d)/g, "$1");
  const found = new Set();
  const re = new RegExp(`(?<![\\d.])${num.replace(/\./g, "\\.")}(?!\\d|\\.\\d)`, "g");
  for (const m of flat.matchAll(re)) found.add((SCALE.exec(flat.slice(m.index + num.length))?.[1] ?? "").toLowerCase());
  return found;
}

const kindOf = (display) => (/%|percent/i.test(display) ? "percent" : /\$/.test(display) ? "dollars" : "count");

const text = (v, max) => typeof v === "string" && v.trim().length > 0 && v.trim().length <= max && !/[<>]/.test(v);

/** One row's evidence: the section or excerpt it names, and whether its quote is really in it. */
function evidence(row, resolve) {
  if (!text(row?.quote, LIMITS.quote) || row.quote.trim().length < LIMITS.minQuote) return { why: "quote_form" };
  const ref = String(row.ref ?? "").replace(/[[\]\s]/g, "").toUpperCase();
  const src = resolve(ref);
  if (!src) return { why: "ref" };
  if (!squash(src.text).includes(squash(row.quote))) return { why: "quote_not_found" };
  return { quote: row.quote.trim(), src };
}

/** Check one drafted chart against the text the model was given. Returns the plain-data chart, or null. */
function inspectChart(spec, resolve) {
  const fail = (why) => ({ why });
  if (!spec || typeof spec !== "object" || !["bars", "stats", "timeline"].includes(spec.type)) return fail("shape");
  if (!text(spec.title, LIMITS.title)) return fail("title");
  if (spec.unit != null && !text(spec.unit, LIMITS.unit)) return fail("unit");
  const list = spec.type === "stats" ? spec.items : spec.rows;
  const [lo, hi] = LIMITS[spec.type];
  if (!Array.isArray(list) || list.length < lo || list.length > hi) return fail("rows");

  const sources = new Map();
  const pool = new Set();
  const rows = [];
  for (const r of list) {
    const ev = evidence(r, resolve);
    if (ev.why) return ev;
    const quoted = numbers(ev.quote);
    for (const n of quoted) pool.add(n);
    const within = (...fields) => fields.every((f) => [...numbers(f)].every((n) => quoted.has(n)));
    if (ev.src.url) sources.set(ev.src.url, { title: ev.src.title, url: ev.src.url, year: ev.src.year ?? null });

    if (spec.type === "bars") {
      if (!text(r.label, LIMITS.label) || !text(r.display, LIMITS.display)) return fail("text");
      const first = String(r.display).match(NUM)?.[0];
      const value = Number(r.value);
      if (!first || !Number.isFinite(value) || value < 0 || value !== Number(first.replace(/,/g, ""))) return fail("value");
      if (!within(r.label, r.display)) return fail("number_unquoted"); // every number shown is in this row's quote
      const scale = (String(r.display).match(/\b(thousand|million|billion|trillion)\b/i)?.[1] ?? "").toLowerCase();
      if (!scalesAfter(ev.quote, first.replace(/,/g, "")).has(scale)) return fail("scale"); // "$183.4" for "$183.4 million" would be a lie of scale
      if (/%|percent/i.test(r.display) && !/%|percent/i.test(ev.quote)) return fail("percent");
      rows.push({ label: r.label.trim(), value, display: r.display.trim(), quote: ev.quote, _kind: kindOf(r.display), _scale: scale });
    } else if (spec.type === "stats") {
      if (!text(r.value, LIMITS.display) || !text(r.label, LIMITS.label) || !numbers(r.value).size) return fail("text");
      if (!within(r.value, r.label)) return fail("number_unquoted");
      rows.push({ value: r.value.trim(), label: r.label.trim(), quote: ev.quote });
    } else {
      if (!text(r.when, 20) || !text(r.what, LIMITS.what) || !numbers(r.when).size) return fail("text");
      if (!within(r.when, r.what)) return fail("number_unquoted");
      rows.push({ when: r.when.trim(), what: r.what.trim(), quote: ev.quote });
    }
  }
  if (!sources.size) return fail("no_source"); // a chart nobody can trace to a page is not shown
  if (![spec.title, spec.unit ?? ""].every((s) => [...numbers(s)].every((n) => pool.has(n)))) return fail("title_number");

  if (spec.type === "bars") {
    if (new Set(rows.map((r) => r._kind)).size > 1 || new Set(rows.map((r) => r._scale)).size > 1) return fail("mixed_units"); // like with like
    if (new Set(rows.map((r) => r.label.toLowerCase())).size < rows.length) return fail("duplicate_labels");
    for (const r of rows) { delete r._kind; delete r._scale; }
  }
  if (spec.type === "timeline" && rows.every((r) => /^\d{4}/.test(r.when))) rows.sort((a, b) => a.when.localeCompare(b.when));

  return {
    id: "drawn", type: spec.type, generated: true, title: spec.title.trim(),
    ...(spec.unit ? { unit: spec.unit.trim() } : {}),
    [spec.type === "stats" ? "items" : "rows"]: rows,
    note: "Drawn by the assistant from the passages quoted under “Show the numbers”. Check it against the sources.",
    sources: [...sources.values()].slice(0, 3),
  };
}

/** The checked chart, or null (the reason is `chartProblem`). */
export function checkChart(spec, resolve) {
  const r = inspectChart(spec, resolve);
  return r.why ? null : r;
}

/** Why a drafted chart was refused, as a short code ("quote_not_found", "mixed_units", ...), or null if it checks out. */
export function chartProblem(spec, resolve) {
  return inspectChart(spec, resolve).why ?? null;
}

/** Take the chart markers out of the model's text; `chart` is the first one that checks out, or null. */
export function takeChart(answer, resolve) {
  let chart = null;
  let offered = false;
  let why = null;
  const clean = answer
    .replace(MARK, (_, json) => {
      offered = true;
      if (chart) return "";
      try {
        const spec = JSON.parse(json);
        const r = inspectChart(spec, resolve);
        if (r.why) why ??= r.why; else chart = r;
      } catch {
        why ??= "json";
      }
      return "";
    })
    .replace(STRAY, () => { if (!offered) why = "cut_off"; offered = true; return ""; })
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
  return { text: clean, chart, offered, why: chart ? null : why };
}

/** Where a `ref` ("C37" or "2") points: the section or excerpt text, with a title and link for the source line. */
export function resolver(core, hits, pubs = {}) {
  return (ref) => {
    if (/^C\d+$/.test(ref)) {
      const s = core.find((c) => c.id === ref);
      return s ? { text: s.text, title: s.title, url: s.url } : null;
    }
    const h = /^\d+$/.test(ref) ? hits[Number(ref) - 1] : null;
    if (!h) return null;
    const pub = pubs[h.u];
    return { text: h.x, title: pub?.t ?? h.t, url: h.u ?? null, year: pub?.y ?? h.y ?? null };
  };
}
