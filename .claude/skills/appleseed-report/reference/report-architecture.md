# Report architecture — measured reference

From 42 scraped publications in `writing-bot/publications/` (2021-08 → 2026-08) plus `publications.json` (75 live items).

**Reports ship as designed PDFs**, not web pages. The primer-editor and .docx outputs are adaptations of that archival form, not replacements for it.

Live-site categories: Taxes & Budget (41) · Affordable Housing (25) · Food Equity (18) · Wages & Labor (15) · Transportation Equity (10) · Health (10) · Native Hawaiian Equity (1).

## Length tiers

Range 2,255 – 11,337 words; median ~5,400.

**Brief / primer (2,200–4,200)** — `hawaii-budget-primer-fy202526` (2,255) · `closing-capital-gains-loophole` (2,371) · `hawaii-budget-primer-2026-27` (2,767) · `fair-tax-code-thriving-hawaii` (3,310) · `pedestrian-head-start` (3,762) · `oahu-mobility-needs` (4,021) · `concentrating-wealth` (4,202)

**Standard (5,000–7,500)** — `policy-in-perspective-2025` (5,050) · `freedom-to-walk` (5,292) · `high-cost-low-wages` (5,380) · `food-is-medicine` (6,690) · `rethinking-roads` (6,758) · `beyond-the-ticket` (7,127) · `stalled-parking-mandates` (7,488)

**Flagship (8,500–11,300)** — `keeping-hawaii-housed` (8,786) · `who-pays-climate-disasters` (9,636) · `hawaii-childrens-budget-2022` (10,903) · `policy-perspective-2026` (11,253) · `hawaii-snap` (11,337)

## Cover

```
October 2025
H AWA I‘I   A P P L E S E E D
CENTER FOR LAW & ECONOMIC JUSTICE
STALLED
HOW PARKING MANDATES DRIVE UP HOUSING COSTS
```

Month + Year · logo lockup · **short punchy title in caps** · sentence-length explanatory subtitle.

The title/deck split is consistent: `Stalled` / *How Parking Mandates Drive Up Housing Costs* · `Concentrating Wealth` · `Beyond the Ticket` · `Rethinking Roads` · `Who Pays for Climate Disasters?` · `Keiki Ride Free`. The deck becomes the site `excerpt` field — median **14 words**, range 5–39. Example: *A Fairer Tax Code for a Thriving Hawaiʻi* → "Progressive Revenue Options to Protect and Invest in Our Future."

## Inside front matter

Logo · `www.hiappleseed.org` · author line · org boilerplate · Table of Contents with page numbers · copyright.

**Author line** — 33/42 (79%) carry one, often with title:
> Author: Abbey Seitz, Trinity Gilliam and Arjuna Heim
> Author: Beth Giesting, Hawaiʻi Budget & Policy Center Director Emeritus
> Author: Devin Thomas, Hawaiʻi Budget & Policy Center Policy Analyst
> Authors: Ray Kong, Kenna StormoGipson, Abbey Seitz, Gavin Thornton

**Org boilerplate** — two paragraphs, verbatim identical in 24/42 (the current template):

> Hawaiʻi Appleseed is committed to a more socially and economically just Hawaiʻi, where everyone has genuine opportunities to achieve economic security and fulfill their potential. We change systems to address inequity and foster greater opportunity by conducting data analysis and research to address income inequality, educating policymakers and the public, engaging in collaborative problem solving and coalition building, and advocating for policy and systems change.

> The work of Hawaiʻi Appleseed is about people. The issues we work on—housing, food, wages, mobility, the state budget and taxation, and racial and indigenous equity—are important because they ensure people have access to shelter, sustenance, and the means to survive and thrive individually and collectively. Addressing these issues requires the knowledge and expertise of the people that have first-hand experience and live with the adverse consequences of our flawed systems.

**Copyright** — 42/42 (100%):

