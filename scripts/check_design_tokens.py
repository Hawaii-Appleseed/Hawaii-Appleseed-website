#!/usr/bin/env python3
"""Check the colour tokens in assets/tokens.css: WCAG AA contrast and chart palettes.

    python3 scripts/check_design_tokens.py           # print the contrast table + palette report
    python3 scripts/check_design_tokens.py --write   # regenerate DESIGN.md's contrast table
    python3 scripts/check_design_tokens.py --check   # CI: fail if DESIGN.md is stale or a palette rule breaks

Contrast. PAIRS below lists every text/background combination the site and the
brand skill actually use. Each is graded against WCAG 2.2 AA for its role
(4.5:1 normal text, 3:1 large text >= 24px or bold >= 18.66px, 3:1 non-text UI).
Failures are FLAGGED in DESIGN.md's table, never fixed by nudging a colour:
changing a brand value is a brand decision. --check fails when a token change
moves a pair across the line (the committed table no longer matches), so a pair
can't silently lose its approval.

Chart palettes (--ha-chart-*). Colour-vision-deficiency safety is checked by
simulating protanopia, deuteranopia and tritanopia (Machado et al. 2009,
severity 1.0) and measuring CIEDE2000 distance:
  - categorical: every pair >= CAT_MIN_DE under normal vision and every simulation
  - sequential: lightness strictly monotonic, each step >= SEQ_MIN_STEP L*
  - diverging: each arm monotonic from the neutral midpoint; mirrored steps of
    the two arms stay >= DIV_MIN_DE apart under every simulation
Stdlib only.
"""
from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TOKENS = REPO / "assets" / "tokens.css"
DESIGN = REPO / "DESIGN.md"
START, END = "<!-- contrast-table:start -->", "<!-- contrast-table:end -->"

CAT_MIN_DE = 10.0
SEQ_MIN_STEP = 5.0
DIV_MIN_DE = 10.0

# (foreground token, background token, role, where it's used)
# role: "text" = normal body/label text, "large" = >=24px or bold >=18.66px, "ui" = non-text
PAIRS = [
    ("--ha-charcoal", "--ha-white", "text", "body text"),
    ("--ha-charcoal", "--ha-bg", "text", "body text on page tint"),
    ("--ha-charcoal", "--ha-ash-light", "text", "callout text"),
    ("--ha-charcoal", "--ha-tint-tax", "text", "issue hub card"),
    ("--ha-charcoal", "--ha-tint-food", "text", "issue hub card"),
    ("--ha-charcoal", "--ha-tint-housing", "text", "issue hub card"),
    ("--ha-charcoal", "--ha-tint-transit", "text", "issue hub card"),
    ("--ha-charcoal", "--ha-tint-wages", "text", "issue hub card"),
    ("--ha-charcoal", "--ha-teal", "text", "primary pill button label"),
    ("--ha-charcoal", "--ha-ash", "text", "primary button hover"),
    ("--ha-slate", "--ha-white", "text", "secondary text"),
    ("--ha-slate", "--ha-bg", "text", "secondary text on tint"),
    ("--ha-ink-muted", "--ha-white", "text", "lede paragraph"),
    ("--ha-ink-muted", "--ha-bg", "text", "lede on page tint"),
    ("--ha-ink-subtle", "--ha-white", "text", "stat labels, source notes"),
    ("--ha-ink-subtle", "--ha-bg", "text", "stat labels on tint"),
    ("--ha-teal-deep", "--ha-white", "text", "links, eyebrows, key numbers"),
    ("--ha-teal-deep", "--ha-bg", "text", "links/eyebrows on page tint"),
    ("--ha-teal-deep", "--ha-ash-light", "text", "eyebrow in callout"),
    ("--ha-teal-deep", "--ha-tint-food", "text", "accent on food card"),
    ("--ha-teal-deep", "--ha-tint-housing", "text", "accent on housing card"),
    ("--ha-teal-deep", "--ha-tint-wages", "text", "accent on wages card"),
    ("--ha-slate", "--ha-tint-tax", "text", "accent on tax card"),
    ("--ha-slate", "--ha-tint-transit", "text", "accent on transit card"),
    ("--ha-teal-deep", "--ha-white", "large", "headline accent"),
    ("--ha-teal", "--ha-white", "text", "teal text on light (avoid)"),
    ("--ha-teal", "--ha-white", "large", "teal headline on light"),
    ("--ha-teal", "--ha-white", "ui", "secondary chart series, rules"),
    ("--ha-white", "--ha-charcoal", "text", "text on dark section"),
    ("--ha-white", "--ha-slate", "text", "text on dark gradient end"),
    ("--ha-white", "--ha-teal-deep", "text", "white on deep-teal fill"),
    ("--ha-white", "--ha-teal", "text", "white on teal button (avoid)"),
    ("--ha-ash", "--ha-charcoal", "text", "body text on dark"),
    ("--ha-ash", "--ha-slate", "text", "body text on dark gradient end"),
    ("--ha-teal", "--ha-charcoal", "text", "eyebrow on dark"),
    ("--ha-teal", "--ha-slate", "text", "eyebrow on dark gradient end"),
    ("--ha-teal-deep", "--ha-charcoal", "text", "deep teal on dark (avoid)"),
    ("--ha-teal-deep", "--ha-white", "ui", "primary chart series, focus ring"),
    ("--ha-ash", "--ha-white", "ui", "tertiary chart series (avoid alone)"),
]
THRESHOLD = {"text": 4.5, "large": 3.0, "ui": 3.0}
ROLE_LABEL = {"text": "normal text", "large": "large text", "ui": "non-text / UI"}


