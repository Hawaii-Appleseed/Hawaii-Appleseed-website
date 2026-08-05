"""
Map a corpus file to its source: live URL / PDF where known, else local path.

Used by the search UI to point readers at the original material.

- publications/*.txt carry `URL:` and `PDF:` header lines (written by the scraper).
- blog-posts/**/*.txt are named by title-slug; their live URL is looked up in
  content-monitor/blog-sources.json ({slug: url}), populated by the scraper's
  --rebuild-sources backfill. Missing entries fall back to the local path.
- testimony/ and reference/ have no live URL — local path only.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).parent
BLOG_SOURCES = ROOT / "content-monitor" / "blog-sources.json"

_DATE_PREFIX = re.compile(r"^\d{4}-\d{2}-\d{2}[_-]")
_BILL_TOKEN = re.compile(r"(?i)^[hs][br]\d")
# Testimony documents lead with boilerplate; the human title is the stance line,
# e.g. "Support for HB 1779 – Relating to School Meals".
_STANCE_LINE = re.compile(r"(?i)^(support|opposition|oppose|comments?|in support|in opposition)\b")

# Classify a testimony's explicitly-declared stance from its header line.
# Order matters: oppose/comment are checked before support so a conditional
# "support with concerns" line lands on comment.
_STANCE_CLASSIFY = [
    ("oppose", re.compile(r"(?i)^(in opposition|opposition|oppos)")),
    ("comment", re.compile(r"(?i)^(comments?|with comments|with concerns)")),
    ("support", re.compile(r"(?i)^(in support|strong support|support)")),
]


# Ask-verb mapping (option 1): testimony states its ask explicitly — "we
# respectfully urge the Committee to PASS HB…". Map the ask verb to a stance.
_ASK_RE = re.compile(
    r"(?i)\b(?:urge|respectfully\s+(?:urge|request|ask)|we\s+(?:ask|request|urge)|please)\b"
    r"[^.\n]{0,80}?\b(pass|passage|adopt|enact|advance|support|oppose|reject|hold|defer|kill|amend)\b"
)
_ASK_STANCE = {
    "pass": "support", "passage": "support", "adopt": "support", "enact": "support",
    "advance": "support", "support": "support",
    "oppose": "oppose", "reject": "oppose", "hold": "oppose", "defer": "oppose", "kill": "oppose",
    "amend": "comment",
}


@lru_cache(maxsize=512)
def document_stance(rel_path: str) -> str | None:
    """The stance a document explicitly declares — 'support', 'oppose', or
    'comment' — or None. Reads what the document actually says (not a keyword
    guess over the whole body): first the testimony header line ("Support for
    HB …"), then the explicit ask sentence ("we urge the Committee to pass …").
    Non-testimony docs typically return None (see infer_stance for those)."""
    try:
        text = (ROOT / rel_path).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    nonempty = [ln.strip().lstrip("﻿") for ln in text.splitlines() if ln.strip()]
    for ln in nonempty[:15]:
        for stance, rx in _STANCE_CLASSIFY:
            if rx.match(ln):
                return stance
    m = _ASK_RE.search(text)
    if m:
        return _ASK_STANCE.get(m.group(1).lower())
    return None


# First-person stance lexicon (option 2): a gated, last-resort inference for
# docs that declare no header/ask and aren't covered by positions.md (blogs,
# op-eds, publications). Cues require HA's first-person voice ("we …") or appear
# in the doc title (which is HA's framing), so we don't trip on text that merely
# describes the opposition's view. Returns a stance only when one side clearly
# outweighs the other — otherwise None (no badge).
# Cues are deliberately narrow. Blog/op-ed stance is *argued*, not declared, and
# generic words betray you: "harmful" appears in pro-protection pieces ("harmful
# federal cuts"), so it is NOT a usable oppose cue. We require HA's first-person
# voice near a support/oppose verb, or a reliably-pejorative HA phrase. Anything
# ambiguous is left out — better None than a wrong badge.
_FP = r"(?:we|hawaiʻi\s+appleseed|appleseed|the\s+center)"
_SUP_CUES = [re.compile(p, re.I) for p in (
    rf"{_FP}[^.\n]{{0,40}}\b(?:strongly\s+)?support(?:s|ed|ing)?\b",
    rf"{_FP}[^.\n]{{0,40}}\bapplaud",
    rf"{_FP}[^.\n]{{0,40}}\burge[^.\n]{{0,30}}\b(?:to\s+)?(?:pass|adopt|enact)\b",
    r"\bin\s+(?:strong\s+)?support\s+of\b",
)]
_OPP_CUES = [re.compile(p, re.I) for p in (
    rf"{_FP}[^.\n]{{0,40}}\b(?:strongly\s+)?oppose(?:s|d|ing)?\b",
    rf"{_FP}[^.\n]{{0,40}}cannot\s+support\b",
    rf"{_FP}[^.\n]{{0,40}}\burge[^.\n]{{0,30}}\b(?:to\s+)?(?:reject|hold|defer|kill)\b",
    r"\bbad\s+policy\b", r"\btrickle-down\b",
)]


@lru_cache(maxsize=512)
def infer_stance(rel_path: str) -> str | None:
    """Best-guess stance from a weighted first-person cue lexicon over the title
    + opening + closing of a document. Gated: returns a stance only when the cue
    counts clearly favor one side, else None. Lower-confidence than
    document_stance / positions.md — used only as a final fallback."""
    try:
        text = (ROOT / rel_path).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    sample = f"{source_title(rel_path)}\n{text[:1500]}\n{text[-1000:]}"
    sup = sum(1 for rx in _SUP_CUES if rx.search(sample))
    opp = sum(1 for rx in _OPP_CUES if rx.search(sample))
    if sup > opp:
        return "support"
    if opp > sup:
        return "oppose"
    return None


@lru_cache(maxsize=1)
def _blog_sources() -> dict:
    if BLOG_SOURCES.exists():
        try:
            return json.loads(BLOG_SOURCES.read_text())
        except Exception:
            return {}
    return {}


def source_ref(rel_path: str) -> dict:
    """Return {kind, url, pdf, local_path} for a corpus-relative file path."""
    p = ROOT / rel_path
    parts = Path(rel_path).parts
    top = parts[0] if parts else ""
    ref = {"kind": top or "other", "url": None, "pdf": None, "local_path": str(p)}

    if top == "publications":
        try:
            head = p.read_text(encoding="utf-8", errors="ignore")[:800]
        except Exception:
            head = ""
        for line in head.splitlines():
            if line.startswith("URL:"):
                ref["url"] = line[4:].strip() or None
            elif line.startswith("PDF:"):
                ref["pdf"] = line[4:].strip() or None
            elif line.startswith("="):
                break
    elif top == "blog-posts":
        ref["url"] = _blog_sources().get(Path(rel_path).stem)

    return ref


def read_source(rel_path: str) -> str:
    """Full text of a corpus file (empty string if unreadable)."""
    try:
        return (ROOT / rel_path).read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def _pretty_slug(rel_path: str) -> str:
    """Last-resort title from the filename: drop any date prefix, split on
    -/_, title-case words but keep acronyms (SNAP) and bill numbers (HB1800)."""
    stem = _DATE_PREFIX.sub("", Path(rel_path).stem)
    words = []
    for w in re.split(r"[-_]+", stem):
        if not w:
            continue
        words.append(w.upper() if (w.isupper() or _BILL_TOKEN.match(w)) else w.capitalize())
    return " ".join(words) or Path(rel_path).name


@lru_cache(maxsize=512)
def source_title(rel_path: str) -> str:
    """Human-readable document title, derived from the file's content where the
    format allows, else a prettified filename. See module docstring for layouts."""
    parts = Path(rel_path).parts
    top = parts[0] if parts else ""
    try:
        text = (ROOT / rel_path).read_text(encoding="utf-8", errors="ignore")
    except Exception:
        text = ""
    lines = [ln.strip().lstrip("﻿") for ln in text.splitlines()]
    nonempty = [ln for ln in lines if ln]

    if top == "publications":
        for ln in lines[:12]:
            if ln.lower().startswith("title:"):
                t = ln.split(":", 1)[1].strip()
                if t:
                    return t
    elif top == "blog-posts":
        if nonempty:
            return nonempty[0]
    elif top == "testimony":
        for ln in nonempty[:15]:
            if _STANCE_LINE.match(ln):
                return ln

    # reference docs are heterogeneous (their first line is often not a title),
    # so they fall through to the prettified filename like everything unmatched.
    return _pretty_slug(rel_path)
