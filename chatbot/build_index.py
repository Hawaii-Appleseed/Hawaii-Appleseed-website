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
        if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
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
        research = [f"{BASE_URL}/publications/{x.strip()}" for x in meta.get("research", "").split(",") if x.strip()]
        items.append({"group": group, "title": title, "text": body, "research": research,
                      "url": _abs(meta.get("url")), "status": meta.get("status", "")})
    return items


def bill_outcomes() -> dict | None:
    if not BILL_STATUS.exists():
        return None
    d = json.loads(BILL_STATUS.read_text(encoding="utf-8"))
    area = {}
    for tr in d.get("trackers", []):
        for n in tr.get("hbNumbers", []):
            area[f"HB{n}"] = tr["issueArea"]
        for n in tr.get("sbNumbers", []):
            area[f"SB{n}"] = tr["issueArea"]
    lines = []
    for key, v in sorted(d["bills"].items()):
        ups = sorted(v["updates"], key=lambda u: u["date"], reverse=True)
        if not ups:
            continue
        last = ups[0]
        desc = re.sub(r"\s+", " ", last["description"]).strip()
        lines.append(f"- {key} ({v['year']}), tracked under \"{area.get(key, 'tax fairness')}\": "
                     f"last recorded action {last['date'][:10]}: {desc}")
    gen = d.get("generatedAt", "")[:10]
    text = (
        "Status of the bills Hawaiʻi Appleseed tracked in the 2026 session, from the "
        f"Legislature's own feed (data pulled {gen}). The 2026 regular session has ended. "
        "A bill whose last recorded action is a referral, a deferral, or a hearing notice "
        "shows no enactment in this data; an Act number means it became law. This feed can "
        "lag, so the Legislature's website (capitol.hawaii.gov) is the authority on final status.\n\n"
        + "\n".join(lines)
    )
    return {"group": "Bill outcomes", "title": "2026 bill outcomes",
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
        if not e.get("variants") or not all(isinstance(v, str) and v.strip() for v in e["variants"]):
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
        out.append({"id": i, "variants": e["variants"], "answer": a,
                    "sources": [{"n": n, "title": src["title"], "url": src["url"], "year": None, "pdf": None} for n, src in enumerate(e["sources"], 1)]})
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
        {"group": "Research", "title": "Latest research", "url": f"{BASE_URL}/research", "research": [],
         "text": "Hawaiʻi Appleseed's most recent reports, newest first. The Research page lists all of them, each with a PDF.\n" + latest},
        {"group": "Research", "title": "Research by issue area", "url": f"{BASE_URL}/research", "research": [],
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
    core, statuses = [], []
    for fname in ("about.md", "practical.md", "positions.md"):
        for it in parse_sections(HERE / "content" / fname):
            if fname == "positions.md" and it["group"] != "Topics with no stated public position":
                statuses.append((it["title"], it["status"] or "(none)"))
                if public and not it["status"].startswith("approved"):
                    skipped["position not approved (public build)"] += 1
                    continue
            it["src"] = fname
            core.append(it)
    bo = bill_outcomes()
    if bo:
        bo["research"] = []
        core.append(bo)
    catalog = pub_catalog()
    core += research_sections(catalog)
    facts = "\n".join(c["text"] for c in core if c.get("src") in ("about.md", "practical.md"))
    faq = load_faq({c["url"] for c in core if c.get("src") in ("about.md", "practical.md") and c["url"]}, facts)
    for i, it in enumerate(core, 1):
        it["id"] = f"C{i}"
        it.pop("status", None)
        it.pop("src", None)
        for u in it["research"]:
            if u not in catalog:
                raise SystemExit(f"{it['title']}: research link {u} is not a published report in writing-bot/publications")

    chunks, dl, post = [], [], {}
    for d in corpus_docs(skipped):
        for piece in chunk(d["lines"]):
            ci = len(chunks)
            chunks.append({"t": d["title"], "u": d["url"], "k": d["kind"],
                           "y": d["year"], "s": d["stance"], "x": piece})
            toks = tokenize(d["title"] + " " + piece)
            dl.append(len(toks))
            for term, tf in Counter(toks).items():
                post.setdefault(term, []).extend([ci, tf])
    n = len(chunks)
    skipped["report without a topic in content/topics.json"] = sum(1 for p in catalog.values() if not p["a"])
    if not skipped["report without a topic in content/topics.json"]:
        del skipped["report without a topic in content/topics.json"]
    return {
        "version": 1,
        "source": _source_info(),
        "built": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "public": public,
        "core": core,
        "faq": faq,
        "pubs": catalog,
        "chunks": chunks,
        "bm25": {"n": n, "avgdl": round(sum(dl) / max(n, 1), 3), "dl": dl, "post": post},
        "_report": {"skipped": dict(skipped), "position_status": statuses},
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--public", action="store_true", help="launch build: approved positions only")
    ap.add_argument("--out", type=Path, default=OUT_DEFAULT)
    a = ap.parse_args()
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
    print(f"  core sections: {len(idx['core'])}   chunks: {len(idx['chunks'])} {dict(kinds)}")
    print(f"  bm25 terms: {len(idx['bm25']['post'])}   avg chunk length: {idx['bm25']['avgdl']} tokens")
    for k, v in rep["skipped"].items():
        print(f"  skipped {v}: {k}")
    appr = sum(1 for _, s in rep["position_status"] if s.startswith("approved"))
    print(f"  positions: {appr} approved, {len(rep['position_status']) - appr} draft")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
