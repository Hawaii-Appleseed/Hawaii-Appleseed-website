---
name: appleseed-report
description: Build a Hawaiʻi Appleseed research report, policy brief, or issue page in the house structure and brand system — cover, executive summary, subject-named sections, recommendations, numbered endnotes, figures. Ships as an editable primer-editor project or a Word .docx. Use when asked to write, draft, structure, or format an Appleseed report/brief/publication, or to put Appleseed content into brand HTML.
---

# Hawaiʻi Appleseed report

Builds a report in the house structure and brand system, then hands off to whichever output you need.

**For the prose itself, use the `appleseed-voice` skill** — it carries the voice rules, positions.md integrity checks, and the corpus. This skill governs *structure and format*. Both apply to a report.

> **Paths in this skill are relative to the repo root** (`Hawaii-Appleseed-website`) — run from there. **One exception:** Step 6's primer-editor output needs a *separate* repo cloned; everything else resolves inside this one.

## Step 1 — Pick the tier

Real published reports fall into three bands (measured across 42 publications):

| Tier | Words | Shape |
|---|---|---|
| **Brief / primer** | 2,200–4,200 | Often no executive summary; leads with Background. 2–3 sections. |
| **Standard report** | 5,000–7,500 | Full architecture. 3–5 middle sections. |
| **Flagship** | 8,500–11,300 | Adds glossary, case studies, sometimes appendix. |

Median across all reports is ~5,400 words. Ask the user if the tier isn't obvious — it drives everything downstream.

**Testimony is a different document** (median 450 words, no sections, bracketed `[1]` cites). If the task is testimony, follow the testimony structure in `positions.md` §Voice signature, not this skill. **Blog posts** (median 804 words, no section headings at all) are `appleseed-voice` territory.

## Step 2 — Build the section architecture

**Only the bookends are generic. The middle sections are named to the subject — never "Background," "Analysis," or "Findings."**

Measured frequency across 42 reports:

| Section | Files | Share |
|---|---|---|
| Endnotes | 39 | **93%** |
| Table of Contents | 31 | 74% |
| Executive Summary | 22 | 52% |
| Recommendations | 18 | 43% |
| Introduction | 8 | 19% |
| Conclusion | 4 | 10% |
| Methodology | 4 | 10% |

Canonical order:

```
Executive Summary
  → 2–5 subject-named sections: problem → mechanism → evidence/comparison → local impact
  → Recommendations (named to the subject)
  → Endnotes
```

The **"proven model elsewhere" section is near-obligatory** — real ones: `Parking Reform On The Continent`, `Lessons From National Programs`, `Case Studies`.

Real tables of contents to model:

- *Who Pays for Climate Disasters?* — Executive Summary · Glossary of Terms · Issue Overview · Key Factors in Market Destabilization · Equity and Climate Justice · Case Studies · Policy Intervention Recommendations · Endnotes
- *Stalled* — Executive Summary · How Parking Impacts Affordable Housing · Efforts To Reduce Parking Mandates · Parking Reform On The Continent · Impacts Of Oʻahu Parking Reform · Recommendations To Further The Impact Of Ordinance 20-41 · Endnotes
- *Pedestrian Head Start* (brief) — Background · Accessible Pedestrian Signals · Leading Pedestrian Intervals · Lessons From National Programs · Benefits · Costs · Recommendations for Hawaiʻi · Endnotes

Section headings are ALL CAPS in the PDFs, and each section's **first few words open in caps** as a lead-in: "OVER THE PAST SEVERAL DECADES, the United States has experienced…"

## Step 3 — Title and front matter

**Title is a short punchy word or two; the explanation lives in the deck.** `Stalled` / *How Parking Mandates Drive Up Housing Costs*. Others: `Concentrating Wealth`, `Beyond the Ticket`, `Rethinking Roads`, `Who Pays for Climate Disasters?`, `Keiki Ride Free`. The deck runs ~14 words (range 5–39) and becomes the site excerpt.

**Cover:** Month + Year · logo lockup · title in caps · subtitle.

**Inside front:** logo + `www.hiappleseed.org` · `Author:` line (79% of reports carry one, often with title — "Author: Devin Thomas, Hawaiʻi Budget & Policy Center Policy Analyst") · the two-paragraph org boilerplate · Table of Contents with page numbers · copyright line.

The **copyright line appears in 100% of reports**, verbatim:
> Copyright © YYYY Hawaiʻi Appleseed Center for Law & Economic Justice. All rights reserved. 733 Bishop Street, Suite 1180, Honolulu, HI 96813

The org boilerplate (identical in 24/42 — the current template) is in `reference/report-architecture.md`. Running footer on every page: `N • SHORT TITLE` in caps.

## Step 4 — Citations and figures

