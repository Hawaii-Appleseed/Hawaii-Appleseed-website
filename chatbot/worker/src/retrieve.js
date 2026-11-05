// BM25 lookup over the prebuilt postings in index.json (see build_index.py).
// The heavy work (tokenizing the corpus, document frequencies) happens at build
// time; a query only tokenizes itself and walks the postings of its own terms.
import { tokenize } from "./tokenize.js";

const K1 = 1.5;
const B = 0.75;

// Words that say nothing about which report a question is after.
const GENERIC = new Set(["hawaii", "appleseed", "state", "center", "law", "economic", "justice", "report", "brief", "help", "make", "want", "new", "read", "know", "tell", "find", "look"]);
const firstChunk = new WeakMap(); // index -> Map(report url -> chunk index of its opening passage)

function openings(index) {
  let m = firstChunk.get(index);
  if (!m) {
    m = new Map();
    index.chunks.forEach((c, i) => { if (c.k === "publication" && c.u && !m.has(c.u)) m.set(c.u, i); });
    firstChunk.set(index, m);
  }
  return m;
}

/** The report a question names, if exactly one family of reports does: every topic word of the question must be in
 *  its title ("how do I read the state budget" -> the newest Budget Primer). Newest wins among a series. */
export function reportNamedBy(index, queryTokens) {
  const q = queryTokens.filter((t) => !GENERIC.has(t) && !/^20\d\d$/.test(t));
  if (!q.length) return null;
  let best = null;
  for (const [url, p] of Object.entries(index.pubs ?? {})) {
    const title = new Set(tokenize(p.t));
    if (q.every((t) => title.has(t)) && (!best || (p.y ?? 0) > (best.p.y ?? 0) || ((p.y ?? 0) === (best.p.y ?? 0) && url > best.url))) best = { url, p };
  }
  return best?.url ?? null;
}

/** The text to search for: the latest question, plus the one before it when the
 *  latest is a short follow-up ("what about renters?"). */
export function queryFor(messages) {
  const users = messages.filter((m) => m.role === "user").map((m) => m.content);
  const last = users[users.length - 1] ?? "";
  if (tokenize(last).length < 4 && users.length > 1) return `${users[users.length - 2]} ${last}`;
  return last;
}

const docChunks = new WeakMap(); // index -> Map(document key -> its chunk indexes, in reading order)
const docKey = (c) => c.u ?? c.t;

function chunksOf(index) {
  let m = docChunks.get(index);
  if (!m) {
    m = new Map();
    index.chunks.forEach((c, i) => {
      const key = docKey(c);
      if (!m.has(key)) m.set(key, []);
      m.get(key).push(i);
    });
    docChunks.set(index, m);
  }
  return m;
}

