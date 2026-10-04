#!/usr/bin/env python3
"""Rebuild the portable brand skill (brand-skill/appleseed-brand/ + .zip) from the repo's spec.

    python3 scripts/build_brand_skill.py           # copy DESIGN.md + tokens.css in, rebuild the zip
    python3 scripts/build_brand_skill.py --check   # CI: fail if either is stale

The skill is uploaded to Claude.ai (org skills) as the zip, so it can't read the
repo: it carries copies. DESIGN.md -> reference/web-design-guide.md and
assets/tokens.css -> reference/tokens.css. SKILL.md itself is hand-written; the
check makes sure every hex in it is a real token value, so a palette change
can't leave the skill teaching the old colours, and that the brand-* eval
graders' "every hex is a token" regex matches tokens.css. The zip is deterministic (sorted
entries, fixed timestamps), so an unchanged skill rebuilds byte-identical.
Stdlib only. Templates (templates/*.pptx, *.docx) come from build_brand_templates.py.
"""
from __future__ import annotations

import argparse
import io
import re
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILL = REPO / "brand-skill" / "appleseed-brand"
ZIP = REPO / "brand-skill" / "appleseed-brand.zip"
COPIES = {  # destination (in the skill) -> (source, transform)
    "reference/web-design-guide.md": (REPO / "DESIGN.md", lambda t: t.replace("](assets/tokens.css)", "](tokens.css)")),
    "reference/tokens.css": (REPO / "assets" / "tokens.css", lambda t: t),
}
EVALS = REPO / "evals" / "skills"
NEVER = {"#3A7811"}  # named in SKILL.md only as the forbidden legacy sage-green
EPOCH = (2026, 1, 1, 0, 0, 0)


def expected_copies() -> dict[str, bytes]:
    return {dst: fn(src.read_text()).encode() for dst, (src, fn) in COPIES.items()}


def skill_files(overrides: dict[str, bytes]) -> dict[str, bytes]:
    files = {p.relative_to(SKILL).as_posix(): p.read_bytes()
             for p in SKILL.rglob("*") if p.is_file() and p.name != ".DS_Store"}
    files.update(overrides)
    return files


def build_zip(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    dirs = sorted({"/".join(k.split("/")[:i]) + "/" for k in files for i in range(1, k.count("/") + 1)})
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for d in ["appleseed-brand/"] + [f"appleseed-brand/{d}" for d in dirs]:
            info = zipfile.ZipInfo(d, EPOCH)
            info.external_attr = 0o40755 << 16
            z.writestr(info, b"")
        for name in sorted(files):
            info = zipfile.ZipInfo(f"appleseed-brand/{name}", EPOCH)
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, files[name])
    return buf.getvalue()


def skill_hex_problems() -> list[str]:
    tokens = {h.upper() for h in re.findall(r"#[0-9a-fA-F]{6}\b", (REPO / "assets" / "tokens.css").read_text())}
    text = (SKILL / "SKILL.md").read_text()
    bad = sorted({h.upper() for h in re.findall(r"#[0-9a-fA-F]{6}\b", text)} - tokens - NEVER)
    return [f"SKILL.md uses {h}, which is not a value in assets/tokens.css" for h in bad]


def offpalette_pattern() -> str:
    """Regex for any #hex that is NOT a token value (#fff allowed), for the brand-* eval graders."""
    toks = sorted({h.upper() for h in re.findall(r"#([0-9a-fA-F]{6})\b", (REPO / "assets" / "tokens.css").read_text())})
    return r"#(?!(?:%s)(?![0-9a-f]))(?:[0-9a-f]{6}|[0-9a-f]{3})(?![0-9a-z_-])" % "|".join(toks + ["FFF"])


def eval_graders() -> dict[Path, bytes]:
    """brand-*/graders/off-palette-hex.md with the pattern line regenerated from tokens.css."""
    pat = offpalette_pattern().replace("\\", "\\\\")
    out = {}
    for g in sorted(EVALS.glob("brand-*/graders/off-palette-hex.md")):
        text = g.read_text()
        out[g] = re.sub(r'^pattern: ".*"$', lambda _: f'pattern: "{pat}"', text, count=1, flags=re.M).encode()
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="fail if the skill or zip is stale (writes nothing)")
    a = ap.parse_args()

    copies = expected_copies()
    files = skill_files(copies)
    want_zip = build_zip(files)
    probs = skill_hex_problems()
    graders = eval_graders()

    if a.check:
        for dst, data in copies.items():
            cur = SKILL / dst
            if not cur.exists() or cur.read_bytes() != data:
                probs.append(f"brand-skill/appleseed-brand/{dst} is stale vs {COPIES[dst][0].relative_to(REPO)}")
        if not ZIP.exists() or ZIP.read_bytes() != want_zip:
            probs.append("brand-skill/appleseed-brand.zip is stale vs the skill folder")
        for g, data in graders.items():
            if g.read_bytes() != data:
                probs.append(f"{g.relative_to(REPO)} allows a different palette than assets/tokens.css")
        for p in probs:
            print("ERROR " + p)
        if probs:
            print("Run: python3 scripts/build_brand_skill.py, then commit brand-skill/.")
            return 1
        print(f"brand skill up to date ({len(files)} files)")
        return 0

    for dst, data in copies.items():
        (SKILL / dst).parent.mkdir(parents=True, exist_ok=True)
        (SKILL / dst).write_bytes(data)
    ZIP.write_bytes(want_zip)
    for g, data in graders.items():
        g.write_bytes(data)
    print(f"rebuilt brand-skill/appleseed-brand.zip ({len(files)} files, {len(want_zip) // 1024} KB)")
    for p in probs:
        print("ERROR " + p)
    return 1 if probs else 0


if __name__ == "__main__":
    sys.exit(main())
