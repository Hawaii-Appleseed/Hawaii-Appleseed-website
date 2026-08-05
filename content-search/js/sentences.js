// Sentence splitting, figure detection, candidate selection, and section
// grouping — ports of the same-named helpers in retrieval.py. The cross-encoder
// SCORING of candidates happens in the worker; this module only does the cheap
// deterministic parts (selection + grouping) that must match Python exactly.

// Split on sentence-ending punctuation OR a blank-line paragraph break. NOT on
// bare single newlines (PDF wraps). One capture group, so JS split interleaves
// the delimiters exactly like Python re.split.
const SENT_DELIM_RE = /([.!?]+['")\]]*\s+|\n\s*\n+)/;

export function splitSentences(text) {
  const parts = text.split(SENT_DELIM_RE);
  const pairs = [];
  for (let i = 0; i < parts.length; i += 2) {
    const body = parts[i] ?? "";
    const delim = i + 1 < parts.length ? parts[i + 1] : "";
    if (body || delim) pairs.push([body, delim]);
  }
  return pairs;
}

const FIGURE_RE =
  /\d+(?:\.\d+)?\s?%|\$\s?\d[\d,]*|\b\d{1,3}(?:,\d{3})+\b|\b\d+(?:\.\d+)?\s?(?:million|billion|percent|x)\b|\b\d{3,}\b/i;

// Candidate sentences for top_sentences: stripped bodies ≥ minLen, capped.
export function sentenceCandidates(text, minLen = 40, maxCandidates = 400) {
  const cand = [];
  for (const [b] of splitSentences(text)) {
    const s = b.trim();
    if (s.length >= minLen) cand.push(s);
  }
  return cand.slice(0, maxCandidates);
}

// Candidate sentences for stat_sentences: also must carry a figure.
export function statCandidates(text, minLen = 30, maxCandidates = 400) {
  const cand = [];
  for (const [b] of splitSentences(text)) {
    const s = b.trim();
    if (s.length >= minLen && FIGURE_RE.test(s)) cand.push(s);
  }
  return cand.slice(0, maxCandidates);
}

// Collapse rank-ordered (text, meta) hits into one entry per source document,
// surfacing the count of distinct relevant SECTIONS. Direct port of
// retrieval.group_sections — preserves first-seen source order, merges adjacent
// chunk-index runs, represents each run by its best (lowest) rank.
// `hits` is [{text, meta}] already filtered + ordered best-first.
export function groupSections(hits, limit) {
  const groups = new Map(); // source -> [{rank, chunk, text, meta}]
  hits.forEach((h, rank) => {
    const src = h.meta.source ?? "?";
    if (!groups.has(src)) groups.set(src, []);
    groups.get(src).push({
      rank,
      chunk: parseInt(h.meta.chunk ?? 0, 10) || 0,
      text: h.text,
      meta: h.meta,
    });
  });

  const out = [];
  for (const items of groups.values()) {
    const byIdx = items.slice().sort((a, b) => a.chunk - b.chunk);
    const runs = [[byIdx[0]]];
    for (const it of byIdx.slice(1)) {
      if (it.chunk === runs[runs.length - 1][runs[runs.length - 1].length - 1].chunk + 1) {
        runs[runs.length - 1].push(it);
      } else {
        runs.push([it]);
      }
    }
    const sections = runs.map((run) =>
      run.reduce((best, x) => (x.rank < best.rank ? x : best), run[0])
    );
    sections.sort((a, b) => a.rank - b.rank);
    const primary = sections[0];
    out.push({
      text: primary.text,
      meta: primary.meta,
      n_sections: sections.length,
      extra_sections: sections.slice(1).map((s) => ({ chunk: s.chunk, text: s.text })),
    });
  }
  return out.slice(0, limit);
}
