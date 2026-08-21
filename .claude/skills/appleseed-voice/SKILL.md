---
name: appleseed-voice
description: Draft or revise writing in Hawaiʻi Appleseed's house voice — blog posts, testimony, op-eds, newsletter copy, web page prose, report narrative. Use whenever writing something that will go out under Hawaiʻi Appleseed's name, or when asked to check/revise existing copy for house voice. Also triggers on "in HA voice", "Appleseed style", "make this sound like us".
---

# Hawaiʻi Appleseed house voice

Writing that goes out under HA's name. Accuracy and faithfulness matter more than fluency.

> Paths are relative to the repo root (`Hawaii-Appleseed-website`) — run from there. Every measured claim below comes from the full blog corpus (112 posts, ~100,500 words, 2021–2026); the numbers behind them live in `reference/style-profile.md`.

## Step 1 — Load the authority (always, before drafting)

Read, in order:

1. **`writing-bot/positions.md`** — HA's curated stances + voice guide, maintained by policy staff. **Authoritative**: where it conflicts with anything below or with retrieved examples, positions.md wins. Read it fresh on every use.
2. **`reference/style-profile.md`** (in this skill) — measured corpus statistics, for calibration when a judgment call comes up.

**Position integrity — non-negotiable:** ground every factual claim in positions.md or a retrieved corpus document. Never invent statistics, bill numbers, hearing dates, committee names, or dollar figures. If the task needs a position positions.md doesn't cover — or contradicts one it does — stop and ask; inventing a stance is worse than an incomplete draft. Items marked `[REVIEW]` are unconfirmed extractions and `[ADD]` are known gaps: both mean "check with the user."

## Step 2 — Retrieve real examples

Don't write from these rules alone. Pull 2–4 actual posts on the nearest topic and read them:

```bash
grep -rl "<topic keyword>" writing-bot/blog-posts/2026/ writing-bot/blog-posts/2025/
```

Corpus layout: `blog-posts/<year>/`, `testimony/<topic>/`, `publications/`, `reference/`.

**Weight 2025–2026 heavily.** The voice measurably shifted — more first-person plural, more contractions, fewer raw statistics. Older posts are on-message but stiffer than current house voice.

**Skip the unpublished drafts as structural models** — about 8 corpus files are Google-Doc exports with `Title:` lines, `________` rules, or `[a]` comments (list in the profile). Their prose is house voice; their structure is not.

## Step 3 — Write to the arc

**Blog post** (per positions.md): values-grounded opening → problem → why the system fails the people most affected → data and named harms → proven model elsewhere → the bill or action in front of us.

**Testimony** (per positions.md): greeting → position → urgent context with named populations → evidence → counter the predictable opposition → restate the ask → mahalo close. Signature: "Hawaiʻi Appleseed Center for Law and Economic Justice".

### Openings

**Lead with a claim, not a number** — only 4 of 112 posts open on a statistic; evidence arrives in paragraphs 2–4 to support a claim already made. The dominant openers, in order: legislative/news hook, values or thesis premise, flat problem-state declaration. Opening paragraph: 1–3 sentences, ending on the thesis or the tension the piece resolves.

### Shape

- **600–1,100 words** is the modal post.
- **Paragraphs: 1–3 sentences** — two-thirds of the corpus's body paragraphs are one or two. A 6-sentence block reads wrong.
- **Vary sentence length hard.** The rhythm is a long analytic sentence followed by a short declarative punch: "The evidence is overwhelming."
- **Subheads:** median 3 per post; short posts often have none. **Title Case noun phrases, ~5 words, no finite verb**: `A Pattern Worth Naming`, `The Broken Promise of Inclusionary Zoning`.
- **Titles:** the reverse — **sentence case**, long and explanatory (~11 words), often `[Evocative phrase]: [How/Why + concrete claim]`.

### Closings

2–4 sentences that restate the stake in moral terms and point forward. Resolute, not triumphant — the two-beat short close is a signature: "Pedestrians across Hawaiʻi deserve better. We will keep pushing until they get it."

**85 percent of posts have no call to action.** Default to ending on the argument. When there is an ask, it goes in the final paragraph, concrete and low-pressure.

