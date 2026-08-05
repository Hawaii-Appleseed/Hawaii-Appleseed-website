// Term + semantic-sentence highlighting — port of search.py's highlight() and
// render_highlighted(). Escapes text first, then wraps query-term matches in
// <mark> and most-relevant sentences in a .relsent band.

import { splitSentences } from "./sentences.js";

export function escapeHtml(s) {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#x27;");
}

function escapeRegex(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

// Bill forms in the query become space-tolerant patterns so "HB1779" marks
// "HB 1779" in the source and vice-versa. Mirrors search._BILL_TERM_RE.
const BILL_TERM_RE = /([HShs][BRbr])\s?(\d{2,5})/g;
// ʻokina (U+02BB) kept in the token class, matching the Python pattern.
const TERM_RE = /[A-Za-z0-9ʻ]{3,}/g;

export function highlight(text, query) {
  const escaped = escapeHtml(text);
  const patterns = [];
  const billSpans = [];

  let m;
  BILL_TERM_RE.lastIndex = 0;
  while ((m = BILL_TERM_RE.exec(query)) !== null) {
    patterns.push(escapeRegex(m[1]) + "\\s*" + escapeRegex(m[2]));
    billSpans.push([m.index, m.index + m[0].length]);
  }

  TERM_RE.lastIndex = 0;
  while ((m = TERM_RE.exec(query)) !== null) {
    const start = m.index;
    if (billSpans.some(([s, e]) => s <= start && start < e)) continue;
    patterns.push(escapeRegex(m[0]));
  }

  if (patterns.length === 0) return escaped;
  patterns.sort((a, b) => b.length - a.length);
  const re = new RegExp("(" + patterns.join("|") + ")", "gi");
  return escaped.replace(re, "<mark>$1</mark>");
}

// render_highlighted: term-highlight, and wrap the most-relevant sentences (in
// `top`) in a .relsent band. Falls back to plain highlight when `top` is empty.
export function renderHighlighted(text, query, top) {
  const topSet = new Set(top || []);
  if (topSet.size === 0) return highlight(text, query);
  const chunks = [];
  for (const [body, delim] of splitSentences(text)) {
    let bh = highlight(body, query);
    if (body.trim() && topSet.has(body.trim())) {
      bh = `<span class='relsent'>${bh}</span>`;
    }
    chunks.push(bh + escapeHtml(delim));
  }
  return chunks.join("");
}