/** The kind of writing a question asks for by name: "your blog post on…", "what did you testify…". */
export function kindAsked(query) {
  const q = query.toLowerCase();
  // "How do I testify?" is the visitor wanting to testify, not asking for ours.
  const visitor = /\b(i|me|my|myself)\b/.test(q) && !/\b(you|your|appleseed|you all|y'all)\b/.test(q);
  if (visitor) return null;
  if (/\btestif(y|ied|ies|ying)\b|\btestimon(y|ies)\b/.test(q)) return "testimony";
  if (/\bblog\b|\bblog ?posts?\b|\bposts?\b|\barticles?\b|\bop-?eds?\b/.test(q)) return "blog";
  return null;
}

// A blog post or one piece of testimony is short (median 5 passages), so when a question is plainly about one, the model
// gets the whole piece in reading order, not 2 disconnected fragments that miss its argument.
const FOCUS_KINDS = new Set(["blog", "testimony"]);
const FOCUS_MAX = 10; // passages of the focused piece (covers ~95% of posts whole; the longest are cut at 10)
const FOCUS_LEAD = 1.35; // the piece must outscore every other document by this much unless its kind was asked for
const KIND_BOOST = 1.6; // "your blog post on X" leans toward blog posts, "your testimony on X" toward testimony

/** The one blog post or testimony a question is about, if any: [document key, ...] or null. */
function focusDoc(index, ranked, asked, queryTokens) {
  // Best passage score per document among the leading few, nudged up when the piece's own title carries the question's
  // topic words ("your blog on Keiki Ride Free" -> the post titled "Keiki Ride Free…", not one that only mentions it).
  const topic = queryTokens.filter((t) => !GENERIC.has(t) && !TOPIC_NOISE.has(t));
  const docs = new Map(); // document key -> { score, kind }
  for (const [ci, s] of ranked) {
    const c = index.chunks[ci];
    const key = docKey(c);
    if (docs.has(key)) continue;
    const title = new Set(tokenize(c.t));
    const frac = topic.length ? topic.filter((t) => title.has(t)).length / topic.length : 0;
    docs.set(key, { score: s * (1 + 0.5 * frac), kind: c.k, frac });
    if (docs.size >= 8) break;
  }
  const ordered = [...docs.entries()].sort((a, b) => b[1].score - a[1].score);
  const [top, second] = ordered;
  if (!top || !FOCUS_KINDS.has(top[1].kind)) return null;
  if (asked === top[1].kind) return top[0];
  // Unasked, the piece must be plainly about the question: its title carries half the topic words and it leads clearly.
  if (top[1].frac >= 0.5 && (!second || top[1].score >= FOCUS_LEAD * second[1].score)) return top[0];
  return null;
}
// Words that say what kind of writing is wanted, not what it is about.
const TOPIC_NOISE = new Set(["blog", "post", "article", "testimony", "testify", "testified", "say", "said", "write", "wrote", "recent", "latest", "summarize", "summary", "submit", "submitted"]);

/** Top `k` chunks for `query`, at most `perDoc` from any one document, except that a question plainly about one blog
 *  post or piece of testimony gets that whole piece first (up to FOCUS_MAX passages, in reading order). */
export function search(index, query, { k = 6, perDoc = 2, focus = true } = {}) {
  const { n, avgdl, dl, post } = index.bm25;
  const asked = kindAsked(query);
  const scores = new Map();
  for (const term of new Set(tokenize(query))) {
    const p = post[term];
    if (!p) continue;
    const df = p.length / 2;
    const idf = Math.log(1 + (n - df + 0.5) / (df + 0.5));
    for (let i = 0; i < p.length; i += 2) {
      const ci = p[i];
      const tf = p[i + 1];
      const s = (idf * tf * (K1 + 1)) / (tf + K1 * (1 - B + (B * dl[ci]) / avgdl));
      scores.set(ci, (scores.get(ci) ?? 0) + s);
    }
  }
  const ranked = [...scores.entries()]
    .map(([ci, s]) => {
      const c = index.chunks[ci];
      // A gentle lean toward recent writing: the organization's voice and the facts move on.
      const recency = 1 + 0.03 * Math.max(0, (c.y ?? 2021) - 2021);
      return [ci, s * recency * (asked && c.k === asked ? KIND_BOOST : 1)];
    })
    .sort((a, b) => b[1] - a[1]);
  const hits = [];
  const perDocCount = new Map();
  const focused = focus && ranked.length ? focusDoc(index, ranked, asked, [...new Set(tokenize(query))]) : null;
  if (focused) {
    const top = ranked[0][1];
    for (const ci of chunksOf(index).get(focused).slice(0, FOCUS_MAX)) hits.push({ ...index.chunks[ci], score: top });
    perDocCount.set(focused, Infinity);
    k = hits.length + Math.max(3, k - 2); // still show a few other sources beside it
  }
  // A question that names a report gets that report's opening passage first, even when body text outscores it.
  const named = reportNamedBy(index, [...new Set(tokenize(query))]);
  const lead = named ? openings(index).get(named) : undefined;
  if (lead !== undefined) {
    hits.push({ ...index.chunks[lead], score: ranked[0]?.[1] ?? 0 });
    perDocCount.set(named, 1);
  }
  for (const [ci, score] of ranked) {
    const c = index.chunks[ci];
    const key = c.u ?? c.t;
    if (ci === lead || (perDocCount.get(key) ?? 0) >= perDoc) continue;
    perDocCount.set(key, (perDocCount.get(key) ?? 0) + 1);
    hits.push({ ...c, score });
    if (hits.length >= k) break;
  }
  return hits;
}
