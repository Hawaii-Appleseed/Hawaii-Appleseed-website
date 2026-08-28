#!/usr/bin/env python3
"""
Build reference/citations.md from the footnotes of the real testimony corpus.

Pairs each citation with the claim it actually supports, so the skill can look
up a *figure* and find its verified source rather than emitting CITATION NEEDED.

Usage:  python build_citations.py [-o citations.md]
"""
from __future__ import annotations
import argparse, os, re, sys, glob, collections
from pathlib import Path

CORPUS = Path(os.path.expanduser("~/HawaiiAppleseed/writing-bot/testimony"))
RULE = re.compile(r"_{6,}")


def docs():
    for f in sorted(CORPUS.glob("*/*.txt")):
        if f.name.startswith("sample_"):
            continue
        yield f


def split_notes(raw: str):
    """Return (body_text, {n: citation}). Footnotes sit after the last rule."""
    raw = raw.replace("﻿", "")
    segs = RULE.split(raw)
    notes, body_parts = {}, []
    for seg in segs:
        found = dict(re.findall(r"^\[(\d+)\]\s*(.+?)(?=\n\[\d+\]|\Z)", seg, re.M | re.S))
        if found and len(found) >= max(1, len(re.findall(r"\[\d+\]", seg)) // 2):
            for k, v in found.items():
                notes.setdefault(k, " ".join(v.split()))
        else:
            body_parts.append(seg)
    return "\n".join(body_parts), notes


def claim_for(body: str, n: str, window: int = 260) -> str | None:
    """Text immediately preceding the [n] marker, trimmed to a sentence start."""
    m = re.search(r"\[" + n + r"\]", body)
    if not m:
        return None
    pre = body[max(0, m.start() - window): m.start()]
    pre = " ".join(pre.split())
    # trim to the last sentence boundary that isn't an abbreviation or a number
    cuts = [c.start() for c in re.finditer(r"(?<![A-Z])(?<!U\.S)(?<!\d)\.\s+(?=[A-Z“])", pre)]
    if cuts:
        pre = pre[cuts[-1] + 1:].strip()
    return pre or None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", default=str(Path(__file__).with_name("citations.md")))
    a = ap.parse_args()

    by_topic = collections.defaultdict(list)
    seen_cites, npairs, norphan = {}, 0, 0

    for f in docs():
        body, notes = split_notes(f.read_text(encoding="utf-8", errors="replace"))
        for n, cite in sorted(notes.items(), key=lambda kv: int(kv[0])):
            if cite.lower().startswith("ibid"):
                continue
            claim = claim_for(body, n)
            if claim:
                npairs += 1
            else:
                norphan += 1
            by_topic[f.parent.name].append((claim, cite, f.name))
            seen_cites.setdefault(re.split(r"[,“\"]", cite)[0].strip(), 0)
            seen_cites[re.split(r"[,“\"]", cite)[0].strip()] += 1

    total = sum(len(v) for v in by_topic.values())
    out = [
        "# Citation library — HA testimony corpus",
        "",
        f"Every footnote from the {len(list(docs()))} real testimonies in `writing-bot/testimony/`, "
        f"paired with the claim it supports. {total} citations, {npairs} with a locatable in-text claim.",
        "",
        "**Use this before writing `CITATION NEEDED`.** If a figure you need appears below, reuse the "
        "source exactly as written — these are citations HA has already published and stood behind. "
        "If the figure is *not* here, say so rather than attaching the nearest-looking source: a "
        "citation that does not support the number is worse than a visible gap.",
        "",
        "Verify a reused citation is still current before submitting. Several point to annual series "
        "(USDA SNAP tables, ALICE, Hawaiʻi Foodbank) whose numbers move each year even though the "
        "source title does not.",
        "",
        "## Most-cited authorities",
        "",
    ]
    for name, c in sorted(seen_cites.items(), key=lambda kv: -kv[1])[:12]:
        if name and c > 1:
            out.append(f"- **{name}** — {c} citations")
    out.append("")

    covered = sorted(by_topic)
    all_topics = sorted(d.name for d in CORPUS.iterdir() if d.is_dir())
    missing = [t for t in all_topics if t not in covered]
    out += [
        "## Coverage — read this before relying on a gap",
        "",
        f"Cited topics: **{', '.join(covered)}**.",
        "",
    ]
    if missing:
        out += [
            f"**No citations at all for: {', '.join(missing)}.** Those corpus folders contain only "
            "`sample_*` template files, which are excluded. A claim in one of those areas will not "
            "be sourceable from here — that is a real gap, not a search failure. Ask the user for "
            "the source or write `CITATION NEEDED`.",
            "",
        ]
    out += [
        "Coverage follows the corpus, which is food-equity heavy. Absence here says nothing about "
        "whether a figure is true or whether HA has used it — only that no *published testimony* "
        "footnoted it.",
        "",
    ]

    for topic in sorted(by_topic):
        out += [f"## {topic}", ""]
        for claim, cite, fn in by_topic[topic]:
            if claim:
                out.append(f"- **Claim:** …{claim}")
                out.append(f"  - **Source:** {cite}")
            else:
                out.append(f"- **Source (no in-text claim located):** {cite}")
            out.append(f"  - <sub>`{topic}/{fn}`</sub>")
        out.append("")

    Path(a.out).write_text("\n".join(out), encoding="utf-8")
    print(f"{a.out}: {total} citations across {len(by_topic)} topics "
          f"({npairs} with claims, {norphan} without)")


if __name__ == "__main__":
    main()
