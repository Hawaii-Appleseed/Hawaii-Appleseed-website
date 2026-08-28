---
name: appleseed-testimony
description: Draft or revise legislative testimony submitted under Hawaiʻi Appleseed's name — House/Senate committee testimony on a bill or resolution, in support, in opposition, or with comments. Use whenever writing, formatting, or checking testimony for a hearing. Also triggers on "write testimony on HB####", "testimony for the hearing", "submit on SB####", "check this testimony".
---

# Hawaiʻi Appleseed legislative testimony

Testimony is a **document with fixed furniture**, not an essay. The scaffold is more rigid than the prose, and getting the scaffold wrong is more visible to a committee clerk than any sentence-level choice. Accuracy and faithfulness matter more than fluency.

> Paths are relative to the repo root (`Hawaii-Appleseed-website`) — run from there. Every measured claim below comes from the 37 real testimonies in `writing-bot/testimony/` (13,255 body words, 561 sentences, 2025–2026). The numbers behind them live in `reference/testimony-profile.md`.

## Step 1 — Load the authority (always, before drafting)

Read, in order:

1. **`writing-bot/positions.md`** — HA's curated stances, maintained by policy staff. **Authoritative on positions.** Read it fresh on every use. Never take a position it doesn't cover; `[REVIEW]` means unconfirmed, `[ADD]` means known gap — both mean *ask*.
2. **`reference/testimony-profile.md`** (in this skill) — the measured corpus statistics.
3. **`reference/citations.md`** (in this skill) — 58 citations from the corpus footnotes, each paired with the claim it supports. Check it before writing `CITATION NEEDED`.

**Position integrity — non-negotiable:** every factual claim traces to positions.md or a retrieved corpus document. Never invent statistics, bill numbers, hearing dates, committee names, chair names, room numbers, or dollar figures. **Hearing logistics are especially dangerous** — the header block asserts a committee, date, and time on the record. If you weren't given them, leave bracketed placeholders and say so; do not guess.

### Where positions.md and the corpus diverge

positions.md §153 prescribes a testimony format written before the corpus was measured. Two places it does not match practice:

| | positions.md says | corpus does |
|---|---|---|
| **Closing** | `"Mahalo for the opportunity to testify"` + ask + signature | **20 of 37 have no closing line at all** — the argument simply ends |
| **Opening verb** | "opportunity to *testify*" | "opportunity to *submit testimony*" (13) or *provide testimony* (6) lead; "testify" is the minority form |

**positions.md wins** — write the closing and signature. But say so in your handoff note, so policy staff can decide which is actually house style. Don't silently pick the corpus.

## Step 2 — Retrieve real examples

Don't write from these rules alone. Pull 2–3 testimonies on the nearest subject and read them whole:

```bash
grep -rl "<topic keyword>" writing-bot/testimony/ | grep -v /sample_
```

Corpus layout: `testimony/{food-equity,housing,labor,tax-and-budget,transportation}/`.

**Never use `sample_*` files as models.** Those 13 files are AI-generated templates containing `[INSERT PERSONAL STORY]` placeholders. They are not house writing and their prose is noticeably off.

Good exemplars: `labor/HB2367_2026_Pay_Transparency.txt` (long, subheaded, heavy evidence), `food-equity/HB2296_EDU_School_meals.txt` (short, no subheads), `tax-and-budget/Adjusting_Act_46.txt` (tax mechanics with a rate table).

## Step 3 — Ground the scaffold, then build it

Get the bill's real title, current draft suffix, committee, and hearing time from LegiScan rather than asking the user to supply them:

```bash
python .claude/skills/appleseed-testimony/bill_lookup.py HB1884
```