> Copyright © 2025 Hawaiʻi Appleseed Center for Law & Economic Justice. All rights reserved. 733 Bishop Street, Suite 1180, Honolulu, HI 96813

**Running footer, every page:** `N • SHORT TITLE` in caps — `2 • CLIMATE DISASTERS`, `10 • BEYOND THE TICKET`, `10 • EQUITY ON THE MENU`, `10 • EMPTY HOMES TAX`.

## Section frequency (n=42, line-anchored)

| Heading | Files | Share |
|---|---|---|
| Endnotes | 39 | 93% |
| Table of Contents | 31 | 74% |
| Executive Summary | 22 | 52% |
| Recommendations | 18 | 43% |
| Introduction | 8 | 19% |
| Conclusion | 4 | 10% |
| Methodology | 4 | 10% |
| Background | 3 | 7% |
| Key Findings | 3 | 7% |
| Summary | 2 | 5% |
| Acknowledgments | 2 | 5% |
| Appendix | 1 | 2% |
| Key Takeaways | 1 | 2% |
| Next Steps | 1 | 2% |

**Only the bookends are generic.** Middle sections are named to the subject — never "Background," "Analysis," or "Findings." The "proven model elsewhere" section is near-obligatory.

Section headings render ALL CAPS, and each section's opening words are set in caps as a lead-in:
> OVER THE PAST SEVERAL DECADES, the United States has experienced a dramatic rise in the frequency…
> AFFORDABLE HOUSING and safe, accessible transportation options are cornerstones to economic opportunity.
> SIGNALIZED INTERSECTIONS are some of the most dangerous places for people walking and biking in Hawaiʻi.¹

## Endnotes

33 reports have a countable block. Density **median 30, range 11–123** — tracks argument density, not length (`pedestrian-head-start`: 51 notes in 3,762 words; `budget-primer-2022-23`: 12 in 9,163).

Highest: `who-pays-climate-disasters` (123) · `policy-perspective-2026` (60) · `hawaii-snap` (59) · `beyond-the-ticket` (56) · `stalled-parking-mandates` (53).

```
121.  Mizuo, Ashley, "As stakeholders navigate building code updates, counties bear
      the burden," Hawaiʻi Public Radio, August 27, 2024. https://www.hawaiipublicradio.org/...

122.  Cohen, Oriya, Sara McTarnaghan and Anne Junod, "Preserving, Protecting, and Building
      Climate-Resilient Affordable Housing," Urban Institute, January 2024. https://www.urban.org/...

123.  "Building for Wildfire Resilience in Hawaiʻi," Community Planning Assistance for
      Wildfire, October 2024. https://static1.squarespace.com/...
```

`N. Author Last, First[, others], "Title," Publishing Org, Month DD, YYYY. URL`. Authorless works start at the quoted title. Short-form repeats: `118. Magin, June 21, 2024` · `119. Magin, 2025`.

Markers are **superscript numerals** on the sentence or figure caption — `…walking and biking in Hawaiʻi.¹`, `Figure 1. HIDOE School Meal Debt¹⁸`, `(see Figure 1).¹⁵`. **No author-date parentheticals, no bibliography, no page-bottom footnotes.**

## Figures

34/42 (81%) contain numbered figures. Caption **above**, source **below**.

Real captions:
- `Figure 1. Average Act 46 Tax Cut By Income Group, Hawaiʻi (2025)³`
- `Figure 1. Community cost of eviction by category, Hawaiʻi (2023)`
- `Figure 1. Federal capital gains tax rates, 1922–2022`
- `Figure 1. Hawaiʻi Housing Costs vs U.S., Averages, 2021`
- `Figure 1. Grounding "Food Is Medicine" in Hawaiian Values`
- `Figure 1. Percent of Hawaiʻi Homes Purchased by Non-Residents, 2017–2020`

