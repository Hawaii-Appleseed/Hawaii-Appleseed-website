"""Approvals are of exact text.

A position, a ready-made answer or a fixed reply goes public only when someone on staff has approved it, and what they
approved is what ships: an approval records a short hash of the exact words that were reviewed, and the public build
treats an approved item whose words have changed since as not approved. (Hand-writing `approved by NAME DATE` with no hash
still works, as the README says; the hash is what `signoff_doc.py --apply` adds, and it is enforced whenever it is present.)

    <!-- status: approved by NAME YYYY-MM-DD -->
    <!-- reviewed: 3fa9c1d07b -->
"""
from __future__ import annotations

import hashlib
import json


def text_hash(payload) -> str:
    """Ten hex characters over the canonical JSON of the words that were reviewed."""
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:10]


def position_hash(title: str, text: str) -> str:
    return text_hash({"title": title, "text": text.strip()})


def faq_hash(answer: str, source_urls: list[str]) -> str:
    return text_hash({"answer": answer.strip(), "sources": list(source_urls)})


def fixed_hash(parts: list[str]) -> str:
    return text_hash({"parts": [p.strip() for p in parts]})


def staff_hash(d: dict) -> str:
    """The people (name, title, email) and the routes: what a reviewer approves when they approve who to point visitors to."""
    return text_hash({"people": d["people"], "routes": d["routes"]})


def judge(status: str | None, reviewed: str | None, current: str) -> tuple[bool, str]:
    """(shippable, why not). Approved means the status says so AND, when a hash was recorded, the words still match it."""
    if not (status or "").startswith("approved"):
        return False, "not approved"
    if reviewed and reviewed != current:
        return False, "changed since it was approved"
    return True, ""
