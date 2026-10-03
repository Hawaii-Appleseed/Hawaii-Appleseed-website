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

Deep Teal (`#52796F`) is the *darker* teal and the workhorse; use plain Teal sparingly. Issue tints (light backgrounds per topic): Tax/budget `#F2F4EF` · Food `#E6EFE9` · Housing `#D9E2D8` · Transportation `#E2E8E8` · Wages/labor `#EDEDE5`.

## Fonts

- **Manrope** (bold 700–800) — headlines, titles, big numbers, buttons, small ALL-CAPS labels.
- **Poppins** (regular 400, medium 500) — body text and **all italics** (Manrope has no real italic).
- No serif fonts. Both are free on Google Fonts. If unavailable (e.g. PowerPoint/Word without them installed), fall back to Arial/Helvetica, and say so.
- Spell **Hawaiʻi** with the ʻokina (U+02BB `ʻ`), not an apostrophe. On web pages, check the ʻokina renders (see `reference/web-design-guide.md` → Fonts).

## Layout and voice

- Headlines: tight and heavy (Manrope 800, slightly negative letter-spacing). Small teal ALL-CAPS "eyebrow" label above section titles, widely letter-spaced.
- Lots of white space; left-aligned text; thin hairline dividers instead of boxes. Rounded corners kept small (≈6–12px).
- Dark sections: Charcoal→Slate gradient with Ash/White text and Teal accents.
- Plain, confident language; lead with the number or the finding.

## By medium

- **Slides:** White or page-tint background; title in Manrope Charcoal; one Deep Teal accent per slide; dark Charcoal title/closing slides with white logo.
- **Charts:** Primary series Deep Teal `#52796F`, then Charcoal `#2F3E46`, Teal `#84A98C`, Ash `#CAD2C5`. Gridlines = hairline; axis text Charcoal at small size; no 3-D, no gradients, no rainbow. Highlight one bar/line in Deep Teal and grey the rest in Ash when telling one story.
- **Documents/reports/flyers:** Charcoal body text in Poppins; headings Manrope; callout boxes in Ash Light with a Deep Teal left rule; logo top or bottom, never stretched.
- **Web/HTML:** Paste `reference/tokens.css` and use `var(--ha-*)` names — no raw hex in the CSS. Full component specs (type scale, spacing, breakpoints): `reference/web-design-guide.md`.

## Logo

`assets/logo.png` (color, for light backgrounds), `assets/logo-white.png` (for dark backgrounds), `assets/logo-mark.png` (the mark alone). Keep proportions; give it clear space; don't recolor or put the color logo on dark.

## Quick on-brand check

Colors only from the table · Manrope headlines / Poppins body · Deep Teal is the accent · ʻokina in Hawaiʻi · no sage-green, no bright colors, no serif.
