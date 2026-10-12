---
type: llm
---
Judge the python-pptx script against the Hawaiʻi Appleseed slide rules: starts from the brand template or sets brand colours (Charcoal #2F3E46 text, Deep Teal #52796F accent) and fonts (Manrope headings, Poppins body); dark Charcoal title/closing slides with the white logo; left-aligned text; at most one Deep Teal accent per slide; no stock clip-art, bright colours or serif fonts; spells Hawaiʻi with the ʻokina (U+02BB) in slide text.

A script that opens `appleseed-slides.pptx` and builds on its layouts (Title Slide / Section Header are the dark Charcoal layouts with the white logo; Title and Content is the light one) gets its colours, fonts and logo from the template: don't require them to be restated in code, and count a dark layout as a dark slide. Judge only what the code itself adds or overrides.

PASS if it follows the rules (missing the ʻokina alone is a FAIL). FAIL otherwise.
