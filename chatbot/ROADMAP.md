# Ask Hawaiʻi Appleseed: next improvements

Scoped 2026-10-21, after the graphics and drawn-chart work. Ordered by what unblocks the most. Sizes are rough: **S** is an afternoon, **M** a day or two, **L** longer than that.

## Blocked on people, not code

These gate everything else; none can be done from here.

1. **Anthropic API key** in a dedicated Console workspace with a spend limit, then `wrangler secret put ANTHROPIC_API_KEY`. Until then the live model path has only been exercised by replaying Haiku and Sonnet answers through the real checks.
2. **Cloudflare Access application** for `ha-ask.dtomkatsu.workers.dev`; send the Audience tag, set `ACCESS_AUD` in `worker/wrangler.toml`, redeploy. Until then every route answers 503 (on purpose).
3. **Staff sign-off on the draft positions** (25, all `status: draft`). Nothing public ships without it, and approving a position also brings its graphic (`--public` build).
4. **Credit expiry:** the Console promotional credit expires 2026-11-12; production needs a payment method.

## Recommended next (in this order)

### 1. Fact cross-check at build time: DONE 2026-10-21
`figures.py` / `check_figures.py`, run in every build and gating `--public` (see the README, *Figure cross-check*). First run found the conveyance allocation missing its "up to" and dollar caps, three loosened qualifiers, and a mix-up of the DHHL waitlist (nearly 30,000) with DHHL's build-out estimate ($800 million for nearly 6,000 families). Correction to an earlier note in this file: I first reported the staff file's "6,000 families ($800M backlog)" as unpublished; both figures *are* published, as the build-out estimate, and the fix is to say what each one measures.
- **Next on this item:** it checks that a figure was published in a similar context, not that our sentence means the same thing. Item 2 closes that by showing each figure's published sentence beside ours for a person to read.
- Not covered yet: `about.md` / `practical.md` (they come from live site pages; `check_figures.py --all` lists what it cannot tie to the corpus), years, and small counts.

### 2. Sign-off review page for staff: DONE 2026-10-21, as a Google Doc
`signoff_doc.py` builds it in Communications & Media › Website: 25 positions (word for word, with chart, research links, aliases, and each figure beside its published sentence), 23 ready-made answers, 6 fixed replies, each with a decision box. `--read` lists decisions and `--apply` marks positions approved in `positions.md` (see the README, *Positions: sign-off*).
- **Next on this item:** ready-made answers and fixed replies have no status line, so approvals for them are read but not applied; add one (`faq.json` flag, a `fixed.json`) so the public build can leave out an unapproved ready-made answer the way it leaves out an unapproved position. Until then the public build ships all of them, so staff should approve Parts 2 and 3 before launch.

### 3. "Ask a person" hand-off (S, practical value)
When the assistant says "I don't have that", or a question is about a specific situation, offer a button that opens a prefilled email to info@hiappleseed.org (a `mailto:` the visitor sends themselves; the assistant still never contacts anyone). Include the question text only if the visitor clicks. Add the phone number and contact page beside it. Closes the biggest dead end in the current answers.

### 4. Measure, without keeping text (S–M)
The Worker logs one counts-only line per request. Add a small daily roll-up (routes: ready-made / stance / model; drawn charts accepted vs rejected and why; uncited answers; deferrals; refusals; spend) written to KV and shown on the staff hub. This is how we find out whether drawn charts are earning their keep, whether Haiku is enough, and what to make a ready-made answer next. No question text is stored outside the opt-in feedback ratings.
- Weekly: pull feedback (`eval/pull_feedback.mjs`) and turn each "No" into a golden eval case or an alias.

### 5. Keep the corpus current (M)
- A scheduled workflow that re-vendors `chatbot/vendor/` when the website repo's corpus changes, rebuilds the index, runs the suites, and opens a PR. `vendor.py --check` already detects drift.
- Bill status goes stale the moment the session ends; add a "session" switch (2027 opens in January) so answers say "I have not checked this session" instead of citing 2026 data.
- Nightly **live** eval against the real model once the key exists (about 140 questions, roughly $0.05 on Haiku): catches drift when content or prompts change.

### 6. Drawn-chart comparability guard (S)
The quote checks catch invented numbers, wrong scale and mixed units. They cannot tell whether two real numbers *should* sit side by side. Cheap tightening: require a bar chart's rows to come from one source (one `ref`, or one report) unless the labels are explicitly paired in the quote; reject charts whose rows are different years of different measures. Then read a sample of accepted charts from the pilot before deciding whether to allow them in the public build (`DYNAMIC_GRAPHICS`).

### 7. More vetted graphics, and a way to share them (M)
- Gaps by issue area: renter cost burden, SNAP/ESAP timeline, Act 46 revenue loss, the Keiki Credit, "housing before handcuffs" ($300 million prisons vs $185 million DHHL, now only drawn on demand). Each is a `graphics.json` entry with quotes; the build already refuses unquoted numbers.
- Reporters and legislative staff are two of the audiences: add **Copy as image** and **Copy the table** to a chart, with the source line baked in.

## Before the public launch (checklist, not improvements)

- Turnstile tested live; `ALLOWED_ORIGINS` set to the real site; per-IP limits reviewed for a public audience.
- A screen-reader pass (VoiceOver) over the charts and the "Show the numbers" tables; the 375px and desktop checks are done.
- Staff read a sample of drawn charts and of canned stance answers; decide on `DYNAMIC_GRAPHICS` for public.
- Privacy and "AI can be wrong" wording reviewed by whoever signs off on the organization's public statements.
- Publish through `python3 scripts/squarespace.py <target> --go`, never by hand; deploy the public Worker with `npm run deploy:public`.

## Parked, with the reason

- **Embedding / hybrid retrieval.** BM25 gets 45 of 46 on the retrieval set; wait for real questions before adding a vector index (cost and a second thing to keep in sync).
- **Routing hard questions to Sonnet.** Haiku and Sonnet both pass the checks; revisit with real traffic and item 4's numbers.
- **Other languages.** The prompt already answers in the visitor's language, but ready-made answers and positions would need reviewed translations; scope after the English launch.
- **Moving `chatbot/` to its own repo.** The README has the `git subtree split` recipe; do it if PR #43 cannot merge for long, since merging publishes the whole repo root to public Pages (including draft positions).
