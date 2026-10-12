---
name: appleseed-brand
description: Hawaiʻi Appleseed's brand — exact colors, fonts, logo and layout rules. Use this whenever you make or style ANYTHING for Hawaiʻi Appleseed (Hawaii Appleseed Center for Law & Economic Justice) — a document, report, policy brief, memo, letter, slide deck, presentation, chart, graph, infographic, social graphic, flyer, one-pager, handout, email header, web page or HTML — or when someone says "on brand", "Appleseed colors", "Appleseed style", "our brand", or asks to make something look like Appleseed. Also use when checking or fixing whether something is on brand. No coding knowledge needed.
---

# Hawaiʻi Appleseed brand

Apply this to anything carrying the Appleseed name. Calm, credible, grounded: deep teal-greens and charcoal on light ash, generous white space, bold sans-serif headlines. Never bright or neon; never the old sage-green (`#3a7811`).

## Colors (use these exact values — nothing else)

| Name | Hex | Use it for |
|---|---|---|
| Charcoal | `#2F3E46` | Body text, dark backgrounds, headers/footers |
| Slate | `#354F52` | Second dark; gradients with Charcoal |
| **Deep Teal** | `#52796F` | **Main accent** — links, headings accents, eyebrow labels, key numbers, chart's primary series |
| Teal | `#84A98C` | Highlights, buttons on dark, secondary series |
| Ash | `#CAD2C5` | Text on dark backgrounds, soft borders, tertiary series |
| Ash Light | `#E5E9E2` | Callout/box fills |
| Page tint | `#F4F7F4` | Light background |
| White | `#FFFFFF` | Background, text on dark |
| Hairline | Slate at 14% (`rgba(53,79,82,.14)`) | Thin divider lines |
| Teal Ink | `#3F5F57` | Small teal text on Ash, Ash Light or an issue tint (see Small text) |
| Teal Bright | `#B0C8B4` | Small teal text on Charcoal or Slate (see Small text) |

Deep Teal (`#52796F`) is the *darker* teal and the workhorse; use plain Teal sparingly. Issue tints (light backgrounds per topic): Tax/budget `#F2F4EF` · Food `#E6EFE9` · Housing `#D9E2D8` · Transportation `#E2E8E8` · Wages/labor `#EDEDE5`.

## Small text (under 24px): pick the colour by background

The brand teals are too faint for small text on some fills. Labels, eyebrows, dates, tags and captions use:

| Background | Small text | Never |
|---|---|---|
| White, Page tint | Charcoal, Slate, Deep Teal | Teal, Ash |
| Ash, Ash Light, issue tints, pale teal chips | Charcoal, Slate, **Teal Ink** | Deep Teal, Teal |
| Charcoal, Slate | White, Ash, **Teal Bright** | Teal, Deep Teal |

Muted text: Charcoal at 74% or more on light, White at 70% or more on dark. Don't fade small text with transparency or `opacity` below that. Headlines and big numbers (24px and up) can use Deep Teal or Teal as before. Buttons: Charcoal label on a Teal fill is the current site style but falls just short (4.2:1); for new work make the label 19px bold, or use a Deep Teal fill with a White label.

## Fonts

- **Manrope** (bold 700–800) — headlines, titles, big numbers, buttons, small ALL-CAPS labels.
- **Poppins** (regular 400, medium 500) — body text and **all italics** (Manrope has no real italic).
- No serif fonts. Both are free on Google Fonts. If unavailable (e.g. PowerPoint/Word without them installed), fall back to Arial/Helvetica, and say so.
- Spell **Hawaiʻi** with the ʻokina (U+02BB `ʻ`), not an apostrophe. On web pages, check the ʻokina renders (see `reference/web-design-guide.md` → Fonts).

## Layout and voice

- Headlines: tight and heavy (Manrope 800, slightly negative letter-spacing). Small teal ALL-CAPS "eyebrow" label above section titles, widely letter-spaced.
- Lots of white space; left-aligned text; thin hairline dividers instead of boxes. Rounded corners kept small (≈6–12px).
- Dark sections: Charcoal→Slate gradient with Ash/White text; Teal accents on large type, Teal Bright on small labels.
- Plain, confident language; lead with the number or the finding.

## By medium

