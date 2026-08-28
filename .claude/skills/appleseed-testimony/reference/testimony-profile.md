# Measured style profile — HA testimony corpus

Derived from the **37 real testimonies** in `writing-bot/testimony/` — 13,255 body words, 561 sentences, hearings 2025–2026. Measured 2026-08-27.

**Excluded:** the 13 `sample_*` files. They are AI-generated templates containing `[INSERT PERSONAL STORY]` placeholders, not house writing. Never profile or model on them.

"Body" = text between the `Dear Chair…` greeting and the closing line, with letterhead, committee/date furniture, footnote blocks, and the org boilerplate paragraph stripped.

Regenerate with `reference/profile_testimony.py` if the corpus grows substantially.

## Length and shape

| Measure | median | p10 | p25 | p75 | p90 | range |
|---|---|---|---|---|---|---|
| Body words | **334** | 214 | 259 | 425 | 510 | 145–791 |
| Paragraphs | **6** | 4 | 5 | 7 | 15 | 3–20 |
| Sentences per paragraph | **2** | 1 | 1 | 3 | 3 | 1–5 |
| Words per sentence | **23** | 11 | 17 | 29 | 37 | 2–85 |

Sentence length mean **23.6**, stdev 10.9. Under 12 words: **11%**. Over 35 words: **12%**.

Subheads: median 0 — **only 30% of docs use any**. Where used: median 4 words, 43% Title Case, 21% contain a finite verb. Bullets/numbered lists in 24% of docs.

## The header scaffold

| Element | share of docs |
|---|---|
| `Testimony of the Hawaiʻi Appleseed Center for Law and Economic Justice` | 70% |
| `[Support\|Opposition\|Comments] for [BILL] – Relating to [Subject]` | 68% |
| Committee name line | 70% |
| Hearing date + time line | 73% |

Position declared in the title line: **26 docs** (`Support for …` 25, `In Support of …` 1). Declared as a standalone prose sentence: **0**.

## Greeting

31 of 37 name the chair. `Dear Chair [Name], Vice Chair [Name], and Members of the Committee` — **colon 59%**, comma 35%. (One typo in corpus: `Committeee`.)

## Opening sentence — 76% use the formula

| Continuation of "Thank you for the opportunity to…" | n |
|---|---|
| submit testimony in support of | 13 |
| provide testimony in support of | 6 |
| testify on behalf of | 4 |
| submit testimony in strong support of | 3 |
| testify in strong support of | 2 |
| submit in support of | 2 |
| present testimony in strong support of | 1 |

Position phrase: `in support of` 15 · `in strong support of` 7 — roughly **2:1 plain over strong**.

## Second paragraph — subject-defining declarative

The most consistent body move. Observed openers: *"SNAP is a critical lifeline for more…"* · *"Medical debt is a persistent cause of…"* · *"Real Estate Investment Trusts (REITs) are entities…"* · *"Public schools are one of the most…"*

Org-mission paragraph in the first three paragraphs: **only 11%** (4 of 37).

## Closing

| | n |
|---|---|
| **No closing line at all** | **20** |
| `Thank you for the opportunity to provide testimony in support…` | 6 |
| `Mahalo for the opportunity to testify.` | 3 |
| `Mahalo for your time and consideration.` | 3 |
| `Mahalo for your consideration.` | 2 |
| other `Mahalo…` | 2 |

⚠️ This contradicts `positions.md` §153, which requires a Mahalo close + signature. positions.md is authoritative; flag the divergence rather than resolving it silently.

## The ask

| | share of docs |
|---|---|
| "urge" (any) | 27% |
| "respectfully urge" | 19% |
| "support this bill/measure" | 16% |
| "pass this / HB / SB" | 16% |
| "we ask" / "we request" | **0%** |
| "please" | 5% |
| Ask located in final 2 paragraphs | 41% |

## Person (per 1,000 words)

| Token | count | /1k | docs |
|---|---|---|---|
| our | 63 | 4.8 | 73% |
| we | 31 | 2.3 | 54% |
| "Hawaiʻi Appleseed" (3rd person) | 26 | 2.0 | 51% |
| us | 4 | 0.3 | 11% |
| **I** | **2** | **0.2** | 5% |
| **my** | **2** | **0.2** | 3% |

Both "I" uses are rhetorical, not autobiographical. **This corpus carries no personal-voice signal** — it is institutional voice by construction.

## Modals — the predictive-analytic register

| Modal | /1k |
|---|---|
| **would** | **7.5** |
| will | 2.3 |
| can | 2.9 |
| should | 0.5 |
| **must** | **0.4** |
| may | 0.5 · could 0.3 · might 0.2 | |

## Punctuation and mechanics

| Mark | count |
|---|---|
| exclamation points | **0** |
| rhetorical questions | 1 |
| em dash — unspaced | 42 |
| em dash — spaced | 2 |
| **en dash used as a dash (`word–word`)** | **16** ← Google Docs autocorrect defect |
| en dash in numeric ranges | 1 |
| semicolons | 9 |
| colons mid-prose | 38 |
| parentheticals | 45 |
| direct quotations | 18 |
| "percent" spelled out | 22 |
| `%` sign | 32 |
| contractions | 87 (**6.6/1k**) |

**`percent` vs `%` is inconsistent within single documents** — `HB2367` uses `percent` 12× and `%` 9×; `HB2360` uses 3× and 12×. The corpus does not resolve this; the skill picks spelled-out to match `appleseed-voice`.

ʻokina: `Hawaiʻi` correct **175** · bare `Hawaii` 1 · curly-quote **0**.

Hawaiian vocabulary: **9 words total in 13,255** — `keiki` 5, `mahalo` 2, `kūpuna` 1, `ʻohana` 1. Far sparser than the blog corpus.

## Evidence density

| | |
|---|---|
| numerals | 356 (**27 per 1,000 words**) |
| dollar figures | 49 (1.3 per testimony) |
| bill references | 88 (in 84% of docs) |
| Act citations | 12 |
| statute citations | 2 |

## Verified zeros

`some argue/say/claim` · `opponents` · `critics` · `it is important to note` · `in conclusion` · `first and foremost` · `at the end of the day` · `delve` · `tapestry` · `stakeholder` · `impactful` · `underscore` · `we ask` · `we request`

**Near-zero — ceilings, not bans:** `furthermore` 5 · `crucial` 5 · `vital` 5 · `however` 4 · `additionally` 3 · `navigate` 3 · `moreover` 1 · `robust` 1 · `leverage` 1.

## Testimony vs blog voice — what changes

| | Blog | Testimony |
|---|---|---|
| Length | 600–1,100 words | **250–430** |
| Subheads | median 3, 81% of posts | **median 0, 30% of docs** |
| Numerals | — | **27/1k, much denser** |
| Hawaiian words | routine (`keiki`, `kūpuna`) | **9 total in 13k words** |
| First person | civic "we/our" | civic "we/our" + **third-person org** |
| Dominant modal | mixed | **`would` 7.5/1k** — analytic, not hortatory |
| Structure | flexible arc | **fixed header block + greeting formula** |
| Close | 85% no CTA | ask in final 2 paragraphs, 41% |
