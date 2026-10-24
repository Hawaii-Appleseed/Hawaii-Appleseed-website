---
name: appleseed-report
description: Build a Hawaiʻi Appleseed research report, policy brief, or issue page in the house structure and brand system — cover, executive summary, subject-named sections, recommendations, numbered endnotes, figures. Ships as an editable primer-editor project, a Google Doc in the shared drive, or a Word .docx. Use when asked to write, draft, structure, or format an Appleseed report/brief/publication, or to put Appleseed content into brand HTML.
---

# Hawaiʻi Appleseed report

Builds a report in the house structure and brand system, then hands off to whichever output you need.

**For the prose itself, use the `appleseed-voice` skill** — it carries the voice rules, positions.md integrity checks, and the corpus. This skill governs *structure and format*. Both apply to a report.

> **Where things live.** `reference/` is in `${CLAUDE_SKILL_DIR}`. Every other repo path in this skill and its reference files (`positions.md` in `writing-bot/`, `assets/okina.css`, the exemplar files `reference/report-architecture.md` cites) is in a clone of the `Hawaii-Appleseed-website` repo, written **`$W`** below. Step 6's primer-editor output needs a *separate* repo. Find `$W` before Step 1:
>
> ```bash
> W="${APPLESEED_WEBSITE:-$HOME/HawaiiAppleseed}"; test -f "$W/writing-bot/positions.md" && echo "$W"
> ```
>
> Use the absolute path it prints wherever `$W` appears below, in commands **and** file reads. Shell variables and `cd` don't carry over between tool calls, so don't rely on either. If the test fails, the repo isn't cloned (or is somewhere else: ask, and have them set `APPLESEED_WEBSITE`). Offer to clone it with `gh repo clone Hawaii-Appleseed/Hawaii-Appleseed-website ~/HawaiiAppleseed` (about 110 MB), and don't draft without positions.md.

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

**Only the bookends are generic. The middle sections are named to the subject — never "Background," "Analysis," or "Findings."** Across 42 measured reports, Endnotes are near-universal (93%), TOC 74%, Executive Summary 52%, Recommendations 43%; everything else — Introduction, Conclusion, Methodology — is the exception. Full frequency table, real TOCs, and exemplar files: `reference/report-architecture.md`.

Canonical order:

```
Executive Summary
  → 2–5 subject-named sections: problem → mechanism → evidence/comparison → local impact
  → Recommendations (named to the subject)
  → Endnotes
```

The **"proven model elsewhere" section is near-obligatory** — real ones: `Parking Reform On The Continent`, `Lessons From National Programs`, `Case Studies`.

A real table of contents to model — *Stalled*: Executive Summary · How Parking Impacts Affordable Housing · Efforts To Reduce Parking Mandates · Parking Reform On The Continent · Impacts Of Oʻahu Parking Reform · Recommendations To Further The Impact Of Ordinance 20-41 · Endnotes. (More, including the flagship and short-brief variants, in the reference.)

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

Load the **`appleseed-brand`** skill first: it holds the palette, fonts, chart palette and which text colours pass contrast, and its `reference/web-design-guide.md` and `reference/tokens.css` hold the type scale, spacing and component CSS. Don't restate brand values from memory. On top of that, reports have these non-negotiables:

- **Tokens are `--ha-*`, declared on a page namespace class, never on `:root`** — so the block can be pasted into Squarespace without leaking. New components must live inside the namespace or they get no tokens.
- **`--ha-teal-deep: #52796F` is the workhorse accent** (not `--ha-teal: #84A98C`, which is lighter despite the name).
- **Font stacks must start with the ʻokina face:** `OkinaManrope, 'Manrope', sans-serif` and `OkinaPoppins, 'Poppins', system-ui, -apple-system, Arial, sans-serif`. Neither Manrope nor Poppins ships U+02BB, and Google's latin face claims the codepoint without providing the glyph — omit the Okina face and ~300 ʻokina fall back to the OS UI font.
- **Manrope = headings/display/buttons/stat numbers/eyebrows. Poppins = body, nav, small labels, and all italics.** Manrope has no true italic on Google Fonts — never set `font-style:italic` on it.
- **Body text is never solid charcoal** — use `var(--ha-ink-muted)` (charcoal at 78%). Labels, dates and source notes use `var(--ha-ink-subtle)` (74%); never go fainter, it fails contrast.
- **Verify at 375px before desktop.** The primary breakpoint is `max-width:700px`; 375px also exercises the 800px, 600px, and 1000px queries. Mobile side padding is universally 20px; section padding `56px 20px`. CTA buttons stack full-width.