It prints a ready header block. **It needs `LEGISCAN_API_KEY`** (free tier, 30K queries/month, https://legiscan.com/user/register). Without the key it exits 2 with instructions — in that case leave the header bracketed and tell the user exactly which details are unverified. Never guess a committee, date, or room.

Two things the lookup will not resolve on its own:

- If LegiScan returns only referral abbreviations (`TRN, FIN`), the committee comes back wrapped in a `[COMMITTEE — …]` marker. Expand it from the hearing notice; do not paste the abbreviations onto the letterhead.
- The draft suffix moves during session. Re-run the lookup if the draft was prepared more than a day or two before the hearing.


Roughly 70 percent of testimonies open with this exact four-line block, before the greeting. Reproduce it:

```
Testimony of the Hawaiʻi Appleseed Center for Law and Economic Justice
[Support|Opposition|Comments] for [BILL] – Relating to [Subject]
[House|Senate] Committee on [Committee Name]
[Weekday], [Month] [D], [Year], at [H:MM] [AM|PM]
```

**The position is declared in that title line, never as a standalone prose sentence.** 26 of 37 use `Support for …`. Zero build a separate "Appleseed is in strong support" sentence in the body. Note the title line takes an **en dash** (`–`) before "Relating to" — this is the one place an en dash is correct.

**Greeting** — 31 of 37 name the chair, and **use a colon**:

```
Dear Chair [Name], Vice Chair [Name], and Members of the Committee:
```

**Opening sentence** — 76 percent use this formula. Follow it with one or two sentences saying what the bill does:

```
Thank you for the opportunity to submit testimony in support of [BILL], which would [what it does].
```

Plain `support` outruns `strong support` about 2:1. Reserve "strong" for the org's flagship priorities in positions.md.

## Step 4 — Write the arc

1. **Opening** (1 paragraph) — the formula above plus what the bill does. No statistic here.
2. **Subject-defining declarative** — the second paragraph flatly establishes what the thing *is* and why it matters: "SNAP is a critical lifeline for more than…", "Medical debt is a persistent cause of…", "Real Estate Investment Trusts (REITs) are entities that…". This is the corpus's most consistent body move. **Do not open paragraph 2 with the org's mission** — only 11 percent do that.
3. **Evidence** (2–4 paragraphs) — named authorities, specific figures, footnoted. See density targets below.
4. **Counter the predictable objection** — name the *idea*, grant its logic, dismantle it with evidence. Never personify an opponent.
5. **The ask** — final one or two paragraphs, in 41 percent of docs. Soft: "We respectfully urge the Committee to pass [BILL]."
6. **Close** — `Mahalo for the opportunity to testify.` then the signature line `Hawaiʻi Appleseed Center for Law and Economic Justice`. (Per positions.md — see the divergence note above.)

### Shape targets

| Measure | Target |
|---|---|
| Body words | **250–430** (median 334; p10 214, p90 510) |
| Paragraphs | **5–7** |
| Sentences per paragraph | **1–3** (median 2; never 5+) |
| Words per sentence | median **23**, mean 23.6, stdev 10.9 — vary hard |
| Short punches (<12 words) | ~11% of sentences |
| Subheads | **none for a short piece** — only 30% of docs use any. Over ~450 words, 3–5, Title Case, median 4 words: `A Proven Model`, `Why Transparency Matters` |
| Bullets | 24% of docs — for "what the bill does" or an impact list, never for argument |

## The register: predictive-analytic, not hortatory

This is the single most distinctive measurement in the corpus, and the easiest thing to get wrong.

| Modal | per 1,000 words |
|---|---|
| **would** | **7.5** |
| will | 2.3 |
| can | 2.9 |
| should | 0.5 |
| **must** | **0.4** |

The house move is *"this bill **would** reduce…"* — analysis of consequences, not exhortation. `must` and `should` are almost absent. A draft that stacks up "the Legislature must act" reads as a different organization. Prescribe through the mechanism, not the imperative.

Hedge **magnitudes** ("approximately 87 percent"), never the judgment.

## Mechanical rules (checkable — verify before delivering)

| Rule | Detail |
|---|---|
| **ʻokina** | `Hawaiʻi`, `Oʻahu`, `Kauaʻi`, `ʻohana`, `kūpuna` — always **U+02BB ʻ**, never a curly quote. Corpus: 175 correct, 1 bare, 0 curly. **`Hawaiian` takes no ʻokina.** |
| **Em dash** | **Unspaced**: `employers—regardless of size—to disclose`. |
| **En dash** | Only in the header title (`HB2367 HD1 – Relating To…`) and numeric ranges. **16 corpus instances of `word–word` are Google Docs autocorrect defects, not style** — never copy them. |
| **percent** | **Spell it out in prose.** The corpus is split (22 spelled / 32 signs) and inconsistent *within single documents* — `HB2367` uses both. Spelling it out is the deliberate choice, matching `appleseed-voice`. |
| **Person** | Org is **third person** ("Hawaiʻi Appleseed advocates…") when acting; "we/our" for shared civic claims. **First-person singular is effectively banned** — 2 uses of "I" in 13,255 words, both rhetorical. |
| **Contractions** | 6.6 per 1,000 words. Fine in a rhetorical sentence; not inside policy mechanics. |
| **Bill numbers** | Corpus uses both `HB2367` and `HB 2367` — pick one per document and hold it. Always carry the draft suffix (`HD1`, `SD2`, `CD1`) once it exists. |
| **Attribution** | Name real authorities inline (U.S. Bureau of Labor Statistics, ITEP, DBEDT, Hawaiʻi Foodbank, ALICE), then a numbered footnote `[1]` with a full citation and URL after a `________` rule. **Check `reference/citations.md` first** — 58 sources HA has already published are there, indexed by the claim each supports. |
| **Hawaiian vocabulary** | **Sparse and load-bearing** — 9 words in the entire 13,255-word corpus. `mahalo` belongs in the closing. Do not decorate. |

### Evidence density

27 numerals per 1,000 words · 1.3 dollar figures per testimony · a bill reference in 84 percent of docs. Every statistic footnoted.

**Sourcing order:** (1) `reference/citations.md` — a source HA has already stood behind; (2) a citation carried by a retrieved corpus document; (3) a source the user supplies. If none of those covers the figure, write `CITATION NEEDED` and say so in the handoff. positions.md carries many figures *without* their sources — reusing a number from it does not give you a citation. Never attach the nearest-looking source: a citation that does not support the number is worse than a visible gap. Testimony is measurably more numeric than the blog voice — but the numbers arrive *after* a claim, never as the opening.

## Anti-patterns — verified zeros across the corpus

1. **Exclamation points (0) and rhetorical questions (1).** Never.
2. **`some argue` / `opponents` / `critics` — all zero.** Name the idea, not a personified adversary.
3. **Consultant/LLM register — all zero:** `delve`, `tapestry`, `stakeholder`, `impactful`, `underscore`, `it is important to note`, `in conclusion`, `first and foremost`, `at the end of the day`.
4. **Near-zero connectives — treat as ceilings, not bans:** `furthermore` 5, `crucial` 5, `vital` 5, `however` 4, `additionally` 3, `moreover` 1. More than one or two per document is a tell.
5. **Partisan labels, attacks on individuals, attributed motive.** Criticism attaches to a body ("the Senate did not assign conferees"), and legislators are named only to credit them.
6. **Deficit labels for people** — "the poor," "the homeless," "illegal immigrants." Use "working families," "low-income households," "houseless residents," "undocumented immigrants."
7. A statistic as the opening sentence; the ask anywhere before the final two paragraphs; paragraphs of 5+ sentences.

## Before delivering

**Scope every orthography check to the prose body.** Two zones are exempt and must not be "corrected":

- **Footnote citations** — a source title is quoted verbatim. The real BLS title is `"Women's Earnings in Hawaii — 2023"`: bare `Hawaii`, spaced em dash. Fixing it corrupts the citation.
- **The running letterhead** — `Hawaii Appleseed Center for Law and Economic Justice` uses a bare `Hawaii` in 21 of 37 documents. It is a page-header template artifact, not prose.

Strip both, and the corpus body is **100 percent clean** on ʻokina. So:

```bash
body() { sed '/^_\{6,\}/,$d' "$1" | grep -v '^\[[0-9]\]' | grep -v 'http' \
         | grep -v 'Hawaii Appleseed Center'; }

body draft.md | grep -nE "Hawaii([^ʻa]|$)"   # bare Hawaii — "Hawaiian" correctly excluded
body draft.md | grep -n "Hawai’i\|Hawai‘i"   # curly-quote fake ʻokina (U+2019 / U+2018)
body draft.md | grep -n " — "                 # spaced em dash — house style is unspaced
body draft.md | grep -nE "[A-Za-z]–[A-Za-z]"  # en dash used as a dash — should be em dash
body draft.md | grep -n "%"                   # should be "percent" in prose
grep -n "!" draft.md                          # should be empty
grep -cE "\b(must|should)\b" draft.md        # >2 means the register drifted hortatory
grep -nE "\bI\b|\bmy\b" draft.md            # first-person singular
```

Then read once for: the header block's four lines present and correct; the position in the title line; paragraph 2 defining the subject; paragraph length ≤3 sentences; sentence variety; every statistic footnoted; no legislator blamed by name.

**Flag to the user, don't silently resolve:** any hearing detail you were not given (committee, date, time, room, chair names), any claim you couldn't source, any position not in positions.md, and the positions.md/corpus closing divergence if it came up.

## Shipping — letterhead, .docx, Google Doc

Write the draft as plain text in the shape above (header block, `Dear Chair…`, body paragraphs one per line, closing, signature, `________________`, then `[n]` footnotes), then render it. Do not hand-build the letterhead.

```bash
S=.claude/skills/appleseed-testimony
.venv/bin/python $S/render_testimony.py draft.txt -o out/HB1884
```

That emits **`HB1884.docx`** and **`HB1884.html`** from one source, and adds the furniture automatically:

- the green horizontal lockup (`assets/appleseed-horizontal-green.png`) in the **first-page header** — the corpus's `\\LEJ-SERVER\…\Logos\GREEN\Horizontal.png` is a dead Windows path, this is the same asset
- a **running header** on later pages: org name + `Page X of Y` as real Word fields
- Arial 11, one-inch margins, 1.15 spacing
- the standard org boilerplate paragraph and the footnote block below the rule

**Verify before sending** — the `.docx` is what gets submitted:

```bash
/Applications/LibreOffice.app/Contents/MacOS/soffice --headless --convert-to pdf out/HB1884.docx --outdir out
sips -s format png --resampleWidth 1000 out/HB1884.pdf --out out/page1.png   # then look at it
```

### Into a Google Doc

Direct Drive API writes are blocked by Workspace policy. The working route is the clipboard one documented in `~/.claude/drive-routes.yml` (`backend: chrome`):

```bash
$S/to_gdoc.sh out/HB1884.html
```

That puts the rendered HTML on the clipboard as HTML flavor and prints the remaining steps: in Chrome signed in as devin@hibudget.org, open the target folder, **New ▸ Google Docs ▸ Blank**, `Cmd+V`, rename.

Three things to know:

- **The `testimony` route in `drive-routes.yml` has no folder id yet.** Ask the user for the Legislative ▸ Testimony folder URL rather than filing the Doc somewhere plausible.
- **A base64 `data:` logo does not reliably survive the paste.** Check the pasted Doc; if the logo is missing, Insert ▸ Image ▸ Upload with `assets/appleseed-horizontal-green.png`.
- **Log the new Doc to the "Google Docs in progress" memory list** as soon as it exists, and never remove an entry unless the user says so in chat.

Do not submit to the Capitol testimony portal. Shipping stops at a document the user reviews.
