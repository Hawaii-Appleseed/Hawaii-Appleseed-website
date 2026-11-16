// Must match tokenize() in chatbot/build_index.py. Both are tested against
// chatbot/tokenizer_vectors.json; change one and the other, then regenerate it.

const STOPWORDS = new Set(
  ("a an and are as at be but by for from has have how i if in into is it its of on or " +
    "our so than that the their them then there these they this to was we were what when " +
    "where which who why will with you your do does did can could would should about " +
    "tell me please").split(" "),
);
const BILL = /\b(hb|sb|hr|sr|hcr|scr|gm)\s*(\d{1,4})\b/g;
const APOSTROPHES = /[ʻ’‘'`]/g;

export function tokenize(text) {
  const t = text
    .normalize("NFKD")
    .toLowerCase()
    .replace(/\p{M}/gu, "")
    .replace(APOSTROPHES, "")
    .replace(BILL, "$1$2");
  const out = [];
  for (let w of t.match(/[a-z0-9]+/g) ?? []) {
    if (w.length < 2 || STOPWORDS.has(w)) continue;
    if (w.length > 4 && /(xes|ches|shes|sses)$/.test(w)) w = w.slice(0, -2); // taxes -> tax, branches -> branch
    else if (w.length > 4 && w.endsWith("ies")) w = w.slice(0, -3) + "y"; // policies -> policy, priorities -> priority
    else if (w.length > 3 && w.endsWith("s") && !w.endsWith("ss")) w = w.slice(0, -1);
    out.push(w);
  }
  return out;
}
