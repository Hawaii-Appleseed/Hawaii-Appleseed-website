---
name: appleseed-voice
description: Draft or revise writing in Hawaiʻi Appleseed's house voice — blog posts, testimony, op-eds, newsletter copy, web page prose, report narrative. Use whenever writing something that will go out under Hawaiʻi Appleseed's name, or when asked to check/revise existing copy for house voice. Also triggers on "in HA voice", "Appleseed style", "make this sound like us".
---

# Hawaiʻi Appleseed house voice

Writing that goes out under HA's name. Accuracy and faithfulness matter more than fluency.

> **Paths in this skill are relative to the repo root** (`Hawaii-Appleseed-website`) — run from there. `positions.md` and the full corpus live in this same repo under `writing-bot/`, so they resolve on any clone, no setup required.

## Step 1 — Load the authority (always, before drafting)

Read these two, in this order:

1. **`writing-bot/positions.md`** — HA's curated stances + voice guide. **This file is authoritative.** It is maintained by policy staff and read fresh on every use. Where it conflicts with anything below or with retrieved examples, positions.md wins.
2. **`reference/style-profile.md`** (in this skill) — measured corpus statistics. Use for calibration when a judgment call comes up.

**Position integrity — non-negotiable:**
- Ground every factual claim in positions.md or in a retrieved corpus document. **Never invent statistics, bill numbers, hearing dates, committee names, or dollar figures.**
- If the task needs a position that positions.md doesn't cover — or contradicts one it does — **stop and flag it.** Ask rather than guess. Inventing a stance is worse than an incomplete draft.
- Items marked `[REVIEW]` in positions.md are unconfirmed extractions; items marked `[ADD]` are known gaps. Treat both as "check with the user."

## Step 2 — Retrieve real examples

Don't write from these rules alone. Pull 2–4 actual posts on the nearest topic and read them:

```bash
grep -rl "<topic keyword>" writing-bot/blog-posts/2026/ writing-bot/blog-posts/2025/
```

Corpus layout: `blog-posts/<year>/`, `testimony/<topic>/`, `publications/`, `reference/`.

**Weight 2025–2026 heavily.** The voice measurably shifted: 2026 uses 3× the first-person plural of 2024, 5× the contractions, more em dashes, and about half the raw percentage density. Older posts are on-message but sound stiffer than current house voice.

**Skip the drafts as structural models.** About 8 corpus files are unpublished Google Doc exports still carrying `Title:`/`Author:` lines, `________________` rules, `[a]` comments, or `EXTRA NOTES DO NOT INCLUDE`. Their prose is house voice; their structure is not. If a file opens with `Draft`, `Current draft`, or a date-stamped revision note, use it for diction only.

## Step 3 — Write to the arc

**Blog post** (per positions.md): values-grounded opening → problem → why the system fails the people most affected → data and named harms → proven model elsewhere → the bill or action in front of us.

**Testimony** (per positions.md): greeting → position → urgent context with named populations → evidence → counter the predictable opposition → restate the ask → mahalo close. Signature: "Hawaiʻi Appleseed Center for Law and Economic Justice".

### Openings
Lead with a **claim, not a number.** Only 4 percent of posts open on a statistic; evidence arrives in paragraph 2–4 to support a claim already made. The dominant patterns, in order of real frequency: legislative/news hook (28%), values or thesis premise (26%), flat problem-state declaration (15%), background/explainer (10%). Direct address ("You've probably heard…") and conventional-wisdom reframes ("We tend to think of building codes as settled, technical matters…") are current 2025–2026 devices.

Opening paragraph: 1–3 sentences, usually 2, ending on the thesis or the tension the piece resolves.

### Shape
- **600–1,100 words** is the modal post (mean 906, median 830).
- **Paragraphs: 1–3 sentences.** Over 64 percent of all body paragraphs are one or two sentences. A 6-sentence block reads wrong.
- **Sentences: mean 21 words** — but vary hard. About 15 percent are ≤10 words. The rhythm is a long analytic sentence followed by a short declarative punch: "The evidence is overwhelming." / "This is not a collection of separate problems. It is one broken system."
- **Subheads:** median 3 per post; posts under ~650 words often have none. **Title Case, noun phrases, ~5 words, no finite verb** (only 7 percent contain one). Real ones: `A Pattern Worth Naming`, `Three Major Sources of Budget Strain`, `The Broken Promise of Inclusionary Zoning`, `What's Happening at Home`.
- **Titles:** the reverse — **sentence case** (93%), long and explanatory, ~11 words, often `[Evocative phrase]: [How/Why + concrete claim]`.

### Closings
2–4 sentences that restate the stake in moral terms and point forward. Resolute, not triumphant. The two-beat short close is a signature: "Pedestrians across Hawaiʻi deserve better. We will keep pushing until they get it."

**Most posts have no call to action at all** — 85 percent don't. Default to ending on the argument. When there is an ask, it goes in the final paragraph and stays concrete and low-pressure.

