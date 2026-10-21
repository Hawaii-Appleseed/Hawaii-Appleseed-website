// Ready-made answers (content/faq.json, built into index.faq). A visitor question that matches one of an entry's
// phrasings gets that entry's answer at once, with no model call: instant, free, and identical every time.
//
// Strict on substance, relaxed on style. What counts is the question's topic words, after the filler is set aside
// (the organization's own name, "my", "please", "right now", "main", ...). They must be exactly the same words as a
// phrasing's. Any extra or missing topic word makes it a question for the model:
//   "what's your mission?"                      -> canned   (same topic words as "what is your mission")
//   "what is the mission of Hawaii Appleseed?"  -> canned   (the name is filler)
//   "what's your mission regarding housing?"    -> the model (housing is an extra topic word)
//   "how do I contact my legislator about HB2049" -> the model (a bill number is an extra topic word)
// A phrasing with no topic words at all ("who are you") matches only itself, exactly.
import { tokenize } from "./tokenize.js";

const MAX_QUESTION = 120;

// Words that do not change which question is being asked.
export const FILLER = new Set([
  "hawaii", "appleseed", "organization", "org", "center", "nonprofit",
  "my", "me", "us", "please", "kindly", "like", "want", "would", "could", "tell", "know", "just", "really", "actually",
  "right", "now", "currently", "today", "there", "here", "own", "anyone", "someone",
  "main", "key", "top", "biggest", "major", "current", "primary", "all", "about",
]);

// Different words for the same ask, folded to one before comparing. Kept small and literal on purpose: every entry
// here is a place where a wrong merge would answer the wrong question.
const SAME = {
  founded: "found", founder: "found", started: "found", start: "found", began: "found", begin: "found", established: "found", created: "found", launched: "found", formed: "found", operating: "found", existed: "found",
  careers: "job", career: "job", jobs: "job", hiring: "job", employment: "job", openings: "job", opening: "job", vacancies: "job",
  telephone: "phone", mobile: "phone",
  human: "person", somebody: "person",
  chatbot: "bot", robot: "bot",
  accomplish: "purpose", achieve: "purpose", point: "purpose", aim: "purpose", objective: "purpose", goal: "purpose", goals: "purpose", mission: "purpose",
  sits: "member", sit: "member", members: "member", serves: "member",
};
// A message made only of greeting words (with at least one real greeting), or only of thank-you words (with at least
// one real thanks), is a greeting or a thank-you however it is worded. "so" or "ok" alone are neither.
const GREETING_ANY = new Set(["hi", "hello", "hey", "aloha", "howdy", "greetings", "yo", "morning", "afternoon", "evening"]);
const GREETING_ALL = new Set([...GREETING_ANY, "good", "there"]);
const THANKS_ANY = new Set(["thanks", "thank", "mahalo", "appreciate", "appreciated", "cheers", "bye", "goodbye"]);
const THANKS_ALL = new Set([...THANKS_ANY, "you", "so", "much", "lot", "ton", "bunch", "nui", "loa", "very", "a", "ok", "okay", "great", "perfect", "awesome", "that", "was", "helpful", "helps", "it"]);

// "what's" -> "what", "I'd" -> "i": the suffix carries no topic. (The tokenizer would turn "what's" into "whats".)
export const prep = (s) => s.replace(/[‘’ʻ`']\s*(s|d|ll|m|re|ve)\b/gi, "");

const norm = (s) =>
  prep(s).normalize("NFKD").toLowerCase().replace(/\p{M}/gu, "").replace(/[ʻ’‘'`]/g, "").replace(/[^a-z0-9]+/g, " ").trim();

const canon = (t) => SAME[t] ?? t;
const topicWords = (s) => new Set(tokenize(prep(s)).map(canon).filter((t) => !FILLER.has(t)));
const rawWords = (s) => norm(s).split(" ").filter(Boolean);
// "who" is a stopword for retrieval, but it changes the question: "who should I ask?" is not "what can I ask?". A question that
// asks about a person only matches a phrasing that does too.
const asksWho = (s) => rawWords(s).some((w) => w === "who" || w === "whom" || w === "whose");

const compiled = new WeakMap();
function compile(index) {
  let c = compiled.get(index);
  if (!c) {
    c = (index.faq ?? []).map((e) => ({
      entry: e,
      exact: new Set(e.variants.map(norm)),
      sets: e.variants.map((v) => ({ words: topicWords(v), who: asksWho(v) })).filter((s) => s.words.size > 0),
    }));
    compiled.set(index, c);
  }
  return c;
}

/** The ready-made answer for the visitor's latest message, or null. */
export function matchCanned(index, messages) {
  const last = messages[messages.length - 1]?.content ?? "";
  if (last.length > MAX_QUESTION) return null;
  const n = norm(last);
  if (!n) return null;
  const q = topicWords(last);
  const who = asksWho(last);
  const words = rawWords(last);
  const byId = (id) => (index.faq ?? []).find((e) => e.id === id) ?? null;
  const only = (all, any) => words.length > 0 && words.length <= 7 && words.every((w) => all.has(w)) && words.some((w) => any.has(w));
  if (only(GREETING_ALL, GREETING_ANY)) return byId("greeting");
  if (only(THANKS_ALL, THANKS_ANY)) return byId("thanks");
  for (const { entry, exact, sets } of compile(index)) {
    if (exact.has(n)) return entry;
    if (!q.size) continue;
    for (const { words: v, who: vWho } of sets) {
      if (who !== vWho) continue; // asking about a person on both sides or neither ...
      if (q.size !== v.size) continue; // ... the same number of topic words ...
      let inter = 0;
      for (const t of q) if (v.has(t)) inter++;
      if (inter !== q.size) continue; // ... and the same ones. (Allowing "one fewer" matched "what's your position?" to "open positions".)
      return entry;
    }
  }
  return null;
}
