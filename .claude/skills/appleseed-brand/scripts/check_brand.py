#!/usr/bin/env python3
"""Check a file you made against the Hawaiʻi Appleseed brand before handing it over.

    python3 check_brand.py FILE [FILE ...]

Works on HTML, CSS, SVG, Markdown, and chart/slide code (Python, JS, R): any text file.
Errors (exit 1):
  - a colour that isn't a brand value (hex or rgb() literal), or the retired sage-green
  - a font other than Manrope / Poppins (and their fallbacks), or any serif
  - small text whose colour fails WCAG AA against the background set in the same CSS
    rule, or that fails on every background it could sit on (Teal under 24px)
  - small text faded below the readable floor (Charcoal under 74%, White under 70%)
  - font-style:italic on Manrope (it has no italic; use Poppins)
Warnings (exit 0): "Hawaii" / "Hawai'i" in visible text where the ʻokina (U+02BB) belongs.

The palette comes from reference/tokens.css next to this script, so it always matches
the skill. Stdlib only. A line ending in `brand-check: allow` is skipped.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
TOKENS = HERE / "reference" / "tokens.css"
SAGE = {"3A7811"}
FONTS_OK = {"manrope", "poppins", "okinamanrope", "okinapoppins", "arial", "helvetica",
            "helvetica neue", "sans-serif", "system-ui", "-apple-system", "blinkmacsystemfont",
            "inherit", "initial", "unset", "dejavu sans", "liberation sans", "segoe ui", "roboto"}
ALLOW = re.compile(r"brand-check:\s*allow")


# ---------- colour ----------

def hex_rgba(h: str):
    h = h.lstrip("#")
    if len(h) in (3, 4):
        h = "".join(c * 2 for c in h)
    a = int(h[6:8], 16) / 255 if len(h) == 8 else 1.0
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)


def load_tokens():
    raw = dict(re.findall(r"(--ha-[\w-]+)\s*:\s*([^;]+);", TOKENS.read_text(encoding="utf-8")))
    vals: dict[str, str] = {}
    for k, v in raw.items():  # first definition wins (the :root one, not the mobile override)
        vals.setdefault(k, v.strip())
    return vals


TOK = load_tokens()
PALETTE = {h.upper() for v in TOK.values() for h in re.findall(r"#([0-9a-fA-F]{6})\b", v)} | {"FFFFFF", "FFF"}
PALETTE_RGB = {hex_rgba(h)[:3] for h in PALETTE}


def parse_colour(v: str, depth=0):
    v = re.sub(r"\s*!important\s*$", "", v.strip())
    if m := re.fullmatch(r"var\((--ha-[\w-]+)(?:\s*,\s*(.+))?\)", v):
        if m.group(1) in TOK and depth < 6:
            return parse_colour(TOK[m.group(1)], depth + 1)
        return parse_colour(m.group(2), depth + 1) if m.group(2) else None
    if re.fullmatch(r"#[0-9a-fA-F]{3,8}", v):
        return hex_rgba(v)
    if m := re.fullmatch(r"rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)(?:[,\s/]+([\d.]+%?))?\s*\)", v):
        a = m.group(4)
        a = 1.0 if a is None else (float(a[:-1]) / 100 if a.endswith("%") else float(a))
        return (float(m.group(1)), float(m.group(2)), float(m.group(3)), a)
    if v.lower() in ("white", "#fff"):
        return (255, 255, 255, 1.0)
    return None


def _lin(c):
    c /= 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def lum(c):
    return 0.2126 * _lin(c[0]) + 0.7152 * _lin(c[1]) + 0.0722 * _lin(c[2])


def over(fg, bg):
    a = fg[3]
    return tuple(fg[i] * a + bg[i] * (1 - a) for i in range(3)) + (1.0,)


def ratio(fg, bg):
    fg = over(fg, bg)
    hi, lo = sorted((lum(fg), lum(bg)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


# ---------- CSS ----------

def font_px(decls: dict) -> float | None:
    v = decls.get("font-size")
    if not v:
        return None
    if m := re.fullmatch(r"var\((--ha-fs-[\w-]+)\)", v.strip()):
        v = TOK.get(m.group(1), "")
    if m := re.match(r"\s*([\d.]+)px", v):
        return float(m.group(1))
    if m := re.match(r"\s*([\d.]+)r?em", v):
        return float(m.group(1)) * 16
    if m := re.match(r"\s*clamp\(\s*([\d.]+)px", v):  # smallest it can get
        return float(m.group(1))
    return None


def rules(text: str):
    """Yield (line_no, selector, {prop: value}) for CSS rules and style="" attributes."""
    for m in re.finditer(r"([^{}<>]*)\{([^{}]*)\}", text):
        body = m.group(2)
        if ":" not in body or "@" in m.group(1):
            continue
        yield text.count("\n", 0, m.start(2)) + 1, m.group(1).strip()[-60:], decls_of(body)
    for m in re.finditer(r"style\s*=\s*\"([^\"]*)\"", text):
        yield text.count("\n", 0, m.start()) + 1, "style=\"…\"", decls_of(m.group(1))


def decls_of(body: str) -> dict:
    out = {}
    for part in re.split(r";(?![^(]*\))", body):
        if ":" in part:
            k, v = part.split(":", 1)
            out[k.strip().lower()] = v.strip()
    return out


def background_of(d: dict):
    for k in ("background-color", "background"):
        if k in d:
            cols = re.findall(r"var\(--ha-[\w-]+\)|#[0-9a-fA-F]{3,8}\b|rgba?\([^)]*\)", d[k])
            if len(cols) == 1 and "gradient" not in d[k] and "url(" not in d[k]:
                return parse_colour(cols[0])
    return None


TEAL = hex_rgba("#84A98C")
CHARCOAL, WHITE = (47, 62, 70), (255, 255, 255)


def check_css(text: str, problems: list):
    for line, sel, d in rules(text):
        if "color" in d:
            fg = parse_colour(d["color"])
            if fg:
                size = font_px(d)
                bold = d.get("font-weight", "400").strip() in ("bold", "700", "800", "900")
                large = size is not None and (size >= 24 or (bold and size >= 18.66))
                need = 3.0 if large else 4.5
                bg = background_of(d)
                if bg and bg[3] >= 1:
                    r = ratio(fg, bg)
                    if r < need:
                        problems.append(("error", line, f"`{sel}`: text {d['color']} on {d.get('background-color') or d.get('background')} is {r:.2f}:1, needs {need}:1 — see SKILL.md › Small text"))
                elif not large and fg[:3] == TEAL[:3]:
                    problems.append(("error", line, f"`{sel}`: Teal (#84A98C) is too faint for text under 24px on any background — use Deep Teal on white, Teal Ink on tints, Teal Bright on dark"))
                elif not large and fg[:3] == CHARCOAL and fg[3] < 0.74:
                    problems.append(("error", line, f"`{sel}`: Charcoal at {fg[3]:.0%} fails contrast for small text — use var(--ha-ink-subtle) (74%) or darker"))
                elif not large and fg[:3] == WHITE and fg[3] < 0.7:
                    problems.append(("error", line, f"`{sel}`: White at {fg[3]:.0%} fails contrast for small text — use var(--ha-ink-on-dark-muted) (70%) or Ash"))
        fam = d.get("font-family", "").lower()
        if d.get("font-style", "").strip() == "italic" and fam.split(",")[0].strip(" '\"") in ("manrope", "okinamanrope", "var(--ha-font-display)"):
            problems.append(("error", line, f"`{sel}`: italic Manrope is a fake slant — set italics in Poppins"))


# ---------- whole-file checks ----------

HEX = re.compile(r"(?<![\w&#/-])(?<!href=\")(?<!url\()#([0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3})(?![\w-])")
RGB = re.compile(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)")
FAMILY = re.compile(r"""(?:font-family\s*:\s*([^;}"]+)|(?:font_?family|fontfamily|family|fontName|font\.name)['"]?\]?\s*[=:]\s*\[?\s*['"]([^'"]+)['"])""", re.I)
OKINA = re.compile(r"(?<![/.@\w-])Hawai(?:i|['’`‘]i)(?![\w.]*\.(?:gov|org|edu|com)\b)(?![\w/])")


def check_file(path: Path) -> list:
    text = path.read_text(encoding="utf-8", errors="replace")
    problems: list = []
    lines = text.split("\n")
    for n, ln in enumerate(lines, 1):
        if ALLOW.search(ln):
            continue
        for m in HEX.finditer(ln):
            h = m.group(1).upper()
            if len(h) == 3:
                h = "".join(c * 2 for c in h)
            h6 = h[:6]
            if h6 in SAGE:
                problems.append(("error", n, f"#{m.group(1)} is the retired sage-green — never use it"))
            elif h6 not in PALETTE and h6 != "000000":  # black is fine for shadows / colour-mix shading
                problems.append(("error", n, f"#{m.group(1)} is not a brand colour — pick from SKILL.md › Colors / Chart palette"))
        for m in RGB.finditer(ln):
            rgb = tuple(float(x) for x in m.groups())
            if rgb not in PALETTE_RGB and rgb not in ((0, 0, 0),):
                problems.append(("error", n, f"{m.group(0)}…) is not a brand colour"))
        for m in FAMILY.finditer(ln):
            fams = [f.strip(" '\"").lower() for f in (m.group(1) or m.group(2)).split(",")]
            bad = [f for f in fams if f and not f.startswith("var(") and f not in FONTS_OK]
            if bad:
                problems.append(("error", n, f"font {', '.join(bad)} — use Manrope (headings) and Poppins (body); no serif"))
        if path.suffix.lower() == ".css":
            continue
        if path.suffix.lower() in (".py", ".js", ".r", ".ts"):
            vis = " ".join(x or y for x, y in re.findall(r"\"([^\"]*)\"|'([^']*)'", ln))  # string literals only
        else:
            vis = re.sub(r"<[^>]*>", " ", ln)
        vis = re.sub(r"https?://\S+|\S+@\S+", " ", vis)
        for m in OKINA.finditer(vis):
            problems.append(("warn", n, f"“{m.group(0)}” — spell it Hawaiʻi with the ʻokina (U+02BB)"))
    if path.suffix.lower() in (".html", ".htm", ".css", ".svg", ".md"):
        kept = "\n".join("" if ALLOW.search(l) else l for l in lines)
        check_css(kept, problems)
    return sorted(set(problems), key=lambda p: p[1])


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0 if argv else 2
    errors = 0
    for a in argv:
        p = Path(a)
        if not p.is_file():
            print(f"{a}: not a file")
            errors += 1
            continue
        probs = check_file(p)
        for kind, n, msg in probs:
            print(f"{a}:{n}: {kind.upper()} {msg}")
        e = sum(1 for k, _, _ in probs if k == "error")
        errors += e
        if not probs:
            print(f"{a}: on brand")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
