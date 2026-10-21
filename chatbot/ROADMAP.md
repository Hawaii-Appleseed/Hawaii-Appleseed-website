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

### 3. "Ask a person" hand-off: DONE 2026-10-21
`worker/src/handoff.js` and the `PERSON` box in `index.html` (see the README, *Ask a person*). A `mailto:` with the visitor's question prefilled, the office phone, and the Contact page, under any answer the assistant could not give and under the no-position reply; never on legal help. Haiku and Sonnet each add `[[staff]]` where it fits (see the eval cases `ho-*`).
- **Next on this item:** the Contact page also has a form; a deep link that prefilled it would beat `mailto:` for visitors without a mail app, but that is Squarespace's form and cannot be prefilled today. Track how often the button is shown (item 4's roll-up) and, when feedback exists, whether the people it was shown to rated the answer "No".

### 4. Measure, without keeping text: DONE 2026-10-21
`worker/src/stats.js` and `/stats` (see the README, *Usage roll-up*): per-day counts by route, spend, uncited answers, "ask a person" and why, drawn charts shown or refused with a reason code, turned-away requests, ratings, distinct people. No text, email, or IP is stored; a test checks.
- **Next on this item:** (a) link `/stats` from the staff hub (that is the `staff-updates-internal` repo, so a separate change); (b) alert when a day's spend passes 80 percent of the budget or the "came up empty" rate jumps (a line in the daily digest or a Slack post is enough); (c) with a few weeks of data, decide Haiku vs Sonnet and whether to keep drawn charts on for the public build.
- **Known limit:** the free Cloudflare plan allows 1,000 KV writes a day, about 200 requests with the limiters and this roll-up. Workers Paid before launch.

### 5. Keep the corpus current: DONE 2026-10-21 (the workflows start once this is on main)
`chatbot-corpus.yml` + `corpus_check.sh` (weekly), `freshness.py` + `record_deploy.py` + `deployed.json`, `content/session.json` and the covered-session switch, `chatbot-live-eval.yml` (nightly, dormant until the key exists). See the README, *Keeping it current*.
- **Changed from the plan:** re-vendoring on a schedule is moot while `chatbot/` sits in this repo (`vendor/` is local and gitignored); the weekly check and the freshness record do that job. The session switch flips on January 1, not on the convening date, on purpose.
- **Next on this item:** (a) set the `ANTHROPIC_API_KEY` repository secret so the nightly eval runs; (b) decide whether `npm run deploy` should run in Actions with a scoped Cloudflare token, so a weekly "behind" issue can become an automatic redeploy for the pilot (not for the public Worker); (c) when 2027 bills exist, update `covered` and the outcome text together.

### 6. Drawn-chart comparability guard: DONE 2026-10-21
`worker/src/charts.js` now refuses bars whose rows are not side by side in the source (different sections or reports unless one sentence carries all the numbers; far apart within a section; no unit; a label with no word from its own quote; more than six bars). The five real charts Haiku and Sonnet drew earlier all still pass; a pair from different reports is refused (`different_sources`). The first 20 accepted charts a day are kept (chart only, no visitor text) and shown at `/stats/charts` for a person to read. See the README, *Charts the assistant draws itself*.
- **The decision this feeds:** after a few weeks of pilot use, read `/stats/charts` and decide whether drawn charts stay on in the public build. Nothing can catch two real numbers from one paragraph that measure different things; reading a sample is the only check for that.

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
