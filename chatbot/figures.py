"""Cross-check the figures in the assistant's own content against what Hawaiʻi Appleseed has published.

Why: the positions in content/positions.md are adapted from a staff file whose entries are marked [REVIEW], and the
stance answers repeat them word for word with no model in between. One of them said the Hawaiian Home Lands waitlist
was "6,000 families ($800M backlog)" while Policy in Perspective 2026 says nearly 30,000. Nothing caught it.

What it does: pull every figure out of a piece of text (dollar amounts, percents, counts of 1,000 or more, bill and Act
numbers), pull the same kinds of figure out of the published corpus (reports, blog posts, testimony) and the
Legislature's bill feed, and report each figure of ours that no published source states, with the closest published
sentence beside it so a person can see whether it is a conflict ("6,000 families" next to "nearly 30,000 families") or
simply unpublished ("from staff").

A figure can be accepted on purpose in content/figures.json, with a reason, per section. The --public build refuses to
ship an approved position that has an unpublished figure nobody has accepted.

Pure functions; build_index.py passes in the data, and check_figures.py is the command-line report.
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict

_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
_SMALL = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
          "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
          "seventeen": 17, "eighteen": 18, "nineteen": 19}
_SPELLED = re.compile(
    r"\b(" + "|".join(_TENS) + r")(?:[- ](" + "|".join(k for k in _SMALL if 0 < _SMALL[k] < 10) + r"))?\b|\b("
    + "|".join(_SMALL) + r")\b", re.I)
_SCALE = {"thousand": 1e3, "million": 1e6, "billion": 1e9, "trillion": 1e12, "k": 1e3, "m": 1e6, "b": 1e9}
_NUM = r"(\d[\d,]*(?:\.\d+)?)"
_MONEY = re.compile(r"\$\s?" + _NUM + r"\s*(thousand|million|billion|trillion|[KMB]\b)?", re.I)
_PCT = re.compile(_NUM + r"\s?(?:%|percent\b|per cent\b)", re.I)
_RANGE_PCT = re.compile(_NUM + r"\s*(?:to|and|-|–|—)\s*" + _NUM + r"\s?(?:%|percent\b)", re.I)
_COUNT = re.compile(r"(?<![\d$.,])(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?\s*(?:thousand|million|billion))(?![\d,]*\s?(?:%|percent))", re.I)
_BILL = re.compile(r"\b(HB|SB|HR|SR|HCR|SCR|GM)\s?(\d{1,4})\b")
_ACT = re.compile(r"\bAct\s+(\d{1,3})\b")
_APOS = re.compile("[ʻ’‘`]")
CTX = 70  # characters either side of a figure that count as "what it is a figure of"
PRE = 32  # the label right before a figure ("affordable housing (") counts for more


def spell_to_digits(text: str) -> str:
    """"Sixty-six percent" -> "66 percent". Single digits and teens only when a figure unit follows (percent, million...),
    so the word "one" in "no one" is left alone."""
    def tens(m):
        if m.group(1):
            return str(_TENS[m.group(1).lower()] + (_SMALL[m.group(2).lower()] if m.group(2) else 0))
        return None
    out, last = [], 0
    for m in _SPELLED.finditer(text):
        val = tens(m)
        if val is None:  # a small word: only when a unit follows
            if not re.match(r"\s*(?:percent|%|million|billion|thousand)\b", text[m.end():m.end() + 14], re.I):
                continue
            val = str(_SMALL[m.group(3).lower()])
        out.append(text[last:m.start()]); out.append(val); last = m.end()
    out.append(text[last:])
    return "".join(out)


def _f(s: str) -> float:
    return float(s.replace(",", ""))


def _key(kind: str, value) -> str:
    if isinstance(value, float):
        value = round(value, 6)
        value = int(value) if value == int(value) else value
    return f"{kind}:{value}"


def extract(text: str) -> list[dict]:
    """Figures in `text`: [{key, kind, raw, sentence}], in order, each text span counted once."""
    text = _APOS.sub("", spell_to_digits(text))
    taken: list[tuple[int, int]] = []
    found: list[dict] = []

    def free(a, b):
        return all(b <= x or a >= y for x, y in taken)

    def sent(a, b):
        s0 = max(text.rfind(". ", 0, a) + 2, text.rfind("\n", 0, a) + 1, 0)
        e = text.find(". ", b)
        return text[s0:(len(text) if e < 0 else e + 1)].strip()

    def ctx(a, b):
        return text[max(0, a - CTX): b + CTX]

    def add(m, kind, value):
        taken.append((m.start(), m.end()))
        found.append({"key": _key(kind, value), "kind": kind, "raw": m.group(0).strip(), "sentence": sent(m.start(), m.end()),
                      "ctx": ctx(m.start(), m.end()), "pre": text[max(0, m.start() - PRE): m.start()],
                      "qual": qualifier(text[max(0, m.start() - 70): m.start()], text[m.end(): m.end() + 14]), "at": m.start()})

    for m in _MONEY.finditer(text):
        n = _f(m.group(1)) * _SCALE.get((m.group(2) or "").lower(), 1)
        add(m, "usd", n)
    for m in _RANGE_PCT.finditer(text):
        if free(m.start(), m.end()):
            for g in (1, 2):
                found.append({"key": _key("pct", _f(m.group(g))), "kind": "pct", "raw": f"{m.group(g)} percent", "sentence": sent(m.start(), m.end()), "ctx": ctx(m.start(), m.end()), "pre": text[max(0, m.start() - PRE): m.start()],
                      "qual": qualifier(text[max(0, m.start() - 70): m.start()], text[m.end(): m.end() + 14]), "at": m.start()})
            taken.append((m.start(), m.end()))
    for m in _PCT.finditer(text):
        if free(m.start(), m.end()):
            add(m, "pct", _f(m.group(1)))
    for m in _COUNT.finditer(text):
        if not free(m.start(), m.end()):
            continue
        raw = m.group(1).lower()
        scale = next((v for k, v in _SCALE.items() if len(k) > 1 and k in raw), 1)
        n = _f(re.sub(r"[a-z\s]+", "", raw)) * scale
        if 1900 <= n <= 2100 and "," not in raw:
            continue
        add(m, "num", n)
    for m in _BILL.finditer(text):
        add(m, "bill", f"{m.group(1)}{int(m.group(2))}")
    for m in _ACT.finditer(text):
        add(m, "act", int(m.group(1)))
    found.sort(key=lambda f: f["at"])
    return found


_MAX = re.compile(r"(up to|as much as|at most|capped at|no more than|maximum of|as many as|not exceed\w*)[\s(]*[\$]?\s*$", re.I)
_MIN = re.compile(r"(at least|more than|over|above|exceeds?|minimum of)[\s(]*[\$]?\s*$", re.I)


_MAX_AFTER = re.compile(r"^[\s)]*(or less|or fewer|or lower|and under|and below|or under|maximum)", re.I)
_MIN_AFTER = re.compile(r"^[\s)]*(\+|or more|or higher|or greater|and up|and above|and over|or over|minimum)", re.I)


_MOVES = re.compile(r"\b(from|rais\w*|increas\w*|ris\w*|brought|grow\w*|climb\w*)\b[^.]{0,50}$", re.I)


def qualifier(before: str, after: str = "") -> str:
    """What the words around a figure say about it: "max" (up to $x, $x or less), "min" (at least $x, $x or more) or "".
    "up to" after a verb of movement ("raised the wage from $10 up to $18") says where it went, not a ceiling."""
    if (_MAX.search(before) and not _MOVES.search(before)) or _MAX_AFTER.search(after):
        return "max"
    return "min" if _MIN.search(before) or _MIN_AFTER.search(after) else ""


def sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if len(s.strip()) > 25]


class Corpus:
    """What has been published: which documents state each figure, and every sentence that states any."""

    def __init__(self, docs: list[dict], extra_text: str = ""):
        self.docs: dict[str, list[tuple[str, str | None]]] = defaultdict(list)
        self.by_key: dict[str, list[tuple[int, set[str], set[str], str]]] = defaultdict(list)  # figure -> (sentence index, words around it) for each time it is stated
        self.sents: list[tuple[str, str, str | None, set[str]]] = []  # (sentence, doc title, url, tokens)
        self.sent_keys: list[set[str]] = []
        self.doc_topic: list[set[str]] = []  # words of each document's title and web address
        self.doc_of: list[int] = []  # sentence index -> document index
        self.key_docs: dict[str, set[int]] = defaultdict(set)
        self.key_where: dict[str, list[tuple[int, int]]] = defaultdict(list)  # figure -> (document, sentence number in it)
        self.doc_sent_tokens: list[list[set[str]]] = []
        self.df: Counter = Counter()
        for di, d in enumerate(docs):
            self.doc_topic.append(_tokens(d["title"] + " " + (d.get("url") or "").rsplit("/", 1)[-1].replace("-", " ")))
            seen = set()
            self.doc_sent_tokens.append([])
            for sn, s in enumerate(sentences(" ".join(d["lines"]))):
                toks = _tokens(s)
                self.doc_sent_tokens[di].append(toks)
                figs = extract(s)
                if not figs:
                    continue
                for f in figs:
                    self.by_key[f["key"]].append((len(self.sents), _tokens(f["ctx"]), _tokens(f["pre"]), f["qual"]))
                    self.key_docs[f["key"]].add(di)
                    self.key_where[f["key"]].append((di, sn))
                    if f["key"] not in seen:
                        seen.add(f["key"])
                        self.docs[f["key"]].append((d["title"], d.get("url")))
                self.sent_keys.append({f["key"] for f in figs})
                self.doc_of.append(di)
                self.sents.append((s, d["title"], d.get("url"), toks))
                self.df.update(toks)
        self.docs_meta = [(d["title"], d.get("url")) for d in docs]
        for f in extract(extra_text):  # the Legislature's feed: bill and Act numbers are published there
            self.docs[f["key"]].append(("Legislature bill-status feed", None))

    def states(self, key: str) -> list[tuple[str, str | None]]:
        return self.docs.get(key, [])

    def weight(self, token: str) -> float:
        return math.log(1 + max(len(self.sents), 3000) / (1 + self.df[token]))  # a small test corpus must not shrink every weight

    def supporting(self, key: str, ctx: str, pre: str, others: set[str]) -> dict | None:
        """A published sentence that states this figure about the same thing: the words around it overlap the words around
        ours (enough rare ones), or it states another figure of our sentence that is a bill or Act number, or states one
        of our other figures and shares a word. A figure on its own proves nothing: with 43 reports in the corpus,
        "$999 million" and "6,000" each turn up somewhere unrelated."""
        mine, label = _tokens(ctx), _tokens(pre)
        best, best_score, via = None, 0.0, None
        for i, around, before, qual in self.by_key.get(key, []):
            text, title, url, toks = self.sents[i]
            shared = mine & around
            score = sum(self.weight(t) for t in shared) + 1.5 * sum(self.weight(t) for t in label & before)
            if len(shared) >= 2 and score >= MIN_TOPIC_SCORE and score > best_score:
                best, best_score, via = {"sentence": text, "title": title, "url": url, "score": round(score, 1), "qual": qual}, score, "words"
            elif via is None and others & self.sent_keys[i] and (any(k.startswith(("bill:", "act:")) for k in others & self.sent_keys[i]) or shared):
                best, via = {"sentence": text, "title": title, "url": url, "score": 0.0, "qual": qual}, "figures"
        return best

    def on_topic(self, key: str, topics: list[set[str]]) -> dict | None:
        """The weaker test: the figure is stated in a published passage ABOUT this section's subject: the document's
        title or web address carries the topic's words, or the sentences around the figure do. It cannot tell whether
        our sentence says the same thing about the figure, so a person should read these against the source."""
        for di, sn in self.key_where.get(key, ()):
            near = set().union(*self.doc_sent_tokens[di][max(0, sn - 3):sn + 4])
            if any(t and (t <= self.doc_topic[di] or t <= near) for t in topics):
                title, url = self.docs_meta[di]
                return {"title": title, "url": url}
        return None

    def closest(self, sentence: str, avoid: set[str], n: int = 2) -> list[dict]:
        """Published sentences that talk about the same thing as `sentence` (shared rare words), with their figures."""
        mine = _tokens(sentence)
        total = max(len(self.sents), 3000)
        best = []
        for s, title, url, toks in self.sents:
            shared = mine & toks
            if len(shared) < 3:
                continue
            score = sum(math.log(1 + total / (1 + self.df[t])) for t in shared) / math.sqrt(len(toks))
            best.append((score, s, title, url))
        best.sort(key=lambda b: -b[0])
        return [{"sentence": s, "title": t, "url": u, "figures": [f["raw"] for f in extract(s)][:4]} for _, s, t, u in best[:n]]


MIN_TOPIC_SCORE = 4.5  # summed rarity of the words a published sentence shares with ours; tuned on the cases in tests/test_figures.py
_STOP = set(("a an and are as at be but by for from has have in into is it its of on or our that the their there these they this to was were which with will would "
             "percent million billion thousand hawaii appleseed state year years more than also could about over under only most such each than into").split())


def _tokens(s: str) -> set[str]:
    words = (w[:-1] if w.endswith("s") and not w.endswith("ss") else w for w in re.findall(r"[a-z]{3,}", _APOS.sub("", s.lower())))
    return {w for w in words if w not in _STOP}


def _topics(sec: dict) -> list[set[str]]:
    base = re.sub(r"\(.*?\)", "", sec["title"])
    return [t for t in ([_tokens(a) for a in sec.get("aliases", [])] + [_tokens(base)]) if t]


def check(sections: list[dict], corpus: Corpus, allow: list[dict] | None = None) -> dict:
    """Report for `sections` ([{title, text, aliases?}]). Each figure is `sentence` (a published sentence says this about
    this), `topic` (only a report on the same subject states it: read it against the source), `accepted` (a person
    said it is fine, in content/figures.json), or `none` (no published source: the thing to fix or explain)."""
    ok = {(a["section"], a["figure"]): a for a in (allow or []) if a.get("reason", "").strip()}
    out = {"sections": [], "figures": 0, "sentence": 0, "qualifier": 0, "topic": 0, "accepted": 0, "none": 0}
    for sec in sections:
        rows, figs = [], extract(sec["text"])
        for f in figs:
            out["figures"] += 1
            others = {g["key"] for g in figs if g["key"] != f["key"] and g["sentence"] == f["sentence"]}
            if f["kind"] in ("bill", "act"):  # identifiers: being in a report or the bill feed is itself the evidence
                status, hit = ("sentence", corpus.states(f["key"])[:1]) if corpus.states(f["key"]) else ("none", None)
            elif (hit := corpus.supporting(f["key"], f["ctx"], f["pre"], others)):
                # "up to 30 percent" in the report, "30 percent" in ours, says something different
                status = "qualifier" if hit["qual"] and hit["qual"] != f["qual"] else "sentence"
            elif (hit := corpus.on_topic(f["key"], _topics(sec))):
                status = "topic"
            else:
                status, hit = "none", None
            if status in ("none", "topic", "qualifier") and (sec["title"], f["key"]) in ok:
                status = "accepted"
            out[status] += 1
            rows.append({"figure": f["raw"], "key": f["key"], "status": status, "sentence": f["sentence"], "source": hit,
                         "accepted_because": ok[(sec["title"], f["key"])]["reason"] if status == "accepted" else None,
                         "closest": corpus.closest(f["sentence"], set()) if status in ("none", "topic") else []})
        if rows:
            out["sections"].append({"title": sec["title"], "group": sec.get("group"), "figures": rows})
    return out


def render(report: dict, show_accepted: bool = False, show_matches: bool = False) -> str:
    lines = [f"{report['figures']} figures: {report['sentence']} stated in a published sentence about the same thing, "
             f"{report['qualifier']} where the published wording is qualified (up to, at least) and ours is not, "
             f"{report['topic']} only in a report on the same subject, {report['accepted']} accepted on purpose, "
             f"{report['none']} with no published source."]
    for want, head in (("sentence", "STATED IN A PUBLISHED SENTENCE (the one we matched, to read beside ours)"),
                       ("qualifier", "PUBLISHED WORDING IS QUALIFIED AND OURS IS NOT (fix the wording, or accept with a reason)"),
                       ("none", "NO PUBLISHED SOURCE (fix, or accept in content/figures.json with a reason)"),
                       ("topic", "ONLY IN A REPORT ON THE SAME SUBJECT (read against the source)"),
                       ("accepted", "ACCEPTED ON PURPOSE")):
        if (want == "accepted" and not show_accepted) or (want == "sentence" and not show_matches):
            continue
        block = []
        for sec in report["sections"]:
            rows = [r for r in sec["figures"] if r["status"] == want]
            if not rows:
                continue
            block.append(f"\n{sec['title']}")
            for r in rows:
                block.append(f"  {r['figure']}  [{r['key']}]")
                block.append(f"    ours:    {r['sentence'][:220]}")
                if r.get("source") and want == "topic":
                    block.append(f"    found in: {r['source']['title']}")
                if want in ("sentence", "qualifier") and isinstance(r.get("source"), dict) and r["source"].get("sentence"):
                    block.append(f"    published: {r['source']['sentence'][:220]}  ({r['source']['title']})")
                for c in r["closest"]:
                    block.append(f"    closest: {c['sentence'][:220]}  ({c['title']}; figures there: {', '.join(c['figures']) or 'none'})")
        if block:
            lines.append(f"\n== {head}")
            lines += block
    return "\n".join(lines)