# ---------- colour math ----------

def parse_tokens(css: str) -> dict[str, tuple]:
    """--name: #hex | rgba(r,g,b,a) | var(--other) -> (r, g, b, a) in 0-255 / 0-1.
    Only the first (top-level :root) definition of each token counts."""
    out: dict[str, tuple] = {}
    raw: dict[str, str] = {}
    for name, val in re.findall(r"(--ha-[\w-]+)\s*:\s*([^;]+);", css):
        raw.setdefault(name, val.strip())
    def resolve(name, depth=0):
        v = raw[name]
        if m := re.fullmatch(r"var\((--ha-[\w-]+)\)", v):
            return resolve(m.group(1), depth + 1) if depth < 5 else None
        if m := re.fullmatch(r"#([0-9a-fA-F]{6})", v):
            h = m.group(1)
            return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 1.0)
        if m := re.fullmatch(r"rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*(?:,\s*([\d.]+)\s*)?\)", v):
            r, g, b, a = m.groups()
            return (float(r), float(g), float(b), float(a) if a else 1.0)
        return None
    for name in raw:
        c = resolve(name)
        if c is not None:
            out[name] = c
    return out


def composite(fg, bg):
    a = fg[3]
    return tuple(fg[i] * a + bg[i] * (1 - a) for i in range(3)) + (1.0,)