## Step 6 — Ship it

Both paths start from a self-contained brand HTML file.

**→ Editable Cider project** (live editing on the staff hub, web publish):

**This path needs a second repo.** Cider (the repo was `primer-editor`) is not part of this one; it is `~/primer-editor` on Devin's Mac. Clone it if you don't have it:

```bash
git clone https://github.com/Hawaii-Appleseed/Cider.git ~/primer-editor
```

**Scaffold from the markdown, not from the HTML.** Save the report as markdown — `# Title`, then `Subtitle:` / `Date:` / `Author:` lines, the executive summary as the paragraphs before the first `##`, each `##` section, `###` subheadings, `> ` pull quotes, bullets, and `[^id]` citations with a `[^id]: Source — https://…` line per endnote — and one command lays it out on the house template's pages (cover, inside cover with contents, executive summary, a section page per `##`, sources filled), in a git worktree of Cider, never its main folder:

```bash
python3 -m docsync.new --id <slug> --template appleseed-report --scheme blue --text <report.md> --build
```

`appleseed-brief` for a policy brief; schemes `blue | slate | teal | charcoal`. With the editor app running, `POST localhost:8010/__scaffold {slug, template, scheme, text}` or the local MCP server's `new_report` tool is the same call. Pagination is an estimate: open the project and run `audit()` (the pilot API) before calling it done. The brand HTML from Step 4 is for the Google Doc and `.docx` paths; `docsync/scaffold.py <page.html>` still exists for bringing in a finished web page, and its STAGE TWO wiring is a day's work — not the route for a new report.

Rules in that repo (its `CLAUDE.md` and `report-editor` skill are the authority):

- Work in a worktree (`tools/wt new <name>`); land by pull request (`tools/wt land <name>`). Edits in `~/primer-editor` itself are refused by a hook.
- While an editor tab is open, change the report through the pilot API (`docsync.api.*` / `POST /__pilot`), not by writing `content.md` or `layout.json`.
- **Never start or kill `serve.py` yourself.** The editor app owns it.
- Save is pre-authorized at checkpoints. **Push, and shipping to the staff hub, stay with Devin.**

**→ Google Doc** (funders, coalition markup, anyone who will comment on it): file the rendered brand HTML straight into the shared drive. **Needs `~/internal-tools/appleseed-drive/`** and its Drive credential (`internal-tools` repo); if it isn't on this machine, ship `.docx` instead and say why.

```bash
~/internal-tools/appleseed-drive/.venv/bin/python \
  ~/internal-tools/appleseed-drive/filer.py <report.html> \
  --route tax-budget-research --name "<Title>"
```

Routes and folder ids are in `~/internal-tools/appleseed-drive/routes.yml`. Use `--update <docId>` to revise in place — the file id survives, so the link you shared, its comments and its version history all do too. Prefer this over `.docx` when the point is markup: comments in a Doc beat tracked changes in a file emailed around.

What survives the conversion, measured on a real report: headings, Poppins/Manrope, the `--ha-*` text colours, bold, hyperlinks, bullets, and figures. What does **not** survive: page layout, backgrounds, and anything positional — a Doc is a flowing document, not the designed artifact. If the design *is* the deliverable, ship primer-editor or PDF instead.

**Figures: `filer.py` rasterizes inline `<svg>` to PNG automatically. Do not bypass it.** Drive's importer drops inline SVG — and it does something worse than dropping: it imports the SVG's `<text>` nodes as loose body text. Measured on the RETITC report, all 58 chart labels landed in the prose as free-floating dollar figures with no chart attached, which reads like sourced text and is not. Every figure needs its caption-above/source-below furniture checked after filing, since that furniture arrives whether the figure did or not.

**→ Word .docx** (when a file, not a link, is the requirement): use the `anthropic-skills:docx` skill. Carry over Manrope/Poppins (fall back to Arial), the `--ha-*` palette, ALL CAPS section headings, numbered endnotes, and figure caption-above/source-below.

## Before delivering

- Every claim sourced to `positions.md` or a corpus document — **flag anything you couldn't source rather than shipping it**
- Endnotes numbered continuously, every marker resolves
- Figures numbered in order, each with a source line
- ʻokina is U+02BB throughout (`grep -n "Hawaii[^ʻ]"` and `grep -n "Hawai'i"` both empty)
- "percent" not "%", zero exclamation points
- Rendered HTML checked at **375px** first, then desktop
