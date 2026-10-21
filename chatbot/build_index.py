#!/usr/bin/env python3
"""Build the public Q&A bot's knowledge index -> chatbot/worker/src/index.json.

What goes in (an allowlist, on purpose):
  core    content/about.md + practical.md + positions.md + generated bill outcomes.
          These ride in the system prompt, so they are always available.
  chunks  writing-bot/publications, blog-posts, testimony, chunked for BM25.
          Blog posts need a live URL (blog-sources.json); sample_ testimony and
          Google-Doc exports are left out.

What stays out: writing-bot/reference/ (internal meeting notes), anything
else under writing-bot/, and any position not approved when --public is set.

Retrieval is BM25 computed here, so the Worker only does lookups. The
tokenizer must match worker/src/tokenize.js; both are tested against
tokenizer_vectors.json.

    python3 chatbot/build_index.py            # pilot build: drafts included
    python3 chatbot/build_index.py --public   # launch build: approved only
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BASE_URL = "https://hiappleseed.org"
VENDOR = Path(os.environ.get("CHATBOT_VENDOR_DIR", HERE / "vendor"))
OUT_DEFAULT = HERE / "worker" / "src" / "index.json"


def _source_roots():
    """Where the corpus comes from: the vendored copy when there is one (vendor.py), else the live repo tree.
    CHATBOT_SOURCE=live|vendor forces one."""
    mode = os.environ.get("CHATBOT_SOURCE") or ("vendor" if (VENDOR / "MANIFEST.json").exists() else "live")
    if mode not in ("live", "vendor"):
        raise SystemExit(f"CHATBOT_SOURCE must be live or vendor, not {mode!r}")
    base = VENDOR if mode == "vendor" else ROOT
    if not (base / "writing-bot" / "sources.py").exists():
        raise SystemExit(f"{mode} source has no writing-bot/sources.py under {base}; run chatbot/vendor.py")
    if mode == "vendor" and (ROOT / "writing-bot" / "sources.py").exists():
        # A live tree is visible too: say so if the vendored copy has fallen behind it, rather than build stale quietly.
        sys.path.insert(0, str(HERE))
        import vendor as _vendor
        behind = _vendor.check(ROOT, VENDOR)
        if behind:
            print(f"WARNING: vendor/ is behind the live tree ({len(behind)} differences, e.g. {behind[0]}). "
                  "Run python3 chatbot/vendor.py, or CHATBOT_SOURCE=live to build from the live files.", file=sys.stderr)
    return mode, base / "writing-bot", base / "tax-fairness" / "data" / "bill-status.json"


SOURCE_MODE, WB, BILL_STATUS = _source_roots()

sys.path.insert(0, str(WB))
import sources  # noqa: E402  (writing-bot/sources.py: titles, URLs, stances)
sys.path.insert(0, str(HERE))
import figures as fg  # noqa: E402  (cross-checks the figures in positions.md against the published corpus)
import approval  # noqa: E402  (approvals are of exact text)

# ---------------------------------------------------------------- tokenizer
# Keep in lockstep with worker/src/tokenize.js (tokenizer_vectors.json tests both).
STOPWORDS = frozenset(
    "a an and are as at be but by for from has have how i if in into is it its of on or "
    "our so than that the their them then there these they this to was we were what when "
    "where which who why will with you your do does did can could would should about "
    "tell me please".split()
)
_BILL = re.compile(r"\b(hb|sb|hr|sr|hcr|scr|gm)\s*(\d{1,4})\b")
_APOS = re.compile("[ʻ’‘'`]")


def tokenize(text: str) -> list[str]:
    t = unicodedata.normalize("NFKD", text).lower()
    t = "".join(c for c in t if not unicodedata.category(c).startswith("M"))
    t = _APOS.sub("", t)
    t = _BILL.sub(r"\1\2", t)
    out = []
    for w in re.findall(r"[a-z0-9]+", t):
        if len(w) < 2 or w in STOPWORDS:
            continue
        if len(w) > 4 and re.search(r"(xes|ches|shes|sses)$", w):
            w = w[:-2]                      # taxes -> tax, branches -> branch
        elif len(w) > 4 and w.endswith("ies"):
            w = w[:-3] + "y"                # policies -> policy, priorities -> priority
        elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        out.append(w)
    return out


# ------------------------------------------------------------- core content
_COMMENT = re.compile(r"<!--\s*(\w+):\s*(.*?)\s*-->")


def _abs(url: str | None) -> str | None:
    if not url:
        return None
    return url if url.startswith("http") else BASE_URL + url


def parse_sections(path: Path, group_level: int = 2, item_level: int = 3):
    """Split a content file into sections. A '##' heading starts a group; an item
    is a '###' section, or the '##' section itself when it has no '###' children.
    Metadata comments (<!-- status: .. -->, <!-- url: .. -->) are lifted out."""
    text = path.read_text(encoding="utf-8")
    heads = list(re.finditer(r"^(#{2,3}) (.+)$", text, re.M))
    items, group = [], None
    for i, h in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        body = text[h.end():end]
        level, title = len(h.group(1)), h.group(2).strip()
        if level == group_level:
            group = title
            nxt = heads[i + 1] if i + 1 < len(heads) else None
            if nxt is not None and len(nxt.group(1)) == item_level:
                continue  # group heading only; its ### children are the items
        meta = {k: v for k, v in _COMMENT.findall(body)}
        body = _COMMENT.sub("", body).strip()
        if not body:
            continue
        aliases = [a.strip() for a in meta.get("aliases", "").split(";") if a.strip()]
        research = [f"{BASE_URL}/publications/{x.strip()}" for x in meta.get("research", "").split(",") if x.strip()]
        graphics = [g.strip() for g in meta.get("graphic", "").split(",") if g.strip()]
        items.append({"group": group, "title": title, "text": body, "research": research, "aliases": aliases,
                      "graphics": graphics, "url": _abs(meta.get("url")), "status": meta.get("status", ""), "reviewed": meta.get("reviewed", "")})
    return items


BILL_SNAPSHOT = HERE / "content" / "bill-status-snapshot.json"


def session_year() -> int:
    """The legislative session this content covers (content/session.json); see freshness in the README."""
    return int(json.loads((HERE / "content" / "session.json").read_text(encoding="utf-8"))["covered"])


def _usable_bills(d: dict) -> tuple[dict, dict]:
    """(bill -> {year, date, description} for its latest recorded action, bill -> issue area). A bill whose fetch failed has
    no `updates` and is left out: the feed is refreshed by a scheduled job and capitol.hawaii.gov sometimes answers it 403."""
    area = {}
    for tr in d.get("trackers", []):
        for n in tr.get("hbNumbers", []):
            area[f"HB{n}"] = tr["issueArea"]
        for n in tr.get("sbNumbers", []):
            area[f"SB{n}"] = tr["issueArea"]
    out = {}
    for key, v in d.get("bills", {}).items():
        ups = sorted(v.get("updates") or [], key=lambda u: u["date"], reverse=True)
        if ups:
            out[key] = {"year": v["year"], "date": ups[0]["date"][:10], "description": re.sub(r"\s+", " ", ups[0]["description"]).strip()}
    return out, area


def bill_outcomes() -> dict | None:
    """The generated "2026 bill outcomes" section. Live feed where it has data; for any bill it has none for (a failed
    fetch), the last good copy committed in content/bill-status-snapshot.json (snapshot_bills.py), so one bad refresh
    does not erase what the assistant knows about a bill."""
    live, area, gen = {}, {}, ""
    if BILL_STATUS.exists():
        d = json.loads(BILL_STATUS.read_text(encoding="utf-8"))
        live, area = _usable_bills(d)
        gen = d.get("generatedAt", "")[:10]
    snap, snap_gen = {}, ""
    if BILL_SNAPSHOT.exists():
        sd_ = json.loads(BILL_SNAPSHOT.read_text(encoding="utf-8"))
        snap, snap_gen = sd_["bills"], sd_.get("generatedAt", "")[:10]
        area = {**sd_.get("areas", {}), **area}
    merged = {**{k: v for k, v in snap.items() if k not in live}, **live}
    if not merged:
        return None
    fallback = sorted(k for k in merged if k not in live)
    if fallback:
        print(f"WARNING: the bill-status feed has no data for {len(fallback)} bills ({', '.join(fallback[:4])}{'...' if len(fallback) > 4 else ''}); "
              f"using the committed snapshot from {snap_gen}", file=sys.stderr)
    lines = [f"- {key} ({v['year']}), tracked under \"{area.get(key, 'tax fairness')}\": last recorded action {v['date']}: {v['description']}"
             for key, v in sorted(merged.items())]
    pulled = snap_gen if fallback else gen  # when any bill is from the snapshot, say so with the older date
    text = (
        f"Status of the bills Hawaiʻi Appleseed tracked in the {session_year()} session, from the "
        f"Legislature's own feed (data pulled {pulled}). The {session_year()} regular session has ended. "
        "A bill whose last recorded action is a referral, a deferral, or a hearing notice "
        "shows no enactment in this data; an Act number means it became law. This feed can "
        "lag, so the Legislature's website (capitol.hawaii.gov) is the authority on final status.\n\n"
        + "\n".join(lines)
    )
    return {"group": "Bill outcomes", "title": f"{session_year()} bill outcomes",
            "text": text, "url": None, "status": "approved: generated from Legislature data"}


# ----------------------------------------------------------------------- faq
_FACT = [r"\(\d{3}\) \d{3}-\d{4}", r"[\w.+-]+@[\w-]+\.[\w.-]+", r"\$\d[\d,]*", r"\b(?:19|20)\d\d\b", r"\b\d{5}\b"]


def load_faq(core_urls: set[str], fact_text: str) -> list[dict]:
    """content/faq.json: stock answers. Checked hard, because they go out unreviewed by a model: sources must be real
    pages in the core content, citation numbers must line up, the voice rules must hold, and every phone number, email,
    dollar amount, year, and zip code must already appear in about.md or practical.md."""
    entries = json.loads((HERE / "content" / "faq.json").read_text(encoding="utf-8"))["entries"]
    seen, out = set(), []
    for e in entries:
        i = e["id"]
        if i in seen:
            raise SystemExit(f"faq: duplicate id {i}")
        seen.add(i)
        if e.get("internal"):  # used by the Worker's own logic (e.g. the stance deferral), never matched by phrasing
            e.setdefault("variants", [])
        elif not e.get("variants") or not all(isinstance(v, str) and v.strip() for v in e["variants"]):
            raise SystemExit(f"faq {i}: needs at least one non-empty variant")
        a = e["answer"]
        for src in e["sources"]:
            if src["url"] not in core_urls:
                raise SystemExit(f"faq {i}: source {src['url']} is not a page in content/about.md or practical.md")
        used = {int(n) for n in re.findall(r"\[(\d+)\]", a)}
        if used != set(range(1, len(e["sources"]) + 1)):
            raise SystemExit(f"faq {i}: citation markers {sorted(used)} do not match its {len(e['sources'])} source(s)")
        if "!" in a or "%" in a or re.search(r"\bHawaii\b(?!\.[A-Za-z])", a) or " \u2014 " in a:
            raise SystemExit(f"faq {i}: voice rule broken (no exclamation points, 'percent' not %, ʻokina on Hawaiʻi, unspaced em dashes)")
        for pat in _FACT:
            for m in re.findall(pat, a):
                if m not in fact_text:
                    raise SystemExit(f"faq {i}: {m!r} is not in content/about.md or practical.md")
        out.append({"id": i, "variants": e["variants"], "answer": a, "graphic": e.get("graphic"),
                    "status": e.get("status", "draft"), "reviewed": e.get("reviewed", ""), "hash": approval.faq_hash(a, [src["url"] for src in e["sources"]]),
                    "sources": [{"n": n, "title": src["title"], "url": src["url"], "year": None, "pdf": None} for n, src in enumerate(e["sources"], 1)]})
    return out


# -------------------------------------------------------------------- contact
def contact_block(core: list[dict]) -> dict:
    """How a visitor reaches the office, from the "Contact the office" section of practical.md (which came from the live
    Contact page): the page, email, and phone the "ask a person" button offers. One source, so the button cannot drift
    from what the assistant tells people in words."""
    sec = next((c for c in core if c["title"] == "Contact the office"), None)
    if not sec:
        raise SystemExit('content/practical.md has no "Contact the office" section')
    email = re.search(r"[\w.+-]+@hiappleseed\.org", sec["text"])
    phone = re.search(r"\((\d{3})\) (\d{3})-(\d{4})", sec["text"])
    if not (email and phone and sec.get("url")):
        raise SystemExit('"Contact the office" needs an @hiappleseed.org email, a (808) 555-0100 style phone, and a url')
    return {"email": email.group(0), "phone": phone.group(0), "tel": "+1" + "".join(phone.groups()), "page": sec["url"]}


# ------------------------------------------------------------------ graphics
_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")
_GRAPHIC_TYPES = {"bars", "stats", "timeline", "scoreboard", "slices"}
_TONES = {"muted"}


_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
_ONES = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9}
_SPELLED = re.compile(r"\b(" + "|".join(_TENS) + r")(?:-(" + "|".join(_ONES) + r"))?\b", re.I)


def _nums(s: str) -> set[str]:
    """Numbers in a string, as digits: "$1,000" -> 1000, and a spelled-out "Sixty-six" -> 66 (the house style spells some
    out). Single spelled digits and teens are left alone: "one" is in nearly every sentence and would prove nothing."""
    out = {m.rstrip(",").replace(",", "") for m in _NUM.findall(s)}
    for t, o in _SPELLED.findall(s):
        out.add(str(_TENS[t.lower()] + (_ONES[o.lower()] if o else 0)))
    return out


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("\u2019", "'")).lower()


def _slice_rows(g: dict) -> dict:
    """A made-up marginal-rate example, computed here so no typed total can disagree with its parts."""
    price, slices = g["price"], g["slices"]
    rows, lo, total = [], 0, 0
    money = lambda n: f"${n // 1_000_000:,} million" if n % 1_000_000 == 0 else f"${n:,}"
    for i, sl in enumerate(slices):
        seg = sl["to"] - lo
        tax = seg * sl["rate"]
        total += tax
        word = "First" if i == 0 else "Last" if i == len(slices) - 1 else "Next"
        rows.append({"label": f"{word} {money(seg)}, taxed at {sl['rate'] * 100:g}%", "value": round(tax), "display": f"${tax:,.0f}"})
        lo = sl["to"]
    if lo != price:
        raise SystemExit(f"graphic {g['id']}: slices end at {lo}, not at the price {price}")
    flat = price * slices[-1]["rate"]
    rows.append({"label": "Total, taxed marginally", "value": round(total), "display": f"${total:,.0f}"})
    rows.append({"label": f"Same sale, top rate on all {money(price)}", "value": round(flat), "display": f"${flat:,.0f}", "tone": "muted"})
    return {**{k: v for k, v in g.items() if k not in ("slices", "price")}, "type": "bars",
            "unit": f"tax owed on a {money(price)} sale", "rows": rows}


def _proofs(r: dict) -> list[str]:
    p = r.get("proof")
    return [p] if isinstance(p, str) else list(p or [])


def _unproven(g: dict, text: str) -> str | None:
    """Why `text` (the approved prose, normalized) does not back this graphic, or None when it does. Every row quotes the
    phrase(s) it rests on, and every number the row shows must be in those phrases; the title, unit and note may only use
    numbers the graphic's own proofs carry. A bar's label must say its value."""
    rows = g.get("rows") or g.get("items") or []
    if not rows:
        return "no rows"
    pool: set[str] = set()
    for r in rows:
        name = r.get("label") or r.get("item") or r.get("when") or r.get("value")
        ps = _proofs(r)
        if not ps:
            return f"row {name!r} has no proof"
        for p in ps:
            if _norm(p) not in text:
                return f"proof {p!r} is not in the approved text"
        allowed = set().union(*(_nums(p) for p in ps))
        pool |= allowed
        for k, v in r.items():
            if k in ("proof", "tone") or isinstance(v, (int, float)):
                continue
            for n in _nums(str(v)):
                if n not in allowed:
                    return f"the number {n} in {v!r} is not in the proof for row {name!r}"
        if "display" in r and "value" in r:
            first = _NUM.search(r["display"])
            if not first or float(first.group().rstrip(",").replace(",", "")) != float(r["value"]):
                return f"label {r['display']!r} does not match value {r['value']}"
    for p in g.get("proofs", []):
        if _norm(p) not in text:
            return f"proof {p!r} is not in the approved text"
        pool |= _nums(p)
    for k in ("title", "unit", "note"):
        for n in _nums(g.get(k, "")):
            if n not in pool:
                return f"the number {n} in the {k} is in none of its proofs"
    return None


def load_graphics(known_urls: set[str], catalog: dict, vetted: str, position_ids: set[str], titles: set[str],
                  public_text: str | None = None, public_titles: set[str] | None = None, skipped: Counter | None = None) -> list[dict]:
    """content/graphics.json: the only graphics the assistant can show. They are data the page draws, never markup the
    model writes. Checked hard against ALL the approved-or-draft position text (`vetted`): each figure needs `proof` phrases
    that appear word for word, sources must be real pages, aliases (two topic words at least) belong to one graphic only,
    and a made-up illustration must say so. A --public build then drops any graphic whose proofs are not in the text of
    the APPROVED positions (`public_text`), or whose `needs` positions are not approved."""
    graphics = json.loads((HERE / "content" / "graphics.json").read_text(encoding="utf-8"))["graphics"]
    text = _norm(vetted)
    seen, aliases, out = set(), {}, []
    for g in graphics:
        i = g["id"]
        if i in seen:
            raise SystemExit(f"graphic: duplicate id {i}")
        seen.add(i)
        if g["type"] not in _GRAPHIC_TYPES:
            raise SystemExit(f"graphic {i}: unknown type {g['type']!r}")
        if not g.get("title"):
            raise SystemExit(f"graphic {i}: needs a title")
        illus = bool(g.get("illustration"))
        if illus and "made-up" not in g.get("note", ""):
            raise SystemExit(f"graphic {i}: an illustration must say its numbers are made-up in its note")
        if g["type"] == "slices" and not illus:
            raise SystemExit(f"graphic {i}: slices are for made-up illustrations only")
        for t in g.get("needs", []):
            if t not in titles:
                raise SystemExit(f"graphic {i}: needs a position titled {t!r}, which does not exist")
        src = g.get("source") or {}
        url = _abs(src.get("url"))
        if url not in known_urls and url not in catalog:
            raise SystemExit(f"graphic {i}: source {url} is not a page in the core content or a published report")
        title = catalog[url]["t"] if url in catalog else src.get("title")
        if not title:
            raise SystemExit(f"graphic {i}: source needs a title")
        al = g.get("aliases") or []
        if not al:
            raise SystemExit(f"graphic {i}: needs aliases")
        for a in al:
            toks = frozenset(tokenize(a))
            if len(toks) < 2:
                raise SystemExit(f"graphic {i}: alias {a!r} is too general (two topic words at least)")
            if aliases.get(toks, i) != i:
                raise SystemExit(f"graphic {i}: alias {a!r} also belongs to {aliases[toks]}")
            aliases[toks] = i
        for r in g.get("rows", []) + g.get("items", []):
            if r.get("tone") not in (None, *_TONES):
                raise SystemExit(f"graphic {i}: unknown tone {r['tone']!r}")
        if not illus:
            why = _unproven(g, text)
            if why:
                raise SystemExit(f"graphic {i}: {why}")
        if public_text is not None:
            gone = [t for t in g.get("needs", []) if t not in (public_titles or set())]
            if gone or (not illus and _unproven(g, _norm(public_text))):
                if skipped is not None:
                    skipped["graphic resting on an unapproved position (public build)"] += 1
                continue
        spec = _slice_rows(g) if g["type"] == "slices" else dict(g)
        for k in ("proofs", "needs", "_comment"):
            spec.pop(k, None)
        for r in spec.get("rows", []) + spec.get("items", []):
            r.pop("proof", None)
        spec["source"] = {"title": title, "url": url}
        spec["auto"] = bool(g.get("auto"))
        out.append(spec)
    for pid in position_ids:
        if pid not in seen:
            raise SystemExit(f"a position or ready-made answer points at graphic {pid!r}, which is not in content/graphics.json")
    return out


# ------------------------------------------------------------------- research
AREAS = ["Affordable Housing", "Food Equity", "Wages & Labor", "Transportation Equity", "Taxes & Budget"]


def _topics() -> dict:
    """content/topics.json: which issue area(s) each report belongs to. Checked at build time."""
    return json.loads((HERE / "content" / "topics.json").read_text(encoding="utf-8"))["reports"]


def pub_catalog() -> dict:
    """Every published report, keyed by live URL: title, year, date, PDF link, issue areas, what it is about."""
    topics = _topics()
    cat = {}
    for p in sorted((WB / "publications").glob("*.txt")):
        ref = sources.source_ref(f"publications/{p.name}")
        if not ref["url"]:
            continue
        slug = ref["url"].rstrip("/").split("/")[-1]
        t = topics.get(slug, {})
        for a in t.get("areas", []):
            if a not in AREAS:
                raise SystemExit(f"content/topics.json: {slug}: unknown issue area {a!r}")
        m = re.match(r"(20\d\d)-(\d\d)-(\d\d)", p.name)
        cat[ref["url"]] = {"t": sources.source_title(f"publications/{p.name}"),
                           "y": int(m.group(1)) if m else None,
                           "d": f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None,
                           "p": ref["pdf"], "a": t.get("areas", []), "w": t.get("about")}
    unknown = sorted(set(topics) - {u.rstrip("/").split("/")[-1] for u in cat})
    if unknown:
        raise SystemExit(f"content/topics.json names reports that do not exist: {unknown}")
    return cat


def _label(p: dict) -> str:
    return f"{p['t']} ({p['w']})" if p.get("w") and p["w"] != "session review" else p["t"]


def _month(d: str | None) -> str:
    if not d:
        return ""
    return datetime.strptime(d, "%Y-%m-%d").strftime("%B %Y")


def research_sections(catalog: dict) -> list[dict]:
    """Generated 'Latest research' and 'Research by issue area' sections, so 'what is your newest report?' and
    'what do you have on housing?' are answered from the real list, newest first, never from keyword luck."""
    reports = sorted(catalog.values(), key=lambda p: (p["d"] or "", p["t"]), reverse=True)
    latest = "\n".join(f"- {_label(p)}, {_month(p['d'])}" for p in reports[:8])
    by_area = []
    for area in AREAS:
        rs = [p for p in reports if area in p["a"]][:5]
        by_area.append(f"{area}: " + "; ".join(f"{_label(p)} ({p['y']})" for p in rs))
    return [
        {"group": "Research", "title": "Latest research", "url": f"{BASE_URL}/research", "research": [], "pos": False,
         "text": "Hawaiʻi Appleseed's most recent reports, newest first. The Research page lists all of them, each with a PDF.\n" + latest},
        {"group": "Research", "title": "Research by issue area", "url": f"{BASE_URL}/research", "research": [], "pos": False,
         "text": "The newest reports in each issue area (Policy in Perspective, the annual look back at each legislative session, covers all five).\n" + "\n".join(f"- {a}" for a in by_area)},
    ]


# ------------------------------------------------------------------- corpus
def _clean_lines(text: str):
    for ln in text.splitlines():
        ln = ln.strip().lstrip("﻿")
        if not ln or re.fullmatch(r"[_=\-\s]{4,}", ln) or re.match(r"^Page\s+of\b", ln):
            continue
        yield ln


def _hard_wrapped(lines: list[str]) -> bool:
    """PDF-derived text breaks lines mid-sentence (median line well under a
    sentence); blog and testimony text keeps one paragraph per line."""
    if len(lines) < 8:
        return False
    sizes = sorted(len(l.split()) for l in lines)
    return sizes[len(sizes) // 2] < 14


def chunk(lines: list[str], target: int = 140, hard: int = 230) -> list[str]:
    lines = [re.sub(r"\s+", " ", l).strip() for l in lines if l.strip()]
    sep = "\n"
    if _hard_wrapped(lines):
        lines = re.split(r"(?<=[.!?])\s+", " ".join(lines))
        sep = " "
    out, cur, n = [], [], 0
    for ln in lines:
        w = len(ln.split())
        if w > hard:  # a very long paragraph: split on sentences, then on words for table-like runs
            pieces = []
            for sent in re.split(r"(?<=[.!?])\s+", ln):
                words = sent.split()
                pieces += [" ".join(words[i:i + target]) for i in range(0, len(words), target)] if len(words) > hard else [sent]
            for s in pieces:
                sw = len(s.split())
                if n + sw > target and cur:
                    out.append(sep.join(cur)); cur, n = [], 0
                cur.append(s); n += sw
            continue
        cur.append(ln); n += w
        if n >= target:
            out.append(sep.join(cur)); cur, n = [], 0
    if cur:
        tail = sep.join(cur)
        if out and n < 30:
            out[-1] += sep + tail
        else:
            out.append(tail)
    return out


def _year(rel: str, text: str) -> int | None:
    m = re.search(r"/(20\d\d)/", rel) or re.match(r"[a-z\-]+/(20\d\d)-\d\d-\d\d_", rel)
    if m:
        return int(m.group(1))
    m = re.search(r"\b(20[12]\d)\b", text[:300])
    return int(m.group(1)) if m else None


def corpus_docs(skipped: Counter):
    for kind, pattern in (("publication", "publications/*.txt"),
                          ("blog", "blog-posts/*/*.txt"),
                          ("testimony", "testimony/*/*.txt")):
        for p in sorted(WB.glob(pattern)):
            rel = str(p.relative_to(WB))
            text = p.read_text(encoding="utf-8", errors="ignore")
            ref = sources.source_ref(rel)
            if kind == "testimony" and p.name.startswith("sample_"):
                skipped["sample testimony"] += 1; continue
            if kind == "blog":
                if not ref["url"]:
                    skipped["blog without a live URL"] += 1; continue
                if re.search(r"^\[[a-z]\]", text, re.M):
                    skipped["blog with doc-comment markers"] += 1; continue
            head = [l.strip().lstrip("\ufeff") for l in text.splitlines() if l.strip()][:3]
            if any(re.match(r"(?i)^draft\b", l) for l in head):
                skipped["marked DRAFT (may not match the published text)"] += 1; continue
            title = sources.source_title(rel)
            stance = None
            if kind == "testimony":
                title = f"Hawaiʻi Appleseed testimony: {title}"
                stance = sources.document_stance(rel)
            if kind == "publication":
                body = text.split("=" * 10, 1)[-1]
            else:
                body = text
            lines = list(_clean_lines(body))
            if kind == "blog" and lines and lines[0] == sources.source_title(rel):
                lines = lines[1:]
            yield {"kind": kind, "title": title, "url": ref["url"], "stance": stance,
                   "year": _year(rel, text), "lines": lines, "rel": rel}


# -------------------------------------------------------------------- build
_FIGURE_CORPORA: dict = {}


def check_figures(core: list[dict], docs: list[dict], public: bool) -> dict:
    """Cross-check the figures in the positions in this build against the published corpus (figures.py). A public build
    refuses to ship an approved position with a figure nobody has accepted; a pilot build only reports."""
    allow_path = HERE / "content" / "figures.json"
    allow = json.loads(allow_path.read_text(encoding="utf-8")).get("allow", []) if allow_path.exists() else []
    feed = BILL_STATUS.read_text(encoding="utf-8") if BILL_STATUS.exists() else ""
    key = (hash(tuple(d["rel"] for d in docs)), len(feed))  # the corpus is the slow part; tests build many times
    if key not in _FIGURE_CORPORA:
        _FIGURE_CORPORA[key] = fg.Corpus(docs, feed)
    report = fg.check([c for c in core if c.get("pos")], _FIGURE_CORPORA[key], allow)
    bad = [(sec["title"], r) for sec in report["sections"] for r in sec["figures"] if r["status"] in ("none", "qualifier")]
    if public and bad:
        lines = "\n".join(f"  {t}: {r['figure']} ({r['status']})" for t, r in bad)
        raise SystemExit(f"figures in approved positions that no published sentence backs, or that drop a published qualifier "
                         f"(run python3 chatbot/check_figures.py; fix the wording or accept the figure in content/figures.json with a reason):\n{lines}")
    report["unexplained"] = len(bad)
    return report


def _source_info() -> dict:
    """Which corpus snapshot this index was built from, shown by the Worker's /health."""
    if SOURCE_MODE == "vendor":
        m = json.loads((VENDOR / "MANIFEST.json").read_text(encoding="utf-8"))
        return {"mode": "vendor", "commit": m.get("source_commit"), "vendored_at": m.get("vendored_at")}
    try:
        sha = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    except Exception:  # noqa: BLE001
        sha = None
    return {"mode": "live", "commit": sha, "vendored_at": None}


