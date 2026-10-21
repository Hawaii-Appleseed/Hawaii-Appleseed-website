#!/usr/bin/env python3
"""Copy the few files the assistant reads from the rest of the website repo into chatbot/vendor/.

With a vendored copy, chatbot/ builds on its own: it can move to its own (private) repo, builds are pinned to a
known corpus snapshot, and a reorganized writing-bot/ cannot break it. The layout inside vendor/ matches the
website repo, so writing-bot/sources.py runs unmodified.

    python3 chatbot/vendor.py                 # copy from this checkout (the repo above chatbot/)
    python3 chatbot/vendor.py --from ~/HawaiiAppleseed     # copy from another checkout
    python3 chatbot/vendor.py --check         # exit 1 if vendor/ has drifted from the source (for CI)

build_index.py uses vendor/ when it has a MANIFEST.json, and the live tree otherwise (override with
CHATBOT_SOURCE=live|vendor). What is copied is exactly what the builder can read: the three corpus folders,
sources.py with its blog URL map, the bill-status feed, and the two stylesheets the widget needs. writing-bot/reference/ (internal meeting notes)
is never copied.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent

# (relative path, glob) pairs, all relative to the source repo root.
CORPUS = [
    ("writing-bot/publications", "*.txt"),
    ("writing-bot/blog-posts", "*/*.txt"),
    ("writing-bot/testimony", "*/*.txt"),
]
SINGLES = [
    "writing-bot/sources.py",
    "writing-bot/content-monitor/blog-sources.json",
    "tax-fairness/data/bill-status.json",
    "assets/tokens.css",  # the widget's design tokens and ʻokina fonts, inlined by build_embed.py
    "assets/okina.css",
]


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def collect(src: Path) -> list[str]:
    rels: list[str] = []
    for folder, pattern in CORPUS:
        rels += [str(p.relative_to(src)) for p in sorted((src / folder).glob(pattern))]
    for s in SINGLES:
        if not (src / s).exists():
            raise SystemExit(f"missing in source: {s}")
        rels.append(s)
    return rels


def git(src: Path, *args: str) -> str | None:
    try:
        return subprocess.run(["git", "-C", str(src), *args], capture_output=True, text=True, check=True).stdout.strip()
    except Exception:  # noqa: BLE001
        return None


def vendor(src: Path, out: Path) -> dict:
    rels = collect(src)
    tmp = out.with_name(out.name + ".tmp")
    if tmp.exists():
        shutil.rmtree(tmp)
    for r in rels:
        (tmp / r).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src / r, tmp / r)
    manifest = {
        "vendored_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_repo": git(src, "remote", "get-url", "origin"),
        "source_commit": git(src, "rev-parse", "HEAD"),
        "source_dirty": bool(git(src, "status", "--porcelain", "--", *[f for f, _ in CORPUS], *SINGLES)),
        "counts": {f.split("/")[-1]: len(list((src / f).glob(g))) for f, g in CORPUS},
        "files": {r: sha256(src / r) for r in rels},
    }
    (tmp / "MANIFEST.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    # Swap in whole: never leave a half-written vendor/ for a build to read.
    old = out.with_name(out.name + ".old")
    if old.exists():
        shutil.rmtree(old)
    if out.exists():
        out.rename(old)
    tmp.rename(out)
    if old.exists():
        shutil.rmtree(old)
    return manifest


def check(src: Path, out: Path) -> list[str]:
    mf = out / "MANIFEST.json"
    if not mf.exists():
        return ["no vendor/MANIFEST.json (run vendor.py)"]
    recorded = json.loads(mf.read_text(encoding="utf-8"))["files"]
    problems = []
    now = {r: sha256(src / r) for r in collect(src)}
    for r in sorted(set(now) | set(recorded)):
        if r not in recorded:
            problems.append(f"new in source, not vendored: {r}")
        elif r not in now:
            problems.append(f"vendored but gone from source: {r}")
        elif now[r] != recorded[r]:
            problems.append(f"changed in source: {r}")
        elif not (out / r).exists() or sha256(out / r) != recorded[r]:
            problems.append(f"vendored copy differs from its manifest: {r}")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--from", dest="src", type=Path, default=HERE.parent, help="repo checkout to copy from")
    ap.add_argument("--out", type=Path, default=Path(os.environ.get("CHATBOT_VENDOR_DIR", HERE / "vendor")))
    ap.add_argument("--check", action="store_true", help="report drift instead of copying")
    a = ap.parse_args()
    src, out = a.src.resolve(), a.out.resolve()
    if a.check:
        problems = check(src, out)
        for p in problems[:40]:
            print(p)
        print(f"{len(problems)} difference(s)" if problems else "vendor/ matches the source")
        return 1 if problems else 0
    m = vendor(src, out)
    n = len(m["files"])
    print(f"vendored {n} files into {out}  (source commit {str(m['source_commit'])[:10]}{', DIRTY' if m['source_dirty'] else ''})")
    print("  " + ", ".join(f"{k}: {v}" for k, v in m["counts"].items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
