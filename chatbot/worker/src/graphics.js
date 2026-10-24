// Explainer graphics. The library is content/graphics.json, vetted at build time (build_index.py): every figure in it
// is in the organization's own approved text, or the graphic is labeled a made-up illustration. The model never draws
// anything and never writes markup. At most it names a graphic from the library with a marker, [[graphic: id]], which is
// checked here against that library and stripped from the answer. The page draws the chart from the plain data this
// module sends (no HTML, no SVG), so nothing a visitor or the model types can run as code.
import { tokenize } from "./tokenize.js";

export const MAX_GRAPHICS = 2;
const MARKER = /\[\[\s*graphic\s*:\s*([A-Za-z0-9-]+)\s*\]\]/g;
const STRAY = /\[+\s*graphic\s*:[^\]\n]*\]*/gi; // anything marker-shaped that did not parse: unclosed, single-bracketed
// The visitor is asking to SEE or have something explained, not only to be told.
const INTENT = /\b(chart|graph|graphic|diagram|visual|visuali[sz]e|picture|illustrat\w*|infographic|timeline|explain|show me|walk me through|break(?:ing)? (?:it )?down)\b/i;

const byId = (index, id) => (index.graphics ?? []).find((g) => g.id === id) ?? null;

/** What the page needs to draw one graphic; nothing else leaves the Worker. */
export function publicGraphic(g) {
  const { id, type, title, unit, note, rows, items, illustration, source } = g;
  return { id, type, title, ...(unit && { unit }), ...(note && { note }), ...(rows && { rows }), ...(items && { items }), ...(illustration && { illustration: true }), source };
}

const compiled = new WeakMap();
function aliasSets(index) {
  let c = compiled.get(index);
  if (!c) {
    c = (index.graphics ?? []).map((g) => ({ g, sets: (g.aliases ?? []).map((a) => new Set(tokenize(a))).filter((s) => s.size >= 2) }));
    compiled.set(index, c);
  }
  return c;
}

/** The graphic a question names: all of one of its aliases' words are in the question, and either the visitor asks for a
 *  picture or the graphic is one that goes with its topic by itself (the history timeline, the session scoreboard).
 *  The alias with the most words wins; the question's other words never veto it, so aliases are written specific. */
export function graphicFor(index, question) {
  const q = new Set(tokenize(question));
  const asked = INTENT.test(question);
  let best = null;
  for (const { g, sets } of aliasSets(index)) {
    if (!asked && !g.auto) continue;
    for (const s of sets) {
      if (s.size > (best?.size ?? 0) && [...s].every((t) => q.has(t))) best = { g, size: s.size };
    }
  }
  return best?.g ?? null;
}

/** Numbers a graphic shows, other than years: what an answer must also say for the graphic to belong under it. */
function figures(g) {
  const strings = [];
  for (const r of [...(g.rows ?? []), ...(g.items ?? [])]) strings.push(String(r.display ?? ""), String(r.value ?? ""), String(r.item ?? ""), String(r.what ?? ""), String(r.label ?? ""));
  const out = new Set();
  for (const m of strings.join(" ").matchAll(/\d[\d,]*(?:\.\d+)?/g)) {
    const n = m[0].replace(/,/g, "").replace(/\.$/, "");
    if (!/^(19|20)\d\d$/.test(n)) out.add(n);
  }
  return out;
}

/** Take the graphic markers out of the model's text. `ids` are the ones that name a real graphic, in order. */
export function takeMarkers(text, index) {
  const ids = [];
  const clean = text
    .replace(MARKER, (_, id) => {
      const g = byId(index, id.toLowerCase());
      if (g && !ids.includes(g.id)) ids.push(g.id);
      return "";
    })
    .replace(STRAY, "")
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
  return { text: clean, ids };
}

/**
 * The graphics to show under an answer, at most MAX_GRAPHICS, as plain data.
 *   attached  ids that go with a ready-made answer or a stated position
 *   question  the visitor's words (a graphic they ask for by name)
 *   marked    ids the model named; each must share a figure with the answer, so a stray marker draws nothing
 */
export function pickGraphics(index, { attached = [], question = "", marked = [], answer = "" } = {}) {
  const out = [];
  const add = (g) => { if (g && !out.some((x) => x.id === g.id) && out.length < MAX_GRAPHICS) out.push(g); };
  for (const id of attached) add(byId(index, id));
  add(graphicFor(index, question));
  if (marked.length) {
    const said = new Set([...answer.matchAll(/\d[\d,]*(?:\.\d+)?/g)].map((m) => m[0].replace(/,/g, "").replace(/\.$/, "")));
    for (const id of marked) {
      const g = byId(index, id);
      if (g && [...figures(g)].some((n) => said.has(n))) add(g);
    }
  }
  return out.map(publicGraphic);
}

/** The list the model is shown: id, and what the graphic is for. */
export function graphicMenu(graphics) {
  return (graphics ?? []).map((g) => `- ${g.id}: ${g.title}${g.illustration ? " (a made-up illustration)" : ""}`).join("\n");
}