## Mechanical rules (checkable — verify before delivering)

| Rule | Detail |
|---|---|
| **ʻokina** | `Hawaiʻi` — 1,023 uses vs 11 bare `Hawaii`. Must be **U+02BB ʻ**, not U+2018 `'` (33 wrong ones snuck into 2025 files). Also `Oʻahu`, `Kauaʻi`, `ʻohana`, `kūpuna`, `ʻāina`. **`Hawaiian` takes no ʻokina.** |
| **percent** | Spell it out — 431 uses vs 19 `%`. |
| **Exclamation points** | **Zero** in 101,513 words. Never. |
| **Em dashes** | Unspaced: `responsibility—the`. 511 unspaced vs 2 spaced. En dash for numeric ranges (`2019–2022`, `$1.2–1.4 billion`). |
| **Person** | "We/our" is the **civic we** (Hawaiʻi, the public) — "our keiki," "our islands." First-person singular is effectively banned outside explicitly personal pieces. The org refers to itself in third person ("Hawaiʻi Appleseed") when reporting its own actions. |
| **Contractions** | Sparingly, and rising: fine in rhetorical or direct-address sentences, almost never inside a data or policy-mechanics paragraph. |
| **Attribution** | Carried by a **hyperlink on the source's name**, not an "according to" clause (only 33 in the corpus). Name real authorities inline: ITEP, U.S. Census Bureau, CBPP, DBEDT, Hawaiʻi Foodbank, ALICE. |
| **Hedging** | Hedge *magnitudes* ("roughly $25.2 million," "nearly 19,000 residents") — **never hedge the judgment.** |
| **House spellings** | `nonprofit`, `healthcare`, `policymaker`, `the Legislature` (now capitalized). `keiki`/`kūpuna` unitalicized. Oxford comma genuinely optional — corpus is split 112/111. |

**Hawaiian vocabulary is small, load-bearing, and unglossed.** `keiki` and `kūpuna` do most of the work; `ʻohana`, `kauhale`, `pilina` appear where they carry real meaning. Note what is *absent*: `kamaʻāina` (0 uses), `mahalo` (0 in blogs — it belongs in testimony closings). Don't decorate with Hawaiian words.

## Stance

- **Prescribe to institutions, not people.** "The Legislature must," "Congress should," "the state can." Bills are named 275 times; legislators almost never are — and when named, it's to *credit* them. Criticism attaches to a body: "the Senate did not assign conferees."
- **Never personify opponents.** "Opponents"/"critics" appears once in the whole corpus; "some argue" appears zero times. Name the *idea*, grant its logic, then dismantle it with evidence. The signature move: "It's not about X. It's about Y." — "A fairer tax code isn't about punishing success. It's about making sure all of us can thrive—not just a wealthy few."
- **State uncertainty; volunteer data limits.** "These results paint an incomplete picture of poverty here in the state."
- **Report losses honestly**, then reframe toward the next session.
- **Urgent but measured. Advocates, not screamers.** Confident in the position, generous to good-faith opposition, unsparing about consequences.

## Anti-patterns — these read as "not us"

1. `Hawaii` without the ʻokina, or `Hawaiʻian`, `Oahu`, `Kauai`, or a curly-quote fake ʻokina
2. Any exclamation point
3. `%` instead of `percent`
4. **Partisan labeling** — "Democrats," "GOP," "partisan," "radical," "socialist" are all at zero. `Republican` appears 5 times, always procedurally
5. **Attacking individuals or attributing motive** — "greedy," "corrupt," "shameful," "outrageous" all at zero
6. Opening on a shock statistic
7. A CTA in the first half — or any CTA in an analysis post
8. Paragraphs of 5+ sentences
9. First-person singular
10. **Consultant/LLM register** — "delve," "tapestry," "unpack," "deep dive," "landscape of," "at the end of the day," "stakeholders," "synergy," "robust holistic" — all at or near zero in 101k words
11. **Deficit labels for people** — "the poor," "the homeless," "illegal immigrants," "handouts," "welfare." Use "low-income families," "houseless residents," "undocumented immigrants," "families struggling to make ends meet." The corpus is actively shifting `homeless` → `houseless`
12. Title Case titles or sentence-case subheads — it's the reverse
13. Subheads written as full sentences
14. Uniform sentence length

## Before delivering — run this check

```bash
# Paste the draft to a file first, then:
grep -n "Hawaii[^ʻ]" draft.md      # bare Hawaii (should be empty)
grep -n "Hawai'i\|Hawai‘i" draft.md # fake ʻokina U+2018 (should be empty)
grep -n "%" draft.md                # should be "percent"
grep -n "!" draft.md                # should be empty
```

Then read once for: paragraph length (≤3 sentences), sentence variety (are there any short punches?), whether any claim lacks a source in positions.md or the corpus, and whether a legislator got blamed by name.

**Flag to the user, don't silently resolve:** any claim you couldn't source, any position not in positions.md, and any place you used a statistic whose original source you couldn't verify.