Source lines carry methodology caveats where needed:
- `Source: California FAIR Plan`
- `Sources: Council on Revenues, …`
- `Source: Data Axle. The data are incomplete. As a result, the estimates in Figure 3 undercount the true number of residents who left.`

In-text references are prose, never "(Fig. 1)": "Figure 1 shows how rates…" · "…as demonstrated in Figure 1, below." · "(see Figure 1).¹⁵"

Photo credits use `//`: "…life-saving warnings. // NOAA, Public domain, via Wikimedia Commons"

## Testimony — a different document

Median **450 words** (range 161–1,083). Full example, `writing-bot/testimony/food-equity/HB2296_FIN_School_meals.txt`:

```
Hawaii Appleseed Center for Law and Economic Justice

Testimony of the Hawaiʻi Appleseed Center for Law and Economic Justice
Support for HB 2296 – Relating to School Meals
House Committee on Finance
Wednesday, March 4, 2026 at 10:00AM

Dear Chair Todd, Vice Chair Takenouchi, and members of the Committee:

Thank you for the opportunity to submit in support of HB 2296, which would reduce
the minimum revenue requirement that the Department of Education must recover
through school meal charges in department schools.

[3–4 body paragraphs: position → urgency → evidence with bracketed cites → ask]

… Thank you for your consideration.
________________
The Hawaiʻi Appleseed Center for Law and Economic Justice advocates for economic
justice for and with Hawaiʻi's people. We envision a Hawaiʻi that puts its people
first—where everyone can meet their basic needs while living happy, healthy and
creative lives.
________________
[1] Hawaiʻi Foodbank, "The State of Food Insecurity in Hawaiʻi," 2023.
[2] Hawaiʻi State Department of Education, "Free and Reduced Price Meals Program," 2025. https://…
```

Differences from a report: 4-line masthead instead of a cover · no TOC, no executive summary, no named sections — continuous prose · position declared **in the header line itself** and restated in the opening sentence · cites are **bracketed inline `[1]`, not superscript**, with the list under a rule at the end (4 notes, not 30) · a **different, shorter org boilerplate**.

Filenames encode bill + committee: `HB2296_FIN_School_meals.txt` · `SB3245_WAM_SNAP_ESAP.txt` · `HCR144_ACR_Food_Security_Strategy.txt`.

**Two real discrepancies in the archive — don't propagate either:**

1. `positions.md` prescribes a "Mahalo for the opportunity to testify" close, but archived testimony closes "Thank you for your consideration." The guide is aspirational on that line — ask the user which they want.
2. The masthead line above is reproduced verbatim and reads **"Hawaii Appleseed"** without the ʻokina, while the body of the same document uses `Hawaiʻi` correctly. That is an error in the source file, not a convention. Use `Hawaiʻi Appleseed` in anything new.

## Blog — a third form

Median **804 words** (p25 660, p75 1,062, range 409–3,064). Title on line 1, then **continuous prose with no section headings**. Only 17/112 contain figures. No endnotes — attribution rides inline hyperlinks.

Blog posts frequently **point at a report** rather than replacing one: *"For more on the state of Hawaiʻi's housing market and recommendations for improving it, see the Hawaiʻi Budget & Policy Center brief…"*

Handled by the `appleseed-voice` skill.

## Best exemplars

- **`2025-10-01_stalled-parking-mandates-housing-costs.txt`** — cleanest full template
- `2025-12-01_who-pays-climate-disasters.txt` — flagship: 123 endnotes, glossary, case studies
- `2026-03-10_pedestrian-head-start.txt` — short-brief variant (no exec summary, nested bullets)
- `2026-08-13_policy-perspective-2026.txt` — annual review form

**Not exemplars:** `millionaire-report/index.html` (one-off interactive, off-brand, only 4 headings) · `writing-bot/reference/a-fair-tax-system-to-fund-hawaiis-future.txt` (despite the name, these are coalition meeting notes) · `research/*.docx` (two Tax Review Commission meeting summaries, no templates).
