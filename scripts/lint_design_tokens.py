#!/usr/bin/env python3
"""Fail on NEW raw colours or px font-sizes in *.html / *.css (DESIGN.md: use var(--ha-*)).

Only lines this branch adds are checked, so the existing pages' literals don't
block anyone; they get cleaned up as pages are touched.

    python3 scripts/lint_design_tokens.py                  # added lines vs origin/main (+ uncommitted)
    python3 scripts/lint_design_tokens.py --base <sha>     # CI: the PR base / push 'before'
    python3 scripts/lint_design_tokens.py --all FILE...    # every line of FILE (audit, not CI)

Flags in an added line:
  - raw colours: #rgb/#rrggbb(aa) hex, rgb()/rgba()/hsl()/hsla() with literal numbers
  - px font sizes: `font-size: …px`, a px size in the `font:` shorthand, `fontSize: '12px'`
Excluded: assets/tokens.css (where the values live) and its copy in brand-skill/, squarespace-ready/ and
*squarespace* snippets (pasted into Squarespace, which can't load tokens.css, so
they keep inline copies by design). A line ending in `design-lint: allow` (in any
comment syntax) is skipped, for the rare deliberate exception — say why next to it.
Stdlib only.
"""
from __future__ import annotations

import argparse
import fnmatch
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
INCLUDE = ("*.html", "*.css")
EXCLUDE = ("assets/tokens.css", "brand-skill/*/reference/tokens.css", "squarespace-ready/*", "*squarespace*")
ALLOW = re.compile(r"design-lint:\s*allow")

# Hex: not part of an entity (&#123;), a URL fragment (href="#cafe", url(#fade)) or an identifier.
HEX = re.compile(r"(?<![\w&#/-])(?<!href=\")(?<!href=')(?<!url\()(?<!src=\")#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})(?![\w-])")
FUNC = re.compile(r"\b(?:rgba?|hsla?)\(\s*[\d.]")
FONT_PX = re.compile(
    r"font-size\s*:\s*[^;\"'}]*?\d+(?:\.\d+)?px"          # font-size: 14px / clamp(…px…)
    r"|\bfont\s*:[^;\"'}]*?\d+(?:\.\d+)?px"                 # font: 700 14px/1.2 …
    r"|fontSize\s*[:=]\s*['\"]?\d+(?:\.\d+)?px",            # JS: fontSize: '12px'
    re.I,
)


def wanted(path: str) -> bool:
    return any(fnmatch.fnmatch(path, p) for p in INCLUDE) and not any(fnmatch.fnmatch(path, p) for p in EXCLUDE)


def problems(line: str) -> list[str]:
    if ALLOW.search(line):
        return []
    out = [f"raw colour {m.group(0)}" for m in HEX.finditer(line)]
    out += [f"raw colour {line[m.start():line.find(')', m.start()) + 1] or m.group(0)}" for m in FUNC.finditer(line)]
    out += [f"px font size `{m.group(0).strip()}`" for m in FONT_PX.finditer(line)]
    return out


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO, check=True, capture_output=True, text=True).stdout


def added_lines(base: str, include_worktree: bool):
    """Yield (path, line_no, text) for lines added since the merge-base with `base`."""
    mb = git("merge-base", base, "HEAD").strip()
    diff_args = ["diff", "-U0", "--no-color", "--no-ext-diff", "--diff-filter=AM", mb]
    if not include_worktree:
        diff_args.append("HEAD")
    path, n = None, 0
    for raw in git(*diff_args, "--", *INCLUDE).splitlines():
        if raw.startswith("+++ "):
            path = raw[6:] if raw.startswith("+++ b/") else None
        elif raw.startswith("@@"):
            n = int(re.search(r"\+(\d+)", raw).group(1))
        elif raw.startswith("+") and path:
            yield path, n, raw[1:]
            n += 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="origin/main", help="ref to diff against (default origin/main)")
    ap.add_argument("--committed", action="store_true", help="ignore uncommitted changes (CI)")
    ap.add_argument("--all", nargs="+", metavar="FILE", help="lint every line of these files instead")
    a = ap.parse_args()

    if a.all:
        lines = ((f, i, t) for f in a.all for i, t in enumerate(Path(f).read_text().splitlines(), 1))
    else:
        lines = added_lines(a.base, include_worktree=not a.committed)

    hits = 0
    for path, n, text in lines:
        if not wanted(path):
            continue
        for p in problems(text):
            hits += 1
            print(f"{path}:{n}: {p} — use a var(--ha-*) token (assets/tokens.css)")
            if "GITHUB_ACTIONS" in __import__("os").environ:
                print(f"::error file={path},line={n}::{p} — use a var(--ha-*) token")
    if hits:
        print(f"\n{hits} new raw colour / px font-size use(s). Add a token to assets/tokens.css if none fits "
              "(DESIGN.md), or end the line with a `design-lint: allow` comment saying why.")
        return 1
    print("design lint: no new raw colours or px font sizes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
