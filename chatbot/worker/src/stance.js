// "What is your stance on the conveyance tax?" / "Do you support X?" / "Where does Appleseed stand on X?"
//
// Three outcomes, decided without a model so the answer is always grounded and never invented:
//   1. A position Hawaiʻi Appleseed holds (content/positions.md) -> that position, with its report links.
//   2. Nothing in the published work touches the topic at all   -> a fixed deferral. It does not echo the topic back.
//   3. The work touches the topic but no adopted position names it -> the model, told to report only what Appleseed's
//      own publications argue (naming the report), and to defer when the excerpts merely mention the topic.
// A question with more on its mind than one topic ("... and what happened in 2026?") is not handled here.
import { FILLER, prep } from "./canned.js";
import { tokenize } from "./tokenize.js";

const STANCE_WORDS = new Set(["stance", "position", "positions", "view", "views", "opinion", "opinions", "take", "stand", "thought", "thoughts", "policy", "support", "supports", "oppose", "opposes", "back", "endorse", "favor", "favour", "feel", "think", "believe", "regard", "regarding", "against", "opposed", "supportive", "favor", "pro", "anti"]);
// Words that name a kind of thing, not which thing: "the millionaire's tax" is about millionaire, "jaywalking laws" about jaywalking.
const KIND = new Set(["tax", "taxing", "bill", "law", "act", "program", "policy", "proposal", "measure", "idea", "rule", "plan", "legislation", "reform"]);
// Words that describe what is done to the topic or how wide it is, not which topic it is ("raising capital gains taxes").
const ACTION = new Set(["raise", "raising", "increase", "increasing", "pass", "passing", "adopt", "adopting", "create", "creating", "establish", "establishing", "implement", "implementing", "enact", "enacting", "expand", "expanding", "end", "ending", "eliminate", "eliminating", "repeal", "repealing", "state", "statewide", "local", "new", "proposed", "proposal"]);
// A topic is one thing. Words that start a second clause make it a compound question for the model.
const CLAUSE = /\b(and|or|but|also|plus|what|how|when|why|who|where|which|since|because|while|after|before)\b|[,;?]/;
const MAX_TOPIC_TOKENS = 5;

// The question must be about the organization's own view ("your", "Appleseed's"), never "the Governor's position on X".
const SUBJECT = String.raw`(?:your|(?:hawaii\s+)?appleseed|the\s+(?:organization|center)|this\s+organization)`;
const WHO = String.raw`(?:(?:hawaii\s+)?appleseed|you|the\s+(?:organization|center)|this\s+organization)`;
const PATTERNS = [
  new RegExp(String.raw`\b${SUBJECT}\s+(?:stance|position|positions|view|views|opinion|take|thoughts|policy)\s+(?:on|about|regarding|toward|towards)\s+(.+)$`),
  new RegExp(String.raw`\b(?:stance|position|view|opinion)\s+of\s+(?:hawaii\s+)?appleseed\s+(?:on|about|regarding)\s+(.+)$`),
  new RegExp(String.raw`\bwhere\s+(?:does|do)\s+${WHO}\s+stand\s+(?:on|about|regarding)\s+(.+)$`),
  new RegExp(String.raw`\b(?:does|do)\s+${WHO}\s+(?:support|oppose|back|endorse|favor|favour)\s+(.+)$`),
  new RegExp(String.raw`\b(?:is|are)\s+${WHO}\s+(?:for|against|in\s+favor\s+of|in\s+support\s+of|opposed\s+to|supportive\s+of)\s+(.+)$`),
  new RegExp(String.raw`\bhow\s+(?:does|do)\s+${WHO}\s+feel\s+about\s+(.+)$`),
  new RegExp(String.raw`\b(?:what|how)\s+(?:does|do)\s+${WHO}\s+think\s+(?:about|of)\s+(.+)$`),
  new RegExp(String.raw`\b(?:does|do)\s+${WHO}\s+want\s+(?:to\s+)?(.+)$`),
  new RegExp(String.raw`\b(?:does|do)\s+${WHO}\s+have\s+(?:a|any)\s+(?:stance|position|view|opinion)\s+(?:on|about|regarding)\s+(.+)$`),
];

const flat = (x) => x.toLowerCase().replace(/[^\p{L}\p{N}]+/gu, " ").replace(/\s+/g, " ").trim();

/** The topic words of a stance question, or null when it is not one (or has more than a single topic on its mind). */
export function stanceTopic(text) {
  return stanceQuery(text)?.tokens ?? null;
}