def build(public: bool) -> dict:
    skipped: Counter = Counter()
    core, statuses, drafts = [], [], []
    for fname in ("about.md", "practical.md", "positions.md"):
        for it in parse_sections(HERE / "content" / fname):
            if fname == "positions.md" and it["group"] != "Topics with no stated public position":
                statuses.append((it["title"], it["status"] or "(none)"))
                ok, why = approval.judge(it["status"], it["reviewed"], approval.position_hash(it["title"], it["text"]))
                if public and not ok:
                    skipped[f"position {why} (public build)"] += 1
                    drafts.append(it)
                    continue
            it["src"] = fname
            it["pos"] = fname == "positions.md" and it["group"] != "Topics with no stated public position"
            core.append(it)
    bo = bill_outcomes()
    if bo:
        bo["research"] = []
        bo["pos"] = False
        core.append(bo)
    catalog = pub_catalog()
    core += research_sections(catalog)
    facts = "\n".join(c["text"] for c in core if c.get("src") in ("about.md", "practical.md"))
    faq_all = load_faq({c["url"] for c in core if c.get("src") in ("about.md", "practical.md") and c["url"]}, facts)
    faq = faq_all
    if public:  # a ready-made answer ships only if staff approved these exact words; the question then goes to the model
        faq = []
        for e in faq_all:
            ok, why = approval.judge(e["status"], e["reviewed"], e["hash"])
            if ok:
                faq.append(e)
            else:
                skipped[f"ready-made answer {why} (public build)"] += 1
    # Graphics are proven against ALL the position text (drafts included), so a bad graphic fails the pilot build too; a
    # public build then ships only the ones the approved text alone backs.
    prose = lambda items: "\n".join(c["text"] for c in items if c.get("src") in ("about.md", "practical.md", "positions.md"))
    everything = [c for c in core if c.get("src")] + [dict(d, src="positions.md", pos=True) for d in drafts]
    wanted = {g for c in everything for g in c.get("graphics", [])} | {e["graphic"] for e in faq_all if e.get("graphic")}
    graphics = load_graphics({c["url"] for c in core + drafts if c["url"]}, catalog, prose(everything), wanted,
                             {c["title"] for c in everything if c.get("pos")},
                             public_text=prose(core) if public else None,
                             public_titles={c["title"] for c in core if c.get("pos")}, skipped=skipped)
    if public:
        shipped = {g["id"] for g in graphics}
        for c in core:
            for gid in c.get("graphics", []):
                if gid not in shipped:
                    raise SystemExit(f"{c['title']}: its graphic {gid!r} is not backed by the approved text alone")
        for e in faq:
            if e.get("graphic") and e["graphic"] not in shipped:
                raise SystemExit(f"ready-made answer {e['id']}: its graphic {e['graphic']!r} is not backed by the approved text alone")
    for i, it in enumerate(core, 1):
        it["id"] = f"C{i}"
        it.pop("status", None)
        it.pop("reviewed", None)
        it.pop("src", None)
        for u in it["research"]:
            if u not in catalog:
                raise SystemExit(f"{it['title']}: research link {u} is not a published report in writing-bot/publications")

    chunks, dl, post = [], [], {}
    docs = []
    for d in corpus_docs(skipped):
        docs.append(d)
        for piece in chunk(d["lines"]):
            ci = len(chunks)
            chunks.append({"t": d["title"], "u": d["url"], "k": d["kind"],
                           "y": d["year"], "s": d["stance"], "x": piece})
            toks = tokenize(d["title"] + " " + piece)
            dl.append(len(toks))
            for term, tf in Counter(toks).items():
                post.setdefault(term, []).extend([ci, tf])
    n = len(chunks)
    figure_report = check_figures(core, docs, public)
    skipped["report without a topic in content/topics.json"] = sum(1 for p in catalog.values() if not p["a"])
    if not skipped["report without a topic in content/topics.json"]:
        del skipped["report without a topic in content/topics.json"]
    return {
        "version": 1,
        "source": _source_info(),
        "built": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "public": public,
        "core": core,
        "faq": [{k: v for k, v in e.items() if k not in ("status", "reviewed", "hash")} for e in faq],
        "graphics": graphics,
        "session": {"covered": session_year()},
        "contact": contact_block(core),
        "pubs": catalog,
        "chunks": chunks,
        "bm25": {"n": n, "avgdl": round(sum(dl) / max(n, 1), 3), "dl": dl, "post": post},
        "_report": {"skipped": dict(skipped), "position_status": statuses, "figures": figure_report,
                    "untopiced": sorted(p["t"] for p in catalog.values() if not p["a"])},
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--public", action="store_true", help="launch build: approved positions only")
    ap.add_argument("--out", type=Path, default=OUT_DEFAULT)
    ap.add_argument("--strict", action="store_true",
                    help="exit 2 if a published report has no entry in content/topics.json or a position has an unexplained figure (the weekly corpus check)")
    a = ap.parse_args()
    if a.public:
        # The fixed replies and page text have no fallback (no model to hand them to), so a public build needs every one approved.
        import fixed
        bad = fixed.problems()
        if bad:
            print("A public build needs every fixed reply and page text approved (in the sign-off review, Part 3; content/fixed.json):", file=sys.stderr)
            for line in bad:
                print(f"  {line}", file=sys.stderr)
            return 3
    idx = build(a.public)
    rep = idx.pop("_report")
    a.out.parent.mkdir(parents=True, exist_ok=True)
    tmp = a.out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(idx, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(a.out)
    kinds = Counter(c["k"] for c in idx["chunks"])
    try:
        shown = a.out.resolve().relative_to(ROOT)
    except ValueError:
        shown = a.out
    print(f"wrote {shown}  {a.out.stat().st_size/1e6:.2f} MB  "
          f"({'public' if a.public else 'pilot'} build, corpus from {SOURCE_MODE})")
    print(f"  research catalog: {len(idx['pubs'])} reports; {sum(1 for c in idx['core'] if c['research'])} sections link curated research")
    print(f"  ready-made answers: {len(idx['faq'])} ({sum(len(e['variants']) for e in idx['faq'])} phrasings)")
    print(f"  graphics: {len(idx['graphics'])} ({sum(1 for c in idx['core'] if c.get('graphics'))} positions attach one)")
    print(f"  core sections: {len(idx['core'])}   chunks: {len(idx['chunks'])} {dict(kinds)}")
    print(f"  bm25 terms: {len(idx['bm25']['post'])}   avg chunk length: {idx['bm25']['avgdl']} tokens")
    for k, v in rep["skipped"].items():
        print(f"  skipped {v}: {k}")
    fr = rep["figures"]
    print(f"  figures in positions: {fr['figures']} checked against the published corpus; {fr['sentence']} backed by a published sentence, "
          f"{fr['accepted']} accepted by a person, {fr['topic']} only in a report on the subject, {fr['unexplained']} unexplained")
    if fr["unexplained"]:
        print("  WARNING: run python3 chatbot/check_figures.py (a --public build refuses these)")
    if rep["untopiced"]:
        print(f"  NEW REPORTS WITHOUT A TOPIC (add each to content/topics.json so it appears under its issue area): {'; '.join(rep['untopiced'])}")
    appr = sum(1 for _, s in rep["position_status"] if s.startswith("approved"))
    print(f"  positions: {appr} approved, {len(rep['position_status']) - appr} draft")
    return 2 if a.strict and (rep["untopiced"] or fr["unexplained"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
