// Exact JS port of retrieval.py's tokenization + query expansion.
// Parity is verified against data/tokenizer_fixture.json (test/run_all.mjs).

// [A-Za-z0-9]+ — same token shape as Python; ʻokina and punctuation split.
const TOKEN_RE = /[A-Za-z0-9]+/g;

// Bill-form normalization. Mirror the three Python regexes EXACTLY, including
// case-sensitivity: _BILL_SPACE_RE is case-sensitive with explicit char classes;
// _BILL_LONG_RE is IGNORECASE.
const BILL_SPACE_RE = /\b([HShs][BRbr])\s+(\d)/g;
const BILL_LONG_RE = /\b(House|Senate)[\s-]+(Bill|Resolution)[\s-]+(\d+)/gi;

export function normalizeBills(text) {
  text = text.replace(BILL_LONG_RE, (_m, chamber, kind, num) => {
    const c = chamber.toLowerCase() === "house" ? "H" : "S";
    const k = kind.toLowerCase() === "bill" ? "B" : "R";
    return `${c}${k}${num}`;
  });
  // \1\2 — collapse the single space between bill prefix and first digit.
  text = text.replace(BILL_SPACE_RE, "$1$2");
  return text;
}

// Identical 26-word stoplist.
const STOP = new Set(
  ("the a an of and or to in on for with by is are was were be been from this " +
    "that these those it as at our we their").split(" ")
);

export function tokenize(text) {
  text = normalizeBills(text);
  const out = [];
  const matches = text.match(TOKEN_RE) || [];
  for (const t of matches) {
    const low = t.toLowerCase();
    if (!STOP.has(low)) out.push(low);
  }
  return out;
}

// Query-side acronym expansion (insertion order preserved, matching Python dict).
export const ALIASES = new Map([
  ["get", ["general excise tax"]],
  ["tat", ["transient accommodations tax"]],
  ["ctc", ["child tax credit"]],
  ["eitc", ["earned income tax credit"]],
  ["snap", ["food stamps", "nutrition assistance"]],
  ["tanf", ["temporary assistance for needy families"]],
  ["ada", ["americans with disabilities act"]],
  ["lih", ["low income housing"]],
  ["lihtc", ["low income housing tax credit"]],
  ["tod", ["transit oriented development"]],
  ["pfml", ["paid family medical leave"]],
]);

const ALIAS_TOKEN_RE = /\b([A-Za-z]{2,6})\b/g;

export function expandQuery(query) {
  const extras = [];
  const seen = new Set();
  const lowerQ = query.toLowerCase();
  let m;
  ALIAS_TOKEN_RE.lastIndex = 0;
  while ((m = ALIAS_TOKEN_RE.exec(query)) !== null) {
    const key = m[1].toLowerCase();
    const expansions = ALIASES.get(key);
    if (!expansions) continue;
    for (const expansion of expansions) {
      if (seen.has(expansion) || lowerQ.includes(expansion)) continue;
      seen.add(expansion);
      extras.push(expansion);
    }
  }
  return extras.length ? `${query} ${extras.join(" ")}` : query;
}

// ^[hs][br]\d{2,5}$ over already-lowercased tokens.
const BILL_TOKEN_RE = /^[hs][br]\d{2,5}$/;

export function billTokens(query) {
  const out = new Set();
  for (const t of tokenize(query)) {
    if (BILL_TOKEN_RE.test(t)) out.add(t);
  }
  return out;
}

export function isPureBillQuery(query) {
  const bills = billTokens(query);
  if (bills.size === 0) return false;
  const toks = new Set(tokenize(query));
  if (toks.size !== bills.size) return false;
  for (const t of toks) if (!bills.has(t)) return false;
  return true;
}