## Mechanical rules (checkable — verify before delivering)

| Rule | Detail |
|---|---|
| **ʻokina** | `Hawaiʻi`, `Oʻahu`, `Kauaʻi`, `ʻohana`, `kūpuna`, `ʻāina` — always, and always **U+02BB ʻ**, never a curly quote. **`Hawaiian` takes no ʻokina.** |
| **percent** | Spell it out in prose. |
| **Exclamation points** | Zero in the entire corpus. Never. |
| **Em dashes** | **Unspaced**: `responsibility—the`. En dash for numeric ranges (`2019–2022`). |
| **Person** | "We/our" is the **civic we** (Hawaiʻi, the public) — "our keiki," "our islands." No first-person singular outside explicitly personal pieces. The org is third person ("Hawaiʻi Appleseed") when reporting its own actions. |
| **Contractions** | Sparingly: fine in rhetorical or direct-address sentences, almost never inside a data or policy-mechanics paragraph. |
| **Attribution** | A **hyperlink on the source's name**, not an "according to" clause. Name real authorities inline: ITEP, U.S. Census Bureau, DBEDT, Hawaiʻi Foodbank, ALICE. |
| **Hedging** | Hedge *magnitudes* ("roughly $25.2 million") — **never the judgment.** |
| **House spellings** | `nonprofit`, `healthcare`, `policymaker`, `the Legislature` (capitalized). `keiki`/`kūpuna` unitalicized. Oxford comma genuinely optional — the corpus is split evenly. |

**Hawaiian vocabulary is small, load-bearing, and unglossed.** `keiki` and `kūpuna` do most of the work; `ʻohana`, `kauhale`, `pilina` appear where they carry real meaning. `kamaʻāina`: zero corpus uses. `mahalo`: zero in blogs — it belongs in testimony closings. Don't decorate with Hawaiian words.

## Stance

- **Prescribe to institutions, not people.** "The Legislature must," "Congress should." Bills are named constantly; legislators almost never — and when they are, it's to *credit* them. Criticism attaches to a body: "the Senate did not assign conferees."
- **Never personify opponents.** "Opponents"/"critics" appears once in the whole corpus; "some argue" never. Name the *idea*, grant its logic, dismantle it with evidence. The signature move: "It's not about X. It's about Y."
- **State uncertainty; volunteer data limits.** "These results paint an incomplete picture of poverty here in the state."
- **Report losses honestly**, then reframe toward the next session.
- **Urgent but measured. Advocates, not screamers.**

## Anti-patterns — verified zeros across the corpus

1. **Partisan labels** — "Democrats," "GOP," "partisan," "radical," "socialist": all zero. `Republican` appears only procedurally.
2. **Attacking individuals or attributing motive** — "greedy," "corrupt," "shameful," "outrageous": zero.
3. **Consultant/LLM register** — "delve," "tapestry," "unpack," "deep dive," "landscape of," "stakeholders," "at the end of the day": zero.
4. **Deficit labels for people** — "the poor," "the homeless," "illegal immigrants," "handouts": zero. Use "working families," "low-income households," "houseless residents," "undocumented immigrants" (the corpus is actively shifting `homeless` → `houseless`).
5. A shock statistic as the opening, or a CTA anywhere before the final paragraph.
6. First-person singular; uniform sentence length; paragraphs of 5+ sentences.

## Before delivering

```bash
grep -nE "Hawaii([^ʻa]|$)" draft.md   # bare Hawaii — "Hawaiian" is correctly excluded
grep -n  "Hawai’i\|Hawai‘i" draft.md  # curly-quote fake ʻokina (U+2019 / U+2018)
grep -n  " — " draft.md               # spaced em dash — house style is unspaced
grep -n  "%" draft.md                 # should be "percent" in prose
grep -n  "!" draft.md                 # should be empty
```

Then read once for: paragraph length (≤3 sentences), sentence variety (any short punches?), whether any claim lacks a source, and whether a legislator got blamed by name.

**Flag to the user, don't silently resolve:** any claim you couldn't source, any position not in positions.md, any statistic whose original source you couldn't verify.
