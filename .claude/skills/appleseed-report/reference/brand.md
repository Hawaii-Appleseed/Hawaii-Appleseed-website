# Hawaiʻi Appleseed brand system — exact values

Extracted from the five canonical issue deep-dive pages at the repo root. Best single exemplar: **`taxes-budget.html`** (tokens L215–222, components L550–1760).

## Palette

```css
--ha-charcoal:  #2F3E46;   /* text, dark backgrounds, nav/footer */
--ha-slate:     #354F52;   /* gradient partner to charcoal */
--ha-teal-deep: #52796F;   /* PRIMARY accent — links, eyebrows, rules */
--ha-teal:      #84A98C;   /* highlights, buttons on dark */
--ha-ash:       #CAD2C5;   /* text on dark backgrounds */
--ha-bg:        #F4F7F4;   /* page tint */
--ha-white:     #FFFFFF;
--ha-rule:      rgba(53,79,82,.14);   /* hairline borders — Slate @ 14% */
```

**Naming trap:** `--ha-teal-deep` (#52796F) is the *darker* one and the workhorse — it outnumbers `--ha-teal` about 4:1 (75 vs 18 uses per page).

**Tokens live on the page namespace class, not `:root`:** `.ha-tax { --ha-charcoal: … }`. This keeps the block pasteable into Squarespace without leaking. **A new component outside the namespace gets no tokens.**

Defined identically in `taxes-budget.html` · `housing.html` · `food-security.html` · `transportation.html` · `wages-labor.html` · `issues.html` (superset, adds `--ha-ash-light:#E5E9E2`, `--ha-rule-dark:rgba(202,210,197,.18)`) · `our-mission.html` · `our-story.html` · `our-team.html` · `board-of-directors.html` · `publications.html` · all `squarespace-ready/` mirrors.

**Older unprefixed set** (same hexes) in `index.html` L25–41 and `support.html`: `--teal` `--deep-teal` `--dark-slate` `--charcoal` `--ash` `--ash-light:#E8EDE6` `--cream:#F4F7F5` `--white`, plus the only motion tokens on the site: `--ease-out:cubic-bezier(.22,.61,.36,1)` `--dur-fast:.2s` `--dur-base:.4s` `--dur-slow:.6s`. Minor drift: `--cream:#F4F7F5` vs `--ha-bg:#F4F7F4`; `--ash-light` `#E8EDE6` vs `#E5E9E2`.

A third variant is in `content-search/css/brand.css` L5–11 (now in the `staff-updates-internal` repo, not this one), whose header cites the source of truth: *"Hawaiʻi Appleseed Brand Guide (April 2026 v1.0)"*.

**Use the `--ha-*` set for new work** — 26 definition sites vs 9, and it's what the canonical pages use.

### Off-brand files — do not use as references

- `millionaire-report/index.html` — Nunito + an unrelated green palette (`#1A3C34`, `#6ABC7A`, `#2A6B4F`). Never migrated.
- `tax-fairness/` — separate coalition identity by design (`--navy:#16314e`, `--amber:#e8920c`).
- `snap-medicaid-timeline/` — its own viz palette.

### Legacy sage-green: already gone

`--sage-*` and `--appleseed:#3a7811` **no longer exist in the repo** — removed in commits `63ef507` and `422c211`. They survive only as the prohibition text in `CLAUDE.md`. The word "sage" persists in descriptive CSS comments and in `issues.html`'s per-issue tints, which are brand-family values, not the forbidden green:

```css
.ha-deep[data-color="tax-budget"]  { --section-bg:#F2F4EF; --section-accent:var(--ha-slate); }
.ha-deep[data-color="food"]        { --section-bg:#E6EFE9; --section-accent:var(--ha-teal-deep); }
.ha-deep[data-color="housing"]     { --section-bg:#D9E2D8; --section-accent:var(--ha-teal-deep); }
.ha-deep[data-color="transit"]     { --section-bg:#E2E8E8; --section-accent:var(--ha-slate); }
.ha-deep[data-color="wages-labor"] { --section-bg:#EDEDE5; --section-accent:var(--ha-teal-deep); }
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

**There are no named spacing tokens** — no `--space-*` or scale variables. Literal px, but highly regular.

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
