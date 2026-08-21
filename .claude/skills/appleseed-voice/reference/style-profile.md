# Measured style profile — HA blog corpus

Derived from all 112 posts in `writing-bot/blog-posts/` (101,513 words, 2021–2026). Use for calibration when a judgment call comes up. Regenerate if the corpus grows substantially.

## Length and shape

| Measure | Value |
|---|---|
| Words per post | mean 906, median 830, range 409–3,064; modal band **600–1,100** |
| Sentence length | mean **21.4** words, median 21 |
| Sentence percentiles | p10=8, p25=14, p50=21, p75=28, p90=35, p95=40, p99=50 |
| Short sentences (≤10 words) | **14.7%** — the punch rhythm |
| Long sentences (≥40 words) | 5.5% |
| Body paragraphs per post | median 16, mean 18, ≈50 words each |
| Paragraph length | mean **2.26** sentences. 1 sent 30.4% · 2 sent 33.9% · 3 sent 22.6% · 4 sent 9.4% · 5+ **3.7%** |
| Subheads per post | median 3; **19% of posts have none** (the short ones) |
| Posts using bullets | 25% — bill roundups, "what the proposal does," options menus |

## Openings — distribution across all 112

| Pattern | n | % |
|---|---|---|
| Legislative / news hook | 31 | 28% |
| Values or thesis premise | 29 | 26% |
| Problem-state declaration | 17 | 15% |
| Background / explainer / precedent | 11 | 10% |
| Org agenda or "about us" | 6 | 5% |
| Direct address / conventional-wisdom reframe | 5 | 4% |
| **Statistic lead** | **4** | **4%** |
| Scene / narrative / named person | 4 | 4% |
| "Read our brief" boilerplate (2022 only, extinct) | 4 | 4% |

## Headings

- **Subheads** (n=384): 71% Title Case · mean 5.4 words · only **7% contain a finite verb** · 18% contain a colon · 14% start with a gerund · 8% start with How/Why/What/Who/When · 5% end with `?` · 2% imperative.
- **Titles** (n=105): **93% sentence case** · mean 11 words (range 6–17) · 24% contain a colon · 7% semicolon · 7% em/en dash · 3% end in `?` · exactly 1 ends in a period.

## Pronouns (per 1,000 words)

| Token | count | /1k | posts |
|---|---|---|---|
| our | 374 | 3.68 | 86/112 |
| we | 358 | 3.53 | 73/112 |
| their | 366 | 3.61 | 91/112 |
| they | 269 | 2.65 | 88/112 |
| us | 51 | 0.50 | 32/112 |
| I | 69 | 0.68 | 26/112 |
| you | 54 | 0.53 | 19/112 |
| my | 9 | 0.09 | 4/112 |

"We/our" is predominantly the **civic we** (Hawaiʻi, the public), not the organizational we. The org names itself in third person ("Hawaiʻi Appleseed," 88 mentions / 39 posts) when reporting its own actions, and switches to "we" for shared civic claims — often within the same post.

## Punctuation

| Mark | count | /1k | posts |
|---|---|---|---|
| parentheses | 558 | 5.50 | 105/112 |
| em dash — | 533 | 5.25 | 96/112 |
| colon | 421 | 4.15 | 88/112 |
| semicolon | 95 | 0.94 | 41/112 |
| en dash – | 74 | 0.73 | 39/112 |
| question mark | 59 | 0.58 | 28/112 |
| **exclamation** | **0** | **0.00** | **0/112** |

Em dashes unspaced 511 vs spaced 2. En dashes for numeric ranges only.

## Numbers

- **"percent" 431 vs "%" 19.**
- `$X million` 291 · `$X billion` 75 · `$X,XXX` 199 · `$X.X trillion` 6.
- Hedged magnitudes (`nearly/roughly/about/more than/over` + number): 205 across 75/112 posts.
- Explicit "according to": only 33 uses in 23 posts — attribution normally rides a hyperlink on the source name.
- Footnote markers `[n]` in only 5 posts; `Figure N.` captions in 20 posts (65 instances).
- Small numbers lean to words below ten in prose, numerals whenever the number is data.

## Orthography