**Numbered endnotes. No inline parentheticals, no bibliography, no page-bottom footnotes.**

Density tracks argument, not length: median 30, range 11–123. Markers are superscript numerals on the sentence or figure caption.

```
121.  Mizuo, Ashley, "As stakeholders navigate building code updates, counties bear
      the burden," Hawaiʻi Public Radio, August 27, 2024. https://www.hawaiipublicradio.org/...
```

Pattern: `N. Author Last, First[, others], "Title," Publishing Org, Month DD, YYYY. URL`. Authorless works start at the quoted title. Repeat cites go short-form: `118. Magin, June 21, 2024`.

**Figures** (81% of reports have them): caption **above**, source line **below**.

- Caption: `Figure N. Descriptive Title Case Caption[, Jurisdiction][ (Year)][superscript]`
- Real: `Figure 1. Average Act 46 Tax Cut By Income Group, Hawaiʻi (2025)³`
- Source line below: `Source: California FAIR Plan` — and source lines carry methodology caveats: *"Source: Data Axle. The data are incomplete. As a result, the estimates in Figure 3 undercount the true number of residents who left."*
- Reference figures in prose, never "(Fig. 1)": "Figure 1 shows how rates…" / "…as demonstrated in Figure 1, below."
- Photo credits use `//`: "…life-saving warnings. // NOAA, Public domain, via Wikimedia Commons"

## Step 5 — Render in the brand system

Read `reference/brand.md` for exact tokens, type scale, spacing, and component CSS. Non-negotiables:

- **Tokens are `--ha-*`, declared on a page namespace class, never on `:root`** — so the block can be pasted into Squarespace without leaking. New components must live inside the namespace or they get no tokens.
- **`--ha-teal-deep: #52796F` is the workhorse accent** (not `--ha-teal: #84A98C`, which is lighter despite the name).
- **Font stacks must start with the ʻokina face:** `OkinaManrope, 'Manrope', sans-serif` and `OkinaPoppins, 'Poppins', system-ui, -apple-system, Arial, sans-serif`. Neither Manrope nor Poppins ships U+02BB, and Google's latin face claims the codepoint without providing the glyph — omit the Okina face and ~300 ʻokina fall back to the OS UI font.
- **Manrope = headings/display/buttons/stat numbers/eyebrows. Poppins = body, nav, small labels, and all italics.** Manrope has no true italic on Google Fonts — never set `font-style:italic` on it.
- **Body text is never solid charcoal** — it's charcoal at 65–85% alpha. `rgba(47,62,70,.78)` is the standard.
- **Verify at 375px before desktop.** The primary breakpoint is `max-width:700px`; 375px also exercises the 800px, 600px, and 1000px queries. Mobile side padding is universally 20px; section padding `56px 20px`. CTA buttons stack full-width.

## Step 6 — Ship it

Both paths start from a self-contained brand HTML file.

**→ Editable primer-editor project** (live editing, web publish):

**This path needs a second repo.** `primer-editor` is not part of this one. Clone it if you don't have it:

```bash
git clone https://github.com/Hawaii-Appleseed/primer-editor.git ~/primer-editor
```

Then scaffold (adjust the path if you cloned it elsewhere):

```bash
python3 ~/primer-editor/docsync/scaffold.py <path-to-report.html> --id <slug> --title "<Title>"
```

Creates `~/primer-editor/projects/<slug>/` with `content.md`, `layout.json`, `render_report.py`, `index.html`. Then:

- Any file `render_report.py` reads **must be listed under `docsync.yml` `editor.engine`** or Pyodide can't see it.
- Every SVG/graphic must use `graphic(el_id, svg, w=…)` in `render_report.py` — a bare `<svg>` is frozen and can't be moved or resized in the editor.
- **Never write `content.md`/`layout.json` while the editor is open** — use the `/__pilot` API instead; concurrent writes clash and changes go invisible.
- **Never start or kill `serve.py` yourself.** "Budget Primer Editor.app" owns it. Ask the user to relaunch the app.
- Save is pre-authorized at checkpoints. **Push publishes the live site and needs an explicit per-message go-ahead.**

**→ Word .docx** (funders, coalition markup, internal circulation): use the `anthropic-skills:docx` skill. Carry over Manrope/Poppins (fall back to Arial), the `--ha-*` palette, ALL CAPS section headings, numbered endnotes, and figure caption-above/source-below.

## Before delivering

- Every claim sourced to `positions.md` or a corpus document — **flag anything you couldn't source rather than shipping it**
- Endnotes numbered continuously, every marker resolves
- Figures numbered in order, each with a source line
- ʻokina is U+02BB throughout (`grep -n "Hawaii[^ʻ]"` and `grep -n "Hawai'i"` both empty)
- "percent" not "%", zero exclamation points
- Rendered HTML checked at **375px** first, then desktop