- **Slides:** White or page-tint background; title in Manrope Charcoal; one Deep Teal accent per slide; dark Charcoal title/closing slides with white logo.
- **Charts:** use the chart palette below (colour-blind safe). Gridlines = hairline; axis text Charcoal at small size; label series directly instead of relying on a legend; no 3-D, no gradients, no rainbow. Highlight one bar/line in Deep Teal and grey the rest in Ash when telling one story. Put a source note under every chart.
- **Documents/reports/flyers:** Charcoal body text in Poppins; headings Manrope; callout boxes in Ash Light with a Deep Teal left rule; logo top or bottom, never stretched.
- **Web/HTML:** Paste `reference/tokens.css` and use `var(--ha-*)` names — no raw hex in the CSS. Full component specs (type scale, spacing, breakpoints): `reference/web-design-guide.md`.

## Chart palette (colour-blind safe — use exactly these)

- **Categories** — any chart where each line, bar group or slice is its own series, **including years or other ordered groups drawn as separate lines/bars** (in this order; never more than 6 — group the rest as "Other" in Ash `#CAD2C5`): Deep Teal `#52796F` · Charcoal `#2F3E46` · Ochre `#BF8A30` · Harbor blue `#6A8CC4` · Clay `#A85A45` · Teal `#84A98C`. Teal is light, so give it a direct label or a thin Charcoal outline.
- **Sequential** (low → high, for **shading only**: a map or heatmap shaded by rate, never separate lines or bars — its light steps vanish on white): `#E5E9E2` `#B4C9B6` `#84A98C` `#6B917D` `#52796F` `#405B5A` `#2F3E46`. Use 3–7 evenly spaced steps.
- **Diverging** (above/below a midpoint, e.g. change since last year): `#2B4A45` `#52796F` `#A9C3B3` · neutral `#F2F0EA` · `#E0BF85` `#B07A35` `#6E4524`. Teal side = above/better, brown side = below/worse.

These were checked under simulated red-, green- and blue-blindness; don't substitute other greens and reds. For which text colours pass on which background, see **Small text** above; the measured table is `reference/web-design-guide.md` → Contrast.

## Templates

- **PowerPoint:** `templates/appleseed-slides.pptx` — 16:9, dark title/section layouts with the white logo, content layouts with the logo and a Deep Teal rule, theme colours = the chart palette (so inserted charts come out on brand), Manrope/Poppins theme fonts. Start decks from it: delete the sample slides, keep the layouts.
- **Word:** `templates/appleseed-document.docx` — Title, Heading 1–3, Eyebrow, Callout (Ash Light fill, Deep Teal rule), Quote, Source Note styles; logo header; footer with org name and page number.

If you generate a .pptx/.docx with code (python-pptx, python-docx), open the template file as the starting document rather than a blank one. Point the script at the template with a path the user can run it from (copy `templates/appleseed-slides.pptx` next to the script, or take the path as an argument); never hard-code the path to this skill's folder. Its layouts, by index and name (python-pptx `prs.slide_layouts[i]`): **0 Title Slide** (dark Charcoal, white logo; title + subtitle) · **1 Title and Content** (light; title + body) · **2 Section Header** (dark, white logo; use it for section breaks and the closing slide) · **3 Two Content** · **4 Comparison** · **5 Title Only** (light; for a chart or table you add) · **6 Blank**. Pick layouts by these indexes rather than guessing names, and let the theme colours and fonts carry the look instead of overriding them on every run. Where Manrope/Poppins aren't installed, Office falls back to Arial — say so.

## Logo

`assets/logo.png` (color, for light backgrounds), `assets/logo-white.png` (for dark backgrounds), `assets/logo-mark.png` (the mark alone). Keep proportions; give it clear space; don't recolor or put the color logo on dark.

## Check before you hand it over

Run the bundled checker on every file you made (HTML, CSS, SVG, Markdown, or chart/slide code):

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/check_brand.py" path/to/file.html
```

On Claude.ai, run `scripts/check_brand.py` from this skill's folder the same way. It flags off-palette colours, the old sage-green, non-brand or serif fonts, small text that fails contrast (including faded text and Teal under 24px), italic Manrope, and "Hawaii" without the ʻokina. Fix every ERROR before you deliver; a WARN is a judgement call (a proper name or a URL may be spelled as-is). If you deliberately keep a flagged line, end it with a `brand-check: allow` comment and say why.

## Quick on-brand check

Colors only from the table · Manrope headlines / Poppins body · Deep Teal is the accent · ʻokina in Hawaiʻi · no sage-green, no bright colors, no serif.