- `Hawaiʻi` **1,023** vs bare `Hawaii` **11**. 110/112 posts use the ʻokina.
- **Must be U+02BB (ʻ).** 1,130 correct; **33 wrong U+2018 (') in 2025 files**; 3 ASCII apostrophes.
- `Hawaiʻi's` possessive: 280. `Hawaiian` correctly takes **no** ʻokina (45 uses, 0 errors).
- `Oʻahu` 26 vs `Oahu` 2 · `Kauaʻi` 24 vs `Kauai` 2 · `Maui` 32 · `Hawaiʻi Island` 4 · `Native Hawaiian` 18.

## Hawaiian vocabulary (count / posts)

`keiki` 57/29 · `kūpuna` 49/16 · `ʻohana` 21/7 · `kauhale` 14/6 · `pilina` 7/2 · `aloha` 5/4 · `ʻāina` 1 · `kuleana` 1 · `mālama` 1 · `ʻōlelo noʻeau` 1.

**Absent:** `kamaʻāina` 0 · `mahalo` 0 in blogs (belongs in testimony closings) · `talk story` 1, in scare quotes.

Small, load-bearing, unglossed. `keiki` and `kūpuna` do most of the work.

## Signature framings (count / posts)

`invest`/`investment` 248/80 · `working families` 109/42 · `the Legislature` 110/54 · `low-income` 102/51 · `must`/`should` 160/73 · `equitable`/`equity` 82/43 · `crisis` 62/34 · `cost of living` 45/32 · `the wealthiest` 32/19 · `the wealthy` 29/20 · `loophole` 28/18 · `thrive` 23/20 · `deserve` 22/19 · `safety net` 22/16 · `our communities` 20/15 · `make ends meet` 17/11 · `top 1 percent` 17/12 · `our keiki` 14/11 · `economic security` 13/12 · `dignity` 10/6 · `economic justice` 7/6 · `fair share` 6/5.

Collocations by doc spread: `earned income tax credit` (19 posts) · `universal free school meals` (12) · `the top 1 percent` (12) · `high cost of living` (10–12) · `taxing capital gains at the same rate as ordinary income` (6–11) · `to make ends meet` (10) · `safe routes to school` (7).

## People-first language

`low-income households/families/residents` 47 (30 posts) vs `the poor` **2**, `poor people` **0**. `struggling` 57 (39 posts). `houseless` 45 vs `homeless` 60 — actively transitioning toward `houseless`/`unsheltered`. `undocumented` 19; `illegal immigrant`/`alien` **0**.

## Verified zeros across 101,513 words

**Attack register:** greedy · corrupt · evil · outrageous · shameful · disgusting · scandal · crazy · "attack on" · "fight back" · radical — all **0**.

**Partisan:** Democrat · partisan · GOP · MAGA · liberal · left-wing · right-wing · socialist · woke — all **0**. `Republican` 5 (procedural only). `Trump` 20/9 posts, always as a policy actor.

**Consultant jargon:** synergy · unpack · deep dive · best-in-class · "at the end of the day" — **0**. utilize 1 · stakeholder 1 · holistic 2 · paradigm 3 · robust 5 · leverage 6 (mostly literal).

**LLM tells:** delve · tapestry · "landscape of" · "in a world" · literally · arguably · frankly · "simply put" · hence — all **0**. obviously 1 · basically 1 · thus 3 · moreover 5 · furthermore 5.

**Casual:** guys 0 · folks 15/11 posts. `very` 40 · `really` 10.

## Stance mechanics

- `opponents`/`critics`/`detractors`: **1** occurrence total. `some argue/say/claim`: **0**.
- Modals directed at institutions: 160 instances / 73 posts.
- Legislators named: `Rep.`/`Representative` 3 · `Sen.`/`Senator` 4 · Governor+name 13 · committees 11. Bills named **275 times / 52 posts** (`Act ##` 69).
- Uncertainty: `would` 420/87 posts · `could` 149 · `may/might` 64 · `likely` 59 · `estimated/projected/expected` 71. Explicit epistemic caveats in 14 posts.
- **CTAs: only 17/112 posts (15%) have one.** Median relative position **0.95** — final paragraph. 70% of CTA instances fall in the last 20% of the post.

## Voice drift — weight 2025–2026

Per 1,000 words:

| Year | posts | we/our/us | contractions | em dash | `?` | percent-stats | must/should |
|---|---|---|---|---|---|---|---|
| 2021 | 3 | 5.83 | 0.00 | 3.89 | 0.00 | 6.22 | 2.72 |
| 2022 | 26 | 6.31 | 1.76 | 2.95 | 1.00 | 4.75 | 1.72 |
| 2023 | 5 | 10.79 | 1.47 | 6.54 | 0.49 | 6.70 | 1.14 |
| 2024 | 18 | 4.17 | 0.64 | 3.85 | 0.13 | 5.45 | 1.35 |
| 2025 | 42 | 7.64 | 1.63 | 5.81 | 0.44 | 3.72 | 1.66 |
| **2026** | **18** | **12.16** | **3.49** | **8.39** | **0.79** | **2.36** | **1.41** |

Current voice is warmer, more conversational, more collectively-voiced, and leans on argument and moral framing more than statistical density. Mean sentence length fell 26.3 (2023) → 19.7 (2026). Direct address and conventional-wisdom reframes are 2025–2026 devices with no earlier precedent.

Two conventions flipped recently:
- **`Legislature` is now capitalized** (2022: 1 cap / 42 lower; 2026: 11 cap / 4 lower).
- The 2022-era "For a more detailed look, read the Hawaiʻi Budget & Policy Center brief…" opener is extinct after 2022.

Constant across all six years: ʻokina, "percent," zero exclamation points, short paragraphs, sentence-case titles / Title Case subheads.

## Corpus hygiene

About 8 files are unpublished Google Doc exports carrying `Title:`/`Author:` lines, `________________` rules, `[a]` comments, or `EXTRA NOTES DO NOT INCLUDE`. Their prose is house voice; their structure is not. Known: `2025/kupuna-at-risk-*` (title literally `Draft`), `2025/can-hawaii-afford-to-cut-the-grocery-tax` (`Current draft`), `2025/proposal-to-raise-transit-fares-will-hurt-oahu-riders` (`1/26/25 Updates`), `2026/taking-policy-local-*`, `2026/one-step-forward-a-few-meals-short` (`DRAFT`).