def _lin(c):
    c /= 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(c):
    r, g, b = (_lin(x) for x in c[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(fg, bg):
    fg = composite(fg, bg) if fg[3] < 1 else fg
    l1, l2 = sorted((luminance(fg), luminance(bg)), reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


def to_lab(c):
    r, g, b = (_lin(x) for x in c[:3])
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883
    f = lambda t: t ** (1 / 3) if t > 216 / 24389 else (24389 / 27 * t + 16) / 116
    fx, fy, fz = f(x), f(y), f(z)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def de2000(c1, c2):
    L1, a1, b1 = to_lab(c1)
    L2, a2, b2 = to_lab(c2)
    C1, C2 = math.hypot(a1, b1), math.hypot(a2, b2)
    Cb = (C1 + C2) / 2
    G = 0.5 * (1 - math.sqrt(Cb ** 7 / (Cb ** 7 + 25 ** 7)))
    a1p, a2p = a1 * (1 + G), a2 * (1 + G)
    C1p, C2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1p = math.degrees(math.atan2(b1, a1p)) % 360
    h2p = math.degrees(math.atan2(b2, a2p)) % 360
    dLp, dCp = L2 - L1, C2p - C1p
    dh = h2p - h1p
    if C1p * C2p == 0:
        dh = 0
    elif dh > 180:
        dh -= 360
    elif dh < -180:
        dh += 360
    dHp = 2 * math.sqrt(C1p * C2p) * math.sin(math.radians(dh / 2))
    Lbp, Cbp = (L1 + L2) / 2, (C1p + C2p) / 2
    if C1p * C2p == 0:
        hbp = h1p + h2p
    elif abs(h1p - h2p) <= 180:
        hbp = (h1p + h2p) / 2
    else:
        hbp = (h1p + h2p + 360) / 2 if h1p + h2p < 360 else (h1p + h2p - 360) / 2
    T = (1 - 0.17 * math.cos(math.radians(hbp - 30)) + 0.24 * math.cos(math.radians(2 * hbp))
         + 0.32 * math.cos(math.radians(3 * hbp + 6)) - 0.20 * math.cos(math.radians(4 * hbp - 63)))
    dth = 30 * math.exp(-(((hbp - 275) / 25) ** 2))
    Rc = 2 * math.sqrt(Cbp ** 7 / (Cbp ** 7 + 25 ** 7))
    Sl = 1 + 0.015 * (Lbp - 50) ** 2 / math.sqrt(20 + (Lbp - 50) ** 2)
    Sc, Sh = 1 + 0.045 * Cbp, 1 + 0.015 * Cbp * T
    Rt = -math.sin(math.radians(2 * dth)) * Rc
    return math.sqrt((dLp / Sl) ** 2 + (dCp / Sc) ** 2 + (dHp / Sh) ** 2 + Rt * (dCp / Sc) * (dHp / Sh))


# Machado, Oliveira & Fernandes (2009), severity 1.0, applied in linear RGB.
CVD = {
    "protan": ((0.152286, 1.052583, -0.204868), (0.114503, 0.786281, 0.099216), (-0.003882, -0.048116, 1.051998)),
    "deutan": ((0.367322, 0.860646, -0.227968), (0.280085, 0.672501, 0.047413), (-0.011820, 0.042940, 0.968881)),
    "tritan": ((1.255528, -0.076749, -0.178779), (-0.078411, 0.930809, 0.147602), (0.004733, 0.691367, 0.303900)),
}


def simulate(c, kind):
    if kind == "normal":
        return c
    lin = [_lin(x) for x in c[:3]]
    out = []
    for row in CVD[kind]:
        v = min(1.0, max(0.0, sum(row[i] * lin[i] for i in range(3))))
        v = 12.92 * v if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055
        out.append(v * 255)
    return tuple(out) + (1.0,)


VISIONS = ("normal", "protan", "deutan", "tritan")


def hexof(c):
    return "#%02X%02X%02X" % tuple(round(x) for x in c[:3])


# ---------- checks ----------

def contrast_rows(tok):
    rows = []
    for fg, bg, role, use in PAIRS:
        if fg not in tok or bg not in tok:
            sys.exit(f"check_design_tokens: {fg if fg not in tok else bg} not defined in tokens.css")
        r = contrast(tok[fg], tok[bg])
        rows.append((fg, bg, role, use, r, r >= THRESHOLD[role]))
    return rows


def contrast_table(rows):
    lines = ["| Foreground | Background | Role | Ratio | AA | Used for |", "|---|---|---|---|---|---|"]
    for fg, bg, role, use, r, ok in sorted(rows, key=lambda x: (not x[5], x[0], x[1], x[2])):
        verdict = "pass" if ok else f"**FAIL** (needs {THRESHOLD[role]}:1)"
        lines.append(f"| `{fg}` | `{bg}` | {ROLE_LABEL[role]} | {r:.2f}:1 | {verdict} | {use} |")
    return "\n".join(lines)


def palette(tok, prefix):
    names = sorted((n for n in tok if re.fullmatch(prefix + r"\d+", n)), key=lambda n: int(n.rsplit("-", 1)[1]))
    return [(n, tok[n]) for n in names]


def palette_problems(tok):
    probs, notes = [], []
    cat = palette(tok, "--ha-chart-cat-")
    seq = palette(tok, "--ha-chart-seq-")
    div = palette(tok, "--ha-chart-div-")
    if not (cat and seq and div):
        return ["chart palette tokens (--ha-chart-cat-/seq-/div-N) missing"], notes
    for v in VISIONS:
        worst = min(((de2000(simulate(a, v), simulate(b, v)), na, nb)
                     for i, (na, a) in enumerate(cat) for nb, b in cat[i + 1:]))
        notes.append(f"categorical {v}: min dE2000 {worst[0]:.1f} ({worst[1]} vs {worst[2]})")
        if worst[0] < CAT_MIN_DE:
            probs.append(f"categorical {worst[1]} / {worst[2]} only dE {worst[0]:.1f} under {v} (< {CAT_MIN_DE})")
    Ls = [to_lab(c)[0] for _, c in seq]
    steps = [abs(b - a) for a, b in zip(Ls, Ls[1:])]
    mono = all(b < a for a, b in zip(Ls, Ls[1:])) or all(b > a for a, b in zip(Ls, Ls[1:]))
    notes.append("sequential L*: " + " ".join(f"{x:.0f}" for x in Ls))
    if not mono or min(steps) < SEQ_MIN_STEP:
        probs.append(f"sequential lightness not monotonic with steps >= {SEQ_MIN_STEP} L*")
    if len(div) % 2 == 0:
        probs.append("diverging palette needs an odd count (neutral midpoint)")
    else:
        mid = len(div) // 2
        Ld = [to_lab(c)[0] for _, c in div]
        notes.append("diverging L*: " + " ".join(f"{x:.0f}" for x in Ld))
        left, right = Ld[:mid + 1], Ld[mid:]
        if not (all(b > a for a, b in zip(left, left[1:])) and all(b < a for a, b in zip(right, right[1:]))):
            probs.append("diverging arms must lighten monotonically toward the midpoint")
        for v in VISIONS:
            d = min(de2000(simulate(div[i][1], v), simulate(div[-1 - i][1], v)) for i in range(mid))
            notes.append(f"diverging {v}: min mirrored dE2000 {d:.1f}")
            if d < DIV_MIN_DE:
                probs.append(f"diverging arms only dE {d:.1f} apart under {v} (< {DIV_MIN_DE})")
    white = tok["--ha-white"]
    low = [f"{n} {contrast(c, white):.1f}:1" for n, c in cat if contrast(c, white) < 3]
    if low:
        notes.append("categorical below 3:1 on white (pair with a direct label or outline): " + ", ".join(low))
    return probs, notes


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--write", action="store_true", help="regenerate the contrast table in DESIGN.md")
    g.add_argument("--check", action="store_true", help="fail if DESIGN.md is stale or a palette rule breaks")
    a = ap.parse_args()

    tok = parse_tokens(TOKENS.read_text())
    rows = contrast_rows(tok)
    table = contrast_table(rows)
    probs, notes = palette_problems(tok)
    fails = [r for r in rows if not r[5]]

    for fg, bg, role, use, r, _ in fails:
        print(f"FLAG  {fg} on {bg} ({ROLE_LABEL[role]}): {r:.2f}:1 < {THRESHOLD[role]}:1 — {use}")
    print(f"contrast: {len(rows) - len(fails)}/{len(rows)} pairs pass WCAG AA")
    for n in notes:
        print("  " + n)
    for p in probs:
        print("ERROR " + p)

    text = DESIGN.read_text()
    block = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)
    if not block.search(text):
        sys.exit(f"DESIGN.md has no {START} … {END} block")
    new = block.sub(lambda _: f"{START}\n{table}\n{END}", text)
    if a.write:
        DESIGN.write_text(new)
        print("wrote DESIGN.md contrast table")
    elif a.check and new != text:
        probs.append("DESIGN.md contrast table is stale: run python3 scripts/check_design_tokens.py --write "
                     "(a token change moved a pair's ratio or verdict)")
        print("ERROR " + probs[-1])
    return 1 if probs else 0


if __name__ == "__main__":
    sys.exit(main())
