#!/usr/bin/env python3
"""polis-sync-primer.py — refresh a primer-editor report's vote-derived
content.md slots from a fresh fetch-polis-report.py pull, without touching
anything editorial.

Pairs with fetch-polis-report.py: that script gets the numbers right, this
one gets them INTO a primer-editor project's content.md (docsync's own
[[key]] format — see ~/primer-editor/docsync/content.py) — the format
docsync.stage/render_report.py actually consume. It only ever overwrites
slots a MAP file names explicitly; every other slot (prose, idea text,
glosses, tier headers, editorial framing) is copied through byte-for-byte.

Why a map file, not automatic matching: a Pol.is comment's `tid` is an
integer with no knowledge of some report's slot naming, and a report's idea
text is usually a paraphrase of the raw Pol.is text, not a literal copy —
there is no reliable automatic key. The map is a one-time, hand-built (or
fingerprint-assisted — match each tid's (agree, votes, pass, disagree)
tuple against the numbers already in content.md's tally slots) record of
that correspondence. See tfc-2027-priorities's own polis-map.json, built
this way, as a worked example.

MAP JSON shape:
{
  "stats": {"votes_cast_key": "num.span-1"},
  "idea_tally_slots": {"<tid>": "<content.md slot key>", ...},
  "families": {"<content.md slot key>": [<tid>, <tid>, ...], ...}
}
`idea_tally_slots` values are written as this project's own tally format —
"**A of T** votes agreed · P passes[ · D disagree]" — one entry per idea.
`families` sums several tids' votes into one aggregate tally slot (e.g. a
"credits vs raisers" rollup card).

What this does NOT cover: anything not named in the map. In practice that
usually includes numbers baked directly into body.slotted.html as literal
text or inline `style="width:…"` — not slotted in content.md at all, so no
content.md-level tool can reach them. Check for these separately; the
project's own map file should say so if any exist.

Usage:
  python3 polis-sync-primer.py POLIS_JSON CONTENT_MD MAP_JSON [-o OUT] [--check]

  --check   report drift only (each slot whose fresh value differs from
            what's currently in content.md), write nothing, exit 1 if
            anything would change. Safe to run against a project whose
            editor is open — content.md is only ever READ in this mode.

Without --check, this WRITES content.md (or -o's path if given). Per the
primer-editor engine's own rule: never run the write mode against a
content.md whose editor tab is open — it holds the document in memory, and
Save would silently overwrite what this script just wrote. Use --check to
get the diff, then apply corrections through the editor's own pilot API
(docsync.api.setSlot / POST /__pilot) instead — see primer-editor/CLAUDE.md.
"""
import argparse
import json
import re
import sys


def format_tally(agree, total, passes, disagree):
    pass_text = ("no passes" if passes == 0
                 else "1 pass" if passes == 1
                 else f"{passes} passes")
    dis_text = ("" if disagree == 0
                else " · 1 disagree" if disagree == 1
                else f" · {disagree} disagrees")
    return f"**{agree} of {total}** votes agreed · {pass_text}{dis_text}"


def parse_content_md(text):
    """(preamble, [[key, body], ...]) — body keeps its own trailing blank lines."""
    parts = re.split(r'(?m)^(\[\[[^\]]+\]\])\n', text)
    preamble = parts[0]
    blocks = [[parts[i][2:-2], parts[i + 1]] for i in range(1, len(parts), 2)]
    return preamble, blocks


def serialize(preamble, blocks):
    return preamble + "".join(f"[[{key}]]\n{body}" for key, body in blocks)


def compute_new_values(polis, mapping):
    ideas_by_tid = {i["tid"]: i for i in polis["ideas"]}
    new_values = {}

    votes_key = mapping.get("stats", {}).get("votes_cast_key")
    if votes_key:
        new_values[votes_key] = str(polis["stats"]["votes_cast"])

    for tid_str, slot_key in mapping.get("idea_tally_slots", {}).items():
        idea = ideas_by_tid[int(tid_str)]
        new_values[slot_key] = format_tally(idea["agree"], idea["votes"],
                                             idea["pass"], idea["disagree"])

    for slot_key, tids in mapping.get("families", {}).items():
        agree = sum(ideas_by_tid[t]["agree"] for t in tids)
        total = sum(ideas_by_tid[t]["votes"] for t in tids)
        passes = sum(ideas_by_tid[t]["pass"] for t in tids)
        disagree = sum(ideas_by_tid[t]["disagree"] for t in tids)
        new_values[slot_key] = format_tally(agree, total, passes, disagree)

    return new_values


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("polis_json", help="output of fetch-polis-report.py")
    ap.add_argument("content_md", help="the primer-editor project's content.md")
    ap.add_argument("map_json", help="tid -> slot-key correspondence (see header)")
    ap.add_argument("-o", "--out", help="write here instead of back to content_md")
    ap.add_argument("--check", action="store_true",
                     help="report drift only; write nothing")
    args = ap.parse_args()

    polis = json.load(open(args.polis_json))
    mapping = json.load(open(args.map_json))
    new_values = compute_new_values(polis, mapping)

    preamble, blocks = parse_content_md(open(args.content_md).read())

    changes = []
    for block in blocks:
        key, body = block
        if key not in new_values:
            continue
        m = re.match(r'(.*?)(\n*)$', body, re.S)
        old_text, trail = m.group(1), m.group(2)
        new_text = new_values[key]
        if old_text.strip() != new_text.strip():
            changes.append((key, old_text.strip(), new_text))
        block[1] = new_text + trail

    unmatched = set(new_values) - {k for k, _ in blocks}
    if unmatched:
        print(f"warning: map names slot(s) not found in {args.content_md}: "
              f"{sorted(unmatched)}", file=sys.stderr)

    if args.check:
        if not changes:
            print("no drift — every mapped slot already matches the fresh pull",
                  file=sys.stderr)
            return
        for key, old, new in changes:
            print(f"{key}:\n  old: {old}\n  new: {new}", file=sys.stderr)
        sys.exit(1)

    out_path = args.out or args.content_md
    with open(out_path, "w") as f:
        f.write(serialize(preamble, blocks))
    print(f"wrote {out_path} ({len(changes)} slot(s) changed)", file=sys.stderr)
    for key, old, new in changes:
        print(f"  {key}: {old!r} -> {new!r}", file=sys.stderr)


if __name__ == "__main__":
    main()
