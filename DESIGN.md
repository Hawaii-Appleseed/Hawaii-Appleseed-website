# Hawaiʻi Appleseed design system

The brand spec for the site and anything Appleseed-branded. **Tokens live in [`assets/tokens.css`](assets/tokens.css)** on `:root`; every page links it before its own `<style>`. Page CSS uses `var(--ha-*)` only — **no raw hex/rgba and no px `font-size`** (CI lints changed lines; see [Checks](#checks)). Need a new value? Add a token there, then use it. Best single exemplar of components: **`taxes-budget.html`**.

Source of truth upstream: *Hawaiʻi Appleseed Brand Guide (April 2026 v1.0)*. A portable copy of this guide for Claude.ai lives in `brand-skill/appleseed-brand/`; `python3 scripts/build_brand_skill.py` copies this file and `tokens.css` into it and rebuilds the zip (CI fails if you forget).

## Palette

```css
--ha-charcoal:   #2F3E46;   /* text, dark backgrounds, nav/footer */
--ha-slate:      #354F52;   /* gradient partner to charcoal */
--ha-teal-deep:  #52796F;   /* PRIMARY accent — links, eyebrows, rules */
--ha-teal:       #84A98C;   /* highlights, buttons on dark */
--ha-ash:        #CAD2C5;   /* text on dark backgrounds */
--ha-ash-light:  #E5E9E2;   /* light fills, callouts */
--ha-bg:         #F4F7F4;   /* page tint */
--ha-white:      #FFFFFF;
--ha-rule:       rgba(53,79,82,.14);    /* hairline borders on light — Slate @ 14% */
--ha-rule-dark:  rgba(202,210,197,.18); /* hairlines on dark — Ash @ 18% */
--ha-rule-light: rgba(202,210,197,.30); /* stronger hairlines on dark */
--ha-ink-muted:  rgba(47,62,70,.78);    /* lede paragraphs */
--ha-ink-subtle: rgba(47,62,70,.65);    /* stat labels, source notes — fails AA small text, see Contrast */
/* Issue tints: --ha-tint-tax #F2F4EF · -food #E6EFE9 · -housing #D9E2D8 · -transit #E2E8E8 · -wages #EDEDE5 */
/* Motion: --ha-ease-out cubic-bezier(.22,.61,.36,1) · --ha-dur-fast .2s · --ha-dur-base .4s · --ha-dur-slow .6s */
```

**Naming trap:** `--ha-teal-deep` (#52796F) is the *darker* one and the workhorse — it outnumbers `--ha-teal` about 4:1.

**Squarespace exception:** `squarespace-ready/` and the `*squarespace*` inject snippets are pasted into Squarespace, which can't load `assets/tokens.css`, so they keep an inline token block scoped to the page namespace class (`.ha-tax { --ha-charcoal: … }`). Keep those copies in step with `tokens.css` by hand.

**Consolidation (Oct 2026, branch `design-tokens`):** the per-page pasted blocks were deleted. Drift resolved to the values above: `--ha-rule` .18→.14 (board, issues, our-mission(-light), our-story(-light), our-team); `--ha-bg` #F6F8F5→#F4F7F4 (publications, addon-policies). `index.html`, `support.html`, `preview/` and the hero prototypes moved from the old unprefixed names (`--teal --deep-teal --dark-slate --charcoal --ash --ash-light --cream --white --ease-out --dur-*`) to `--ha-*`; `--cream` #F4F7F5→`--ha-bg` #F4F7F4 and `--ash-light` #E8EDE6→#E5E9E2.

### Off-brand files — do not use as references

- `millionaire-report/index.html` — Nunito + an unrelated green palette (`#1A3C34`, `#6ABC7A`, `#2A6B4F`). Never migrated.
- `tax-fairness/` — separate coalition identity by design (`--navy:#16314e`, `--amber:#e8920c`).
- `snap-medicaid-timeline/` — its own viz palette.

### Legacy sage-green: already gone

`--sage-*` and `--appleseed:#3a7811` **no longer exist in the repo** — removed in commits `63ef507` and `422c211`. They survive only as the prohibition text in `CLAUDE.md`. The word "sage" persists in descriptive CSS comments and in `issues.html`'s per-issue tints, which are brand-family values, not the forbidden green:

```css
.ha-deep[data-color="tax-budget"]  { --section-bg:var(--ha-tint-tax); --section-accent:var(--ha-slate); }
.ha-deep[data-color="food"]        { --section-bg:var(--ha-tint-food); --section-accent:var(--ha-teal-deep); }
.ha-deep[data-color="housing"]     { --section-bg:var(--ha-tint-housing); --section-accent:var(--ha-teal-deep); }
.ha-deep[data-color="transit"]     { --section-bg:var(--ha-tint-transit); --section-accent:var(--ha-slate); }
.ha-deep[data-color="wages-labor"] { --section-bg:var(--ha-tint-wages); --section-accent:var(--ha-teal-deep); }
```

## Fonts

```html
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Manrope:wght@300;400;500;600;700;800&family=Poppins:ital,wght@0,300;0,400;0,500;0,600;0,700;1,300;1,400;1,500;1,600;1,700&display=swap">
```

```css
/* Headings / display / UI labels */
font-family: OkinaManrope, 'Manrope', sans-serif;
/* Body, nav, small labels, ALL italics */
font-family: OkinaPoppins, 'Poppins', system-ui, -apple-system, Arial, sans-serif;
```

**The Okina face must come first.** `OkinaManrope`/`OkinaPoppins` are defined in `assets/okina.css` (also inlined into `squarespace-footer.html` and `video-hero/squarespace-inject.html`) as base64 woff2 with `unicode-range: U+02BB`. Neither Manrope nor Poppins ships U+02BB, and adding it to the real families doesn't work — Google's latin face claims the codepoint in its unicode-range without shipping the glyph. Omit the Okina face and ~300 ʻokina fall back to the OS UI font.

- **Manrope:** headings, display, buttons, stat numbers, eyebrows, footer `h4`.
- **Poppins:** body, lead paragraphs, nav, small labels, and **every italic** — Manrope has no true italic on Google Fonts, so italic on it would faux-slant.
- Weights actually used: 700 ×183 · 600 ×132 · 800 ×90 · 500 ×55 · 400 ×19. **Essentially no 300** despite being loaded.
- No serif anywhere. Fraunces is gone.

## Type scale

**Tokens** (in `tokens.css`; the `≤700px` block on `:root` swaps in the mobile size, so pages don't need their own media query for these):

| Token | Desktop | ≤700px | Role |
|---|---|---|---|
| `--ha-fs-hero` | 78px | 48px | Hero H1 |
| `--ha-fs-display` | 54px | 30px | Big stat headline |
| `--ha-fs-cta` | `clamp(30px,4.2vw,48px)` | — | CTA H2 |
| `--ha-fs-h2-lg` | 44px | 28px | Vision H2 |
| `--ha-fs-h2` | 38px | 28px | Section H2 |
| `--ha-fs-stat` | 28px | — | Priority stat number |
| `--ha-fs-h3` | 26px | — | Card H3 |
| `--ha-fs-h4` | 24px | — | Callout heading, pull-quote |
| `--ha-fs-stat-sm` | 22px | — | Pillar stat number |
| `--ha-fs-h5` | 18px | — | Pillar H3 |
| `--ha-fs-lead` | 17px | 15px | Lede |
| `--ha-fs-body` | 15.5px | 15px | Body |
| `--ha-fs-small` | 14px | — | Card body, buttons |
| `--ha-fs-caption` | 13px | — | Captions, source notes, stat labels |
| `--ha-fs-eyebrow` | 11px | — | Eyebrow |
| `--ha-fs-micro` | 10.5px | — | Cite labels, chart annotations |

Also `--ha-font-display` / `--ha-font-body` (the Okina-first stacks below), line-heights `--ha-lh-display 1 · -heading 1.15 · -snug 1.3 · -small 1.55 · -body 1.65`, tracking `--ha-track-hero -.035em · -display -.02em · -tight -.01em · -button .04em · -eyebrow .22em`. A size the scale doesn't have (the `13.5px` button, `19px` mobile pull-quote) means pick the nearest token or add one here — not a literal in the page.

**Measured usage** (existing pages, before the tokens; kept as the record of where the scale came from):

| Role | Class | Desktop | ≤700px | Weight | Tracking | LH |
|---|---|---|---|---|---|---|
| Hero H1 | `__hero h1` | 78px | 48px | 800 | -.035em → -.03em | 1 |
| Big stat headline | `__stat-headline h2` | 54px | 30px | 800 | -.02em | 1.1 |
| CTA H2 | `__cta h2` | `clamp(30px,4.2vw,48px)` | — | 800 | -.02em | 1.12 |
| Vision H2 | `__vision h2` | 44px | 28px | 800 | -.02em | 1.12 |
| Section H2 | `__h2` | 38px | 28px | 800 | -.02em | 1.15 |
| Cross-nav H2 | `__more h2` | `clamp(24px,2.6vw,34px)` | — | 700 | -.02em | 1.15 |
| Card H3 | `__compare h3` | 26px | — | 800 | -.015em | 1.18 |
| Callout H | `__callout-q` | 24px | — | 700 | — | 1.3 |
| Pillar H3 | `__vision-pillar h3` | 18px | — | 700 | — | 1.25 |
| Footer H4 | `.px-footer h4` | 14px caps | — | 700 | .04em | — |

Body: lead `17px/1.65` → 15px mobile · body `15–17px/1.6–1.7` · card body `14px/1.6` · captions `13–13.5px/1.55` · micro-labels `10.5–12.5px`.

**Tracking is a strict two-mode system:** display = negative (`-.035` / `-.02` / `-.015` / `-.01em`); uppercase micro-labels = wide positive (**`.22em` is the signature eyebrow value**, used 35×; also `.18 .16 .14 .12 .04 .02 .01em`).

Line-heights: `1` display · `1.1–1.18` headings · `1.3–1.45` card titles · `1.5–1.55` small copy · `1.6–1.7` body (`1.6` is the root default).

## Spacing

**Tokens:** `--ha-space-3xs 4 · -2xs 8 · -xs 12 · -sm 16 · -md 20 · -lg 28 · -xl 36 · -2xl 48 · -3xl 56 · -4xl 72 · -5xl 80 · -6xl 96` (px). Semantic, responsive: `--ha-gutter` (section side padding, 36→20 at ≤700px) and `--ha-section-y` (section top/bottom, 80→56). Layout: `--ha-container 1200px`, `--ha-measure 680px`. Radii: `--ha-radius-pill 999px · -card 8px · -panel 6px · -callout 4px`. The standard section is `padding: var(--ha-section-y) var(--ha-gutter)` — no media query needed.

Existing pages still use the literal px below (the lint only blocks *new* px font-sizes and colours, not spacing); move them to the tokens when you touch them.

| Section type | Desktop | ≤700px |
|---|---|---|
| Standard section | `80px 36px` | `56px 20px` |
| Tight section | `48px 36px` | `48px 20px` |
| Panel body | `56px 36px` | `56px 20px` |
| Hero | `72px 28px 56px` | `40px 20px 36px` |
| CTA | `96px 28px` | `64px 20px` |
| Cross-issue nav | `72px 28px 80px` | — |
| Footer | `60px 28px 40px` | — |

`56px 20px` is the single most common value on the site (×25). **20px is the universal mobile side padding**; 28–36px desktop.

**Container max-widths:** 1200 (page shell, footer grid) · 1000 (vision panel) · 900 (hero inner) · 880 (callout) · 760 (section head, CTA inner) · 720 (pull-quote) · 680/620 (body measure) · 600 (hero sub) · 560 (chart source note).

**Radii:** `999px` ×65 — pills, tabs, buttons, the dominant shape · `8px` cards · `6px` panels · `4px` callouts · `3px` swatches · `2px` donate button.

**Rhythm:** eyebrow→h2 12px · h2→rule 22px · rule→lede 22px · head→content 48px · grid gaps 16–22px.

## Chart palette

Colour-vision-deficiency safe: `scripts/check_design_tokens.py` simulates protanopia, deuteranopia and tritanopia and fails CI if any categorical pair drops below ΔE2000 10, the sequential ramp stops being monotonic in lightness, or the diverging arms converge. Use the tokens (`var(--ha-chart-*)`, or read them with `getComputedStyle` for canvas libraries); the brand skill carries the same hex values for non-web charts.

| Kind | Tokens | Values | Use |
|---|---|---|---|
| Categorical | `--ha-chart-cat-1…6` | `#52796F` Deep Teal · `#2F3E46` Charcoal · `#BF8A30` Ochre · `#6A8CC4` Harbor blue · `#A85A45` Clay · `#84A98C` Teal | Series in this order. 1–3 alone stay in the brand family; 4–6 extend it for more series. Never more than 6 — group the rest as "Other" in `--ha-chart-muted`. |
| Sequential | `--ha-chart-seq-1…7` | `#E5E9E2 #B4C9B6 #84A98C #6B917D #52796F #405B5A #2F3E46` | Ordered magnitude (maps, heat tables), low → high. Use 3–7 evenly spaced steps. |
| Diverging | `--ha-chart-div-1…7` | `#2B4A45 #52796F #A9C3B3` · `#F2F0EA` · `#E0BF85 #B07A35 #6E4524` | Above/below a meaningful midpoint (change vs. last year, gap vs. state average). Teal arm = above/better, ochre-brown = below/worse; 4 is the neutral midpoint. |
| Support | `--ha-chart-muted` `#CAD2C5` · `--ha-chart-grid` | Ash · Slate @ 14% | De-emphasised series ("grey the rest"); gridlines. |

Rules: **label series directly** (end-of-line labels, in-bar values) rather than relying on a legend — colour is never the only cue (WCAG 1.4.1). `--ha-chart-cat-6` (Teal, 2.6:1 on white) and `--ha-chart-muted` are below the 3:1 non-text contrast line, so they need a direct label or a Charcoal outline. One-story charts: highlight the series in `--ha-chart-cat-1`, everything else `--ha-chart-muted`.

## Contrast

WCAG 2.2 AA, measured from the tokens by `python3 scripts/check_design_tokens.py` (alpha tokens composited on the background). Normal text needs 4.5:1; large text (≥24px, or ≥18.66px bold) and non-text UI/chart marks need 3:1. **Approved** = every `pass` row below for its role. The table is generated (`--write`); CI's `--check` fails if a token change moves a ratio or verdict, so an approval can't lapse silently.

**Flagged, not fixed.** These are current brand usages that fail; colours were deliberately left alone because changing a brand value is a brand decision:
- **Charcoal on Teal** pill buttons (4.23:1) — the 13.5px label is not "large". Options: 18.66px bold label, or a darker fill.
- **`--ha-ink-subtle` (Charcoal @ 65%)** stat labels and source notes (3.95 on white, 3.82 on tint), and the `.55` source notes on the issue pages are lower still. `--ha-ink-muted` (.78) passes; use it for anything small.
- **Deep Teal small text on Ash Light and the food/housing/wages tints** (3.66–4.14). Fine for headlines ≥24px; eyebrows on those fills should use Charcoal or Slate.
- **Teal (`#84A98C`) on dark** for eyebrows: passes on nothing as small text (4.23 on Charcoal, 3.36 on Slate). Large text on Charcoal is fine; small eyebrows on dark should use Ash.
- **Teal on white** fails even as a non-text mark (2.61) — chart series need a label or outline (see Chart palette); never use it for text on light.
- **Deep Teal on Charcoal** (2.28) — never.

<!-- contrast-table:start -->
| Foreground | Background | Role | Ratio | AA | Used for |
|---|---|---|---|---|---|
| `--ha-ash` | `--ha-charcoal` | normal text | 7.13:1 | pass | body text on dark |
| `--ha-ash` | `--ha-slate` | normal text | 5.66:1 | pass | body text on dark gradient end |
| `--ha-charcoal` | `--ha-ash` | normal text | 7.13:1 | pass | primary button hover |
| `--ha-charcoal` | `--ha-ash-light` | normal text | 9.00:1 | pass | callout text |
| `--ha-charcoal` | `--ha-bg` | normal text | 10.25:1 | pass | body text on page tint |
| `--ha-charcoal` | `--ha-tint-food` | normal text | 9.42:1 | pass | issue hub card |
| `--ha-charcoal` | `--ha-tint-housing` | normal text | 8.33:1 | pass | issue hub card |
| `--ha-charcoal` | `--ha-tint-tax` | normal text | 9.99:1 | pass | issue hub card |
| `--ha-charcoal` | `--ha-tint-transit` | normal text | 8.92:1 | pass | issue hub card |
| `--ha-charcoal` | `--ha-tint-wages` | normal text | 9.40:1 | pass | issue hub card |
| `--ha-charcoal` | `--ha-white` | normal text | 11.06:1 | pass | body text |
| `--ha-ink-muted` | `--ha-bg` | normal text | 5.43:1 | pass | lede on page tint |
| `--ha-ink-muted` | `--ha-white` | normal text | 5.69:1 | pass | lede paragraph |
| `--ha-slate` | `--ha-bg` | normal text | 8.14:1 | pass | secondary text on tint |
| `--ha-slate` | `--ha-tint-tax` | normal text | 7.93:1 | pass | accent on tax card |
| `--ha-slate` | `--ha-tint-transit` | normal text | 7.08:1 | pass | accent on transit card |
| `--ha-slate` | `--ha-white` | normal text | 8.78:1 | pass | secondary text |
| `--ha-teal-deep` | `--ha-bg` | normal text | 4.50:1 | pass | links/eyebrows on page tint |
| `--ha-teal-deep` | `--ha-white` | large text | 4.86:1 | pass | headline accent |
| `--ha-teal-deep` | `--ha-white` | normal text | 4.86:1 | pass | links, eyebrows, key numbers |
| `--ha-teal-deep` | `--ha-white` | non-text / UI | 4.86:1 | pass | primary chart series, focus ring |
| `--ha-white` | `--ha-charcoal` | normal text | 11.06:1 | pass | text on dark section |
| `--ha-white` | `--ha-slate` | normal text | 8.78:1 | pass | text on dark gradient end |
| `--ha-white` | `--ha-teal-deep` | normal text | 4.86:1 | pass | white on deep-teal fill |
| `--ha-ash` | `--ha-white` | non-text / UI | 1.55:1 | **FAIL** (needs 3.0:1) | tertiary chart series (avoid alone) |
| `--ha-charcoal` | `--ha-teal` | normal text | 4.23:1 | **FAIL** (needs 4.5:1) | primary pill button label |
| `--ha-ink-subtle` | `--ha-bg` | normal text | 3.82:1 | **FAIL** (needs 4.5:1) | stat labels on tint |
| `--ha-ink-subtle` | `--ha-white` | normal text | 3.95:1 | **FAIL** (needs 4.5:1) | stat labels, source notes |
| `--ha-teal` | `--ha-charcoal` | normal text | 4.23:1 | **FAIL** (needs 4.5:1) | eyebrow on dark |
| `--ha-teal` | `--ha-slate` | normal text | 3.36:1 | **FAIL** (needs 4.5:1) | eyebrow on dark gradient end |
| `--ha-teal` | `--ha-white` | large text | 2.61:1 | **FAIL** (needs 3.0:1) | teal headline on light |
| `--ha-teal` | `--ha-white` | normal text | 2.61:1 | **FAIL** (needs 4.5:1) | teal text on light (avoid) |
| `--ha-teal` | `--ha-white` | non-text / UI | 2.61:1 | **FAIL** (needs 3.0:1) | secondary chart series, rules |
| `--ha-teal-deep` | `--ha-ash-light` | normal text | 3.95:1 | **FAIL** (needs 4.5:1) | eyebrow in callout |
| `--ha-teal-deep` | `--ha-charcoal` | normal text | 2.28:1 | **FAIL** (needs 4.5:1) | deep teal on dark (avoid) |
| `--ha-teal-deep` | `--ha-tint-food` | normal text | 4.14:1 | **FAIL** (needs 4.5:1) | accent on food card |
| `--ha-teal-deep` | `--ha-tint-housing` | normal text | 3.66:1 | **FAIL** (needs 4.5:1) | accent on housing card |
| `--ha-teal-deep` | `--ha-tint-wages` | normal text | 4.13:1 | **FAIL** (needs 4.5:1) | accent on wages card |
| `--ha-white` | `--ha-teal` | normal text | 2.61:1 | **FAIL** (needs 4.5:1) | white on teal button (avoid) |
<!-- contrast-table:end -->

## Checks

| Command | What it guards | CI |
|---|---|---|
| `python3 scripts/lint_design_tokens.py [--base origin/main]` | New raw hex/rgba/hsl colours or px `font-size` in **changed lines** of `*.html`/`*.css` (excludes `tokens.css`, `squarespace-ready/`, `*squarespace*` snippets). Silence a deliberate exception with `/* design-lint: allow */` on the line. | `design-system.yml`, every PR |
| `python3 scripts/check_design_tokens.py --check` | Contrast table above is current; chart palettes stay CVD-safe. | `design-system.yml` |
| `python3 scripts/build_brand_skill.py --check` | `brand-skill/appleseed-brand/` and its zip match this file + `tokens.css`; every hex in its `SKILL.md` is a token. | `design-system.yml` |
| `uv run --with python-pptx --with python-docx scripts/build_brand_templates.py` | Regenerates the branded `.pptx`/`.docx` templates in the skill from the tokens. | — (run by hand after a palette change) |

## Components

**Naming:** BEM with a per-page namespace — `.ha-{slug}__{block}[-{element}][--{modifier}]`. Namespaces: `ha-tax` `ha-housing` `ha-food` `ha-transit` `ha-wages` `ha-issues` `ha-pub`. Shared chrome uses flat `px-*` (`px-announce`, `px-nav`, `px-links`, `px-dropdown`, `px-donate-btn`, `px-footer`).

Anchor rules need a specificity boost to survive Squarespace: `.ha-tax a.ha-tax__cta-btn`, not `.ha-tax__cta-btn`.

**Eyebrow** — the most repeated pattern (8 variants):
```css
font-size:11px; font-weight:600; letter-spacing:.22em;
text-transform:uppercase; color:var(--ha-teal-deep); margin-bottom:12px;
```
Chip variant adds `display:inline-block; background:rgba(82,121,111,.1); padding:5px 12px; border-radius:3px`. On dark, color flips to `var(--ha-teal)`.

**Lead paragraph** — `__lede`: `17px/1.65; color:rgba(47,62,70,.78); max-width:620px; margin:0 auto` → 15px mobile.

**Pull-quote** — `__vision-pullquote`:
```css
font-family:OkinaPoppins,'Poppins'; font-style:italic; font-weight:500;
font-size:24px; line-height:1.45; color:var(--ha-teal-deep);
max-width:720px; padding:18px 0 18px 28px;
border-left:3px solid var(--ha-teal); text-align:left;
```
Plus a `::before` decorative `"\201C"` at 54px in `rgba(82,121,111,.18)`. Mobile: 19px, `padding-left:22px`. Attributed variant `__priority-quote` is 15.5px with `cite` in Manrope 600 / 10.5px / `.16em` / uppercase. A giant decorative open-quote `__vision-quote` runs 120px, `line-height:.6`, `user-select:none`.

**Stat block** — two tiers, same anatomy (num over label, `border-top:1px solid var(--ha-rule)`, `padding-top:14px`):
```css
__vision-pillar-stat-num { Manrope 800; 22px; -.01em }
__priority-stat-num      { Manrope 800; 28px; -.01em }
__*-stat-label           { 12–13px; rgba(47,62,70,.65–.7); 1.45 }
__*-stat-label strong    { color:var(--ha-teal-deep); font-weight:600 }
```

**Callout** — white, `border:1px solid var(--ha-rule)`, **`border-left:4px solid var(--ha-teal-deep)`**, radius 4px, `padding:32px 36px`, `max-width:880px`. Children `-eyebrow`, `-q` (Manrope 700, 24px), `-body` (15.5px/1.65). `-body em` is de-italicized into teal 600.

**CTA** — `linear-gradient(135deg, var(--ha-charcoal) 0%, var(--ha-slate) 100%)` plus a `::before` double radial-gradient glow. Pill buttons:
```css
padding:14px 28px; border-radius:999px; Manrope 700; 13.5px; letter-spacing:.04em;
--primary { background:var(--ha-teal); color:var(--ha-charcoal) }  /* hover → --ha-ash */
--ghost   { transparent; #fff; border:1px solid rgba(202,210,197,.40) }  /* hover → --ha-teal */
/* both hover: transform:translateY(-2px) */
```
**Mobile: `flex-direction:column; width:100%`** — the stacked-CTA rule.

**Figure / chart** — `__chart-wrap` (`height:380px`), `__legend` + `-swatch`/`-label`/`-pct`, italic source note:
```css
__bar-note, __compare-source {
  text-align:center; font-size:13–14px; font-style:italic;
  color:rgba(47,62,70,.55–.7); max-width:560px; margin:0 auto; }
```
Real markup: `<p class="ha-tax__bar-note">Source: Institute on Taxation and Economic Policy, <em>Who Pays?</em> — Hawaiʻi state and local taxes, 2024.</p>`

**Glossary tooltip** — `__term` (`border-bottom:1px dotted; cursor:help`) + `__term-tip` (charcoal bubble, 260px → 220px mobile, 12.5px → 12px), on hover **and** `:focus` with `tabindex="0"`. Copy this accessibility pattern.

**Section head** — `__section-head` (centered, `max-width:760px`, `margin-bottom:48px`) → eyebrow → `__h2` → `__h2-rule`, a 108×1.5px split rule with a rotated 7px diamond `::after` — the brand's signature divider. Hero variant `__hero-rule` is a plain 56×3px teal bar.

## Breakpoints

| Query | Uses (÷5 pages) | Purpose |
|---|---|---|
| **`max-width:700px`** | **74** | **primary mobile** |
| `max-width:900px` | 30 | tablet grid collapse |
| `min-width:900px` | 5 | desktop nav reveal |
| `min-width:760px` | 5 | footer → `2fr 1fr 1fr` |
| `min-width:701px` | 5 | paired with the 700px rule |
| `max-width:800px` | 5 | 3-col pillars → 1-col |
| `max-width:1000px` | 5 | 4-col cross-nav → 2-col |
| `max-width:600px` | 5 | 2-col → 1-col |
| `prefers-reduced-motion:reduce` | 5 | accordion transitions off |

**Verifying at 375px** exercises the 700, 800, 600, and 1000px queries at once and drops below the 900/760/701 min-widths.

At ≤700px: page padding → 20px · section padding → `56px 20px` · hero 78→48 · H2s 38/44→28 · big stat 54→30 · lede 17→15 · tabs become a hidden-scrollbar horizontal scroller (`--tab-w:150px→112px`, height 46→40px) · "Research & News" pill and chart annotations `display:none` · CTA buttons stack full-width · sticky bar `top:107px→111px`.

**Fixed-chrome offsets** (these drive the sticky math): `.px-announce` is `position:fixed; top:0`, `padding:10px 18px`, 13px line-height → ~38px tall. `.px-nav` is `position:fixed; top:38px`, `padding:16px 28px` → ~107px total. Hence `__stuck-bar{top:107px}` and `section[id]{scroll-margin-top:124px}`.

## Issue-page accents

All five issue pages are **token-identical** — no per-page accent variable. The per-issue tint lives one level up, in `issues.html`'s `--section-bg`/`--section-accent` hub tints (the CSS block quoted above). Page structure — two tabs, `Overview` and `Priorities`, with "Vision" a sub-block inside Overview — is documented in `CLAUDE.md`'s mirror-format section (corrected 2026-08-20).