/** { tokens, phrase }: the topic's words and the topic as written (so "just cause eviction" can be found as a phrase). */
export function stanceQuery(text) {
  if (text.length > 160) return null;
  const n = prep(text).normalize("NFKD").replace(/\p{M}/gu, "").toLowerCase().replace(/[\u02bb\u2019\u2018`']/g, "").replace(/[^\p{L}\p{N}\s-]/gu, " ").replace(/\s+/g, " ").trim(); // Hawaiʻi -> hawaii
  for (const re of PATTERNS) {
    const m = re.exec(n);
    if (!m) continue;
    const phrase = m[1].replace(/^or\s+against\b/, " ").replace(/\bfor\s+or\s+against\b|\bfor\/against\b/g, " ");
    if (CLAUSE.test(phrase.replace(/\?+$/, ""))) return null;
    const tokens = [...new Set(tokenize(phrase).filter((t) => !FILLER.has(t) && !STANCE_WORDS.has(t) && !ACTION.has(t)))];
    return tokens.length >= 1 && tokens.length <= MAX_TOPIC_TOKENS ? { tokens, phrase: flat(phrase.replace(/^(?:the|a|an)\s+/, "")) } : null;
  }
  return null;
}

const cache = new WeakMap();
const content = (tokens) => new Set([...tokens].filter((t) => !KIND.has(t)));
const same = (a, b) => a.size === b.size && [...a].every((t) => b.has(t));
const words = (text) => new Set(tokenize(text).filter((t) => !FILLER.has(t) && !STANCE_WORDS.has(t) && !ACTION.has(t)));

function positions(index) {
  let p = cache.get(index);
  if (!p) {
    p = index.core.filter((c) => c.pos).map((c) => {
      const title = new Set(tokenize(c.title));
      return { c, title, titleContent: content(title), aliases: (c.aliases ?? []).map(words).filter((s) => s.size) };
    });
    cache.set(index, p);
  }
  return p;
}

/**
 * The position the topic names, or null. A topic names a position only by being one of its listed aliases or by being
 * most of its title; the text of a position is never searched, because a side note in one position ("charter schools"
 * in the school meals text) must not make it the answer about another subject. Two positions equally good: null.
 */
export function positionFor(index, tokens) {
  const topic = new Set(tokens);
  const topicContent = content(topic);
  const scored = [];
  for (const s of positions(index)) {
    let score = 0;
    for (const a of s.aliases) {
      const ac = content(a);
      if (same(topic, a) || (topicContent.size && ac.size && same(topicContent, ac))) { score = 3; break; }
    }
    if (!score && topicContent.size && [...topicContent].every((t) => s.title.has(t)) && topicContent.size / Math.max(s.titleContent.size, 1) >= 0.5) {
      score = 1 + topicContent.size / s.titleContent.size;
    }
    if (score) scored.push({ c: s.c, score });
  }
  scored.sort((x, y) => y.score - x.score);
  if (!scored.length || (scored[1] && scored[1].score >= scored[0].score)) return null;
  return scored[0].c;
}

/** Bounded edit distance, for telling a typo of a word in our work ("conveyence") from a word that is simply absent. */
function within(a, b, max) {
  if (Math.abs(a.length - b.length) > max) return false;
  let prev = Array.from({ length: b.length + 1 }, (_, j) => j);
  for (let i = 1; i <= a.length; i++) {
    const cur = [i];
    let rowMin = i;
    for (let j = 1; j <= b.length; j++) {
      cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
      rowMin = Math.min(rowMin, cur[j]);
    }
    if (rowMin > max) return false;
    prev = cur;
  }
  return prev[b.length] <= max;
}

/** True when `token` is not a word our published work uses, and is not a near-miss of one either. */
export function absentFromWork(index, token) {
  if (index.bm25.post[token]) return false;
  const max = token.length >= 7 ? 2 : token.length >= 5 ? 1 : 0;
  return !Object.keys(index.bm25.post).some((t) => within(token, t, max));
}

/**
 * { kind: "position", section } | { kind: "defer" } | { kind: "excerpts" } | null (not a stance question).
 *   position: a position we hold. Say it as written, with its reports.
 *   defer:    a short topic with a word our published work never uses and no near-typo of one: nothing to answer from.
 *   excerpts: everything else, including topics that only the excerpts touch: the model answers under the stance rules.
 * Deferral is deliberately rare. Wrongly deferring on something we have written about is worse than asking the model.
 */
export function resolveStance(index, text) {
  const q = stanceQuery(text);
  if (!q || q.tokens.every((t) => KIND.has(t))) return null; // "do you support taxes?" is a general question
  const section = positionFor(index, q.tokens);
  if (section) return { kind: "position", section };
  const topic = q.tokens.filter((t) => !KIND.has(t));
  const absent = topic.filter((t) => absentFromWork(index, t));
  return topic.length <= 3 && absent.length > 0 ? { kind: "defer" } : { kind: "excerpts" };
}
