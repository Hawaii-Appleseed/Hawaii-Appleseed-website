"""
Parse positions.md into structured, queryable entries.

positions.md is HA's curated stance guide (one entry per topic: Position, Active
bill(s), Core argument, Standard ask). It is injected verbatim into the writing
bot's generation prompt, but the search UI also wants to *fetch* the canonical
position when a user searches a topic or a bill number — so this module turns the
markdown into structured records plus a bill -> entry index.

Parsed in-process (not indexed into Chroma) so editing positions.md takes effect
without a reindex; results are cached and re-read when the file's mtime changes.

Public API:
    get_index() -> PositionsIndex
    PositionsIndex.match(query) -> Entry | None      # bill match, else cross-encoder
    PositionsIndex.stance_for_bill(bill) -> str|None # 'support'|'oppose'|'comment'
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).parent
POSITIONS_PATH = ROOT / "positions.md"

_BILL_RE = re.compile(r"\b([HS][BR])\s?(\d{3,5})\b")
_FIELD_RE = re.compile(r"^[-*]\s+\*\*(.+?):\*\*\s*(.*)$")
_ENTRY_RE = re.compile(r"^\*\*(.+?)\*\*\s*(.*)$")  # bold title line, not a "- " bullet
_SECTION_RE = re.compile(r"^###\s+(.+?)\s*$")


def _norm_bill(s: str) -> str:
    m = _BILL_RE.search(s)
    return f"{m.group(1).upper()}{m.group(2)}" if m else s.upper().replace(" ", "")


def _stance_from_text(text: str) -> str:
    """Classify the stance HA annotated on an 'Active bill' line. positions.md
    writes the stance after an em/en dash — "HB2049 (2026) — support." — so we
    read that explicit annotation; 'amend'/'with concerns' = conditional support
    (comment); anything else defaults to support (HA's corpus is support-heavy)."""
    # Prefer the explicit annotation after the (last) dash, if present.
    annotation = re.split(r"[—–-]", text)[-1].lower() if re.search(r"[—–]", text) else text.lower()
    if "oppos" in annotation or "reject" in annotation:
        return "oppose"
    if "amend" in annotation or "with comment" in annotation or "with concern" in annotation:
        return "comment"
    return "support"


@dataclass
class Entry:
    title: str
    section: str
    fields: dict = field(default_factory=dict)
    bills: list = field(default_factory=list)  # [{"bill","stance"}]
    raw: str = ""

    @property
    def position(self) -> str:
        return self.fields.get("position", "")

    @property
    def core_argument(self) -> str:
        return self.fields.get("core argument", "")

    @property
    def standard_ask(self) -> str:
        return self.fields.get("standard ask", "")

    def match_text(self) -> str:
        return f"{self.title}. {self.position} {self.core_argument}".strip()


class PositionsIndex:
    def __init__(self, entries: list):
        self.entries = entries
        self.bill_index = {}
        for e in entries:
            for b in e.bills:
                self.bill_index.setdefault(b["bill"], e)

    def stance_for_bill(self, bill: str | None) -> str | None:
        if not bill:
            return None
        e = self.bill_index.get(_norm_bill(bill))
        if not e:
            return None
        for b in e.bills:
            if b["bill"] == _norm_bill(bill):
                return b["stance"]
        return None

    def entry_for_bill(self, bill: str | None) -> "Entry | None":
        return self.bill_index.get(_norm_bill(bill)) if bill else None

    def match(self, query: str, *, min_score: float = 0.0) -> "Entry | None":
        """Best matching position for a free-text query. A bill number in the
        query wins outright; otherwise the cross-encoder ranks topic relevance."""
        for m in _BILL_RE.finditer(query):
            e = self.bill_index.get(f"{m.group(1).upper()}{m.group(2)}")
            if e:
                return e
        if not self.entries:
            return None
        try:
            from retrieval import _get_reranker
            model = _get_reranker()
            scores = model.predict([(query, e.match_text()) for e in self.entries])
        except Exception:
            return None
        best_i = max(range(len(scores)), key=lambda i: scores[i])
        return self.entries[best_i] if scores[best_i] >= min_score else None


def _parse(text: str) -> list:
    entries: list = []
    section = ""
    cur: Entry | None = None
    cur_lines: list = []
    last_field: str | None = None

    def flush():
        nonlocal cur, cur_lines
        if cur is not None:
            cur.raw = "\n".join(cur_lines).strip()
            # collect bills from any "active bill" field
            for label, val in cur.fields.items():
                if "active bill" in label:
                    for m in _BILL_RE.finditer(val):
                        bill = f"{m.group(1).upper()}{m.group(2)}"
                        if not any(b["bill"] == bill for b in cur.bills):
                            cur.bills.append({"bill": bill, "stance": _stance_from_text(val)})
            entries.append(cur)
        cur, cur_lines = None, []

    for line in text.splitlines():
        sec = _SECTION_RE.match(line)
        if sec:
            flush()
            section = sec.group(1).strip()
            last_field = None
            continue
        if line.startswith("## ") or line.strip() == "---":
            flush()
            last_field = None
            continue

        fld = _FIELD_RE.match(line)
        if fld and cur is not None:
            label = fld.group(1).strip().lower()
            cur.fields[label] = fld.group(2).strip()
            cur_lines.append(line)
            last_field = label
            continue

        stripped = line.strip()
        ent = _ENTRY_RE.match(stripped)
        if ent and not stripped.startswith("-"):
            title = ent.group(1).strip().rstrip(":")
            # Standalone "Active ... bills:" lines attach to the current entry.
            if title.lower().startswith("active") and cur is not None:
                cur.fields["active bills (standalone)"] = ent.group(2) or title
                cur_lines.append(line)
                continue
            flush()
            cur = Entry(title=title, section=section)
            cur_lines = [line]
            last_field = None
            continue

        # continuation line (sub-bullet / wrapped text) for the last field
        if cur is not None and stripped:
            cur_lines.append(line)
            if last_field:
                cur.fields[last_field] = (cur.fields[last_field] + " " + stripped).strip()

    flush()
    # keep only entries that carry a real position or bills
    return [e for e in entries if e.position or e.bills]


_cache: tuple | None = None  # (mtime, PositionsIndex)


def get_index() -> PositionsIndex:
    global _cache
    try:
        mtime = POSITIONS_PATH.stat().st_mtime
    except OSError:
        return PositionsIndex([])
    if _cache and _cache[0] == mtime:
        return _cache[1]
    text = POSITIONS_PATH.read_text(encoding="utf-8")
    idx = PositionsIndex(_parse(text))
    _cache = (mtime, idx)
    return idx
