# Ask Hawaiʻi Appleseed (public Q&A assistant)

A chat assistant for public visitors. It answers questions about the organization, its research, and its policy positions from Hawaiʻi Appleseed's own published writing, cites its sources, and answers any request for legal help with a fixed "no".

This is separate from `writing-bot/`, which is the staff drafting tool. They share the corpus; nothing here reads `writing-bot/reference/` (internal meeting notes) or the relationship-memory module.

**Status: pilot build.** Positions are drafts awaiting staff sign-off, and the live model path has not been exercised yet (no API key was available when this was built). See *Before it goes live*.

## How a question is answered

```
widget (index.html, on hiappleseed.org)
  → Worker  POST /chat
      1. origin check, Turnstile, per-visitor + whole-site rate limits
      2. legal-help gate (legal.js): clear requests get the fixed reply, no model call
      3. BM25 search of the corpus (retrieve.js) → top 6 excerpts
      4. Claude: rules + positions + org facts (cached) + excerpts (per question)
      5. cleanup: [C12]/[2] markers → numbered links we built; raw URLs stripped;
         a [[LEGAL]] reply from the model becomes the same fixed text
      6. research links (research.js): sources get year + PDF; "Related research" is added
      7. graphics (graphics.js): a position or ready-made answer brings its graphic; a question that asks
         for a chart finds one by name; a [[graphic: id]] marker from the model is checked and stripped
  ← { answer, sources[], related[], graphics[], flags }
```

| Path | What it is |
|---|---|
| `content/about.md` | Organization facts, written from the site pages. Edit and rebuild. |
| `content/practical.md` | How to subscribe, give, contact, apply, follow bills. Each section carries the live page it came from, checked 2026-10-20. |
| `vendor.py` | Copies the few files the assistant reads from the rest of the website repo into `vendor/` (see *Vendoring* below). |
| `check_links.py` | Fetches every link the assistant can show (pages, reports, PDFs) and reports any that fail. Run before each deploy. |
| `content/faq.json` | Ready-made answers to the 23 questions asked most (mission, history, leadership, how to give, contact, jobs, ...). The quickest file for staff to review. |
| `content/graphics.json` | The explainer graphics (see *Graphics* below). Every figure carries a quoted proof from the approved text; the build fails without it. |
| `content/topics.json` | Which issue area(s) each report belongs to; drives "latest research" and "research on housing". |
| `content/positions.md` | Public positions, each tagged `<!-- status: draft -->` or `approved by …`. |
| `build_index.py` | Builds `worker/src/index.json` (core text + BM25 index over publications, blog, testimony). Generates the bill-outcomes section from `tax-fairness/data/bill-status.json`. |
| `worker/src/` | `index.js` Worker entry · `handler.js` one chat turn · `legal.js` the gate · `prompt.js` rules · `retrieve.js` BM25 · `tokenize.js` |
| `index.html` | The embeddable widget (own wrapper, tokens only, DOM-built rendering). |
| `build_embed.py` | Builds the widget into one self-contained, ASCII-only file (`dist/embed.html`) with the design tokens and ʻokina fonts inlined, and the Worker URL and Turnstile key written in. Works with no website repo. |
| `squarespace-inject.html` | The same widget built by the website repo's `scripts/squarespace.py` (the `--go` publish route). Only used while `chatbot/` sits inside the website repo. |
| `worker/src/graphics.js` | Chooses which graphic (if any) goes under an answer. |
| `worker/src/research.js` | Picks the "Related research" list shown under each answer (see below). |
| `eval/` | `golden.jsonl` (137 cases, including multi-turn follow-ups) + `run_eval.mjs`. |
| `tokenizer_vectors.json` | Shared test vectors keeping the Python and JS tokenizers identical. |

## Run it locally

```bash
cd chatbot/worker && npm install
npm run dev:mock          # no key needed: answers by quoting the best excerpt (UI + retrieval + citations)
npm run dev               # real model: needs ANTHROPIC_API_KEY or ~/.anthropic_api_key
```

Serve the repo root (`python3 -m http.server`) and open `/chatbot/index.html?endpoint=http://localhost:8791/chat` (the `endpoint` override works only on localhost).

## Tests and eval

```bash
python3 -m unittest discover -s chatbot/tests     # index builder: drafts, privacy guards
cd chatbot/worker && npm test                     # tokenizer parity, legal gate, retrieval, handler, budget, rate limits
cd chatbot/worker && npm run test:workerd         # the real Worker in Cloudflare's runtime (workerd) with simulated KV
python3 chatbot/check_links.py                    # fetch every link the assistant can show (needs network)
node chatbot/eval/run_eval.mjs --offline          # legal gate + retrieval on the golden set, no key
node chatbot/eval/run_eval.mjs                    # LIVE: all 56 cases through the model (spends credits)
node chatbot/eval/run_eval.mjs --model claude-haiku-5-5   # compare models (prints cost per question)
node chatbot/eval/run_eval.mjs --dry --model claude-haiku-5-5   # no key: build real prompts, ESTIMATE tokens and cost
# No API key? Export the exact prompts, answer them with any model (e.g. subagents on a subscription),
# then grade the saved answers with the real checks:
node chatbot/eval/export_prompts.mjs --ids exec-director,pos-conveyance --out prompts.md
node chatbot/eval/run_eval.mjs --replay answers.json
```

The offline pass is in CI-able shape today. The live pass is the one that tells you whether answers are right; run it before any launch and again after any change to `prompt.js` or the content files.

## Vendoring: building without the website repo

`build_index.py` reads only four things from outside `chatbot/`: `writing-bot/{publications,blog-posts,testimony}`, `writing-bot/sources.py` with its blog URL map, and `tax-fairness/data/bill-status.json` (about 3 MB). `python3 chatbot/vendor.py` copies exactly those into `chatbot/vendor/`, in the same layout, and writes `vendor/MANIFEST.json` (source commit, per-file hashes). When a manifest exists the builder uses the copy; `CHATBOT_SOURCE=live` forces the live tree. The Worker's `/health` reports which snapshot an index came from.

- `python3 chatbot/vendor.py --check` exits 1 if the copy has drifted from the source (for CI in the repo that owns the corpus).
- `writing-bot/reference/` (internal meeting notes) is never copied; a test enforces it.
- A test proves a build from the vendored copy is identical to a build from the live tree (core text, report catalog, chunks, search index).
- `vendor/` is git-ignored here, because these files already live in `writing-bot/` in this public repo. Delete `chatbot/.gitignore` when `chatbot/` moves to its own repo and commit `vendor/` there.

**Everything lives in one repo, widget included.** `vendor.py` also copies `assets/tokens.css` and `assets/okina.css` (13 KB), and `build_embed.py` inlines them, so the widget needs nothing from the website repo or its Pages host. To publish: `python3 build_embed.py --endpoint https://<worker>/chat --sitekey <turnstile key>` and paste `dist/embed.html` into a Squarespace Code Block on the page (while `chatbot/` is inside the website repo, `python3 scripts/squarespace.py chatbot --go` does the same through the usual route).

**Moving `chatbot/` to its own (private) repo.** `git subtree split --prefix=chatbot -b chatbot-standalone` keeps the history. In the new repo delete `.gitignore`'s `vendor/` line, run `python3 vendor.py --from <website checkout>`, and commit `vendor/`. Drop `squarespace-inject.html` (the website repo's generated copy) and use `build_embed.py` instead. Refresh the snapshot after each weekly corpus refresh, the way `deploy-content-search.yml` pushes to the private hub repo. `build_index.py` warns if `vendor/` has fallen behind a live tree it can see. A copy of `chatbot/` with no website repo around it was verified to pass every suite (Worker, workerd runtime, Python, offline eval) and to build the widget.

## Ready-made answers

The questions visitors ask most (*What is your mission?*, *Who is the executive director?*, *How do I donate?*, *What's your phone number?*, *Are you hiring?*, *Are you a bot?*, hello, thanks) are answered from `content/faq.json` with no model call: instant, free, and the same reviewed words every time. 23 answers, each with its own source links.

**Matching is strict on purpose.** The question's topic words (with filler like the organization's name, "my", "please", "right now" set aside, and a few synonyms folded) must be *exactly* a listed phrasing's. So "What is the mission of Hawaiʻi Appleseed?" gets the stock mission answer, while "What is your mission regarding housing?", "What's your position?", or a bill number go to the model. Wrong stock answers are the failure to avoid; a model answer in their place costs a few tenths of a cent and is fine.

**How well it recognizes phrasings.** On wording I had not seen, the first try matched 58% and 35% on two fresh sets, with one wrong answer (fixed by making matching exact). After adding each miss as a phrasing, both sets match 98 to 100%, which says nothing about the next set. So expect most, not all, common phrasings to hit; the rest are answered by the model. When staff see the model answering a common question, add its wording to that entry's `variants` and add the phrasing to `eval/canned_sets.json`.

**Guarded at build time.** `build_index.py` fails the build if a stock answer cites a page that is not in the content, cites a number that does not match its sources, uses `%` or an unmarked `Hawaii` or an exclamation point, or quotes a phone number, email, dollar amount, year, or zip code that is not already in `about.md` or `practical.md`. The offline eval also checks that every stock answer satisfies the golden expectations of the questions it intercepts. `CANNED=off` (a var) sends everything to the model, for comparing.

## "Where do you stand on X?" (stance questions)

A question like *What's your stance on the conveyance tax?*, *Do you support the empty homes tax?*, or *Where does Appleseed stand on rent control?* takes one of three routes, decided in `worker/src/stance.js` before any model call:

1. **A position we hold** (any section of `content/positions.md`, 25 of them): the position is stated as written, with its report links and what happened in 2026. No model, no cost, same words every time. A topic names a position only by being one of its **aliases** (the `<!-- aliases: ... -->` line, the ways visitors name it) or most of its title. Position text is never searched: an early version let "charter schools" (mentioned in passing in the school meals position) return the school meals answer, so it no longer can.
2. **Our work never uses a word of the topic** (and no near-typo of one): a fixed deferral, "Hawaiʻi Appleseed has not published a position on that in the material I have", pointing to the Issues page and the office. It never repeats the visitor's words. Deferral is deliberately rare: wrongly deferring on something we have written about is worse than asking the model.
3. **Everything else**, including topics our work only touches: the model, told to report only what Hawaiʻi Appleseed's own publications argue, name the publication, say it is published work and not a vote of the board, and to say "no stated position" when the excerpts merely mention the topic or are about something else (rental vouchers are not school vouchers).

A question with a second question inside it ("... and what happened in 2026?"), someone else's position ("the Governor's stance on ..."), or a topic too general to be one thing ("do you support taxes?") is not treated as a stance question.

**How it did on wording it had not seen.** Two fresh sets: 73% and 50% of position questions got their position directly on the first try (the rest went to the model, which is safe), with **no wrong position and no wrong deferral** in either set; every uncertain topic reached the model. Both Sonnet and Haiku, run on the uncertain topics (stadium, bitcoin, gun control, school vouchers, charter schools, the death penalty), said there was no stated position and did not mistake passing mentions for one; on topics our work does cover but no position names (vaping taxes, rent control), they reported what the publication argues. After adding every miss as an alias or pattern both sets match nearly fully, which says nothing about the next set: expect to add aliases as real questions arrive.

**When our work says it but no position does.** Two topics found this way, now positions (status `draft`): rent control (the 2026 blog "Unburden the burdened") and vaping and tobacco taxes (*Policy in Perspective 2022*). The positions file also now records the estate tax breaks stance, which an earlier version wrongly listed as "no stated position". When staff see the model reporting a publication's argument on a topic that deserves a position, promote it: add a section and its aliases.

## Graphics

The assistant shows small, plain charts under an answer when one explains the point better than words: where conveyance tax revenue would go, how a marginal rate works, capital gains versus ordinary income, REITs, the empty homes tax, the school meals income cliff, where Hawaiʻi's transportation money goes, the pay gap, the minimum wage law, the 2026 bill scoreboard, and a history timeline. Each has a **Show the numbers** table and links its source.

**The model never draws anything.** It cannot write a number onto a chart or send markup. The library is `content/graphics.json`, plain data. A graphic reaches the page three ways:

1. **A position or ready-made answer brings its own** (`<!-- graphic: id -->` in `positions.md`; `"graphic"` in `faq.json`). "What's your stance on the conveyance tax?" shows the revenue split; "When was Hawaiʻi Appleseed founded?" shows the timeline. No model, no cost.
2. **A question that asks for a picture.** "Show me a chart of the empty homes tax revenue", "explain how marginal rates work". Each graphic lists `aliases`; all of one alias's words must be in the question, and the question must ask to see or have something explained (chart, graphic, diagram, visualize, explain, show me, timeline), except the two that go with their topic by themselves (`"auto": true`: the 2026 scoreboard and the history timeline). Aliases are two topic words at least, so "a timeline of the conveyance tax" does not pull up the organization's history.
3. **The model names one.** The system prompt lists the available graphics; the model can end its answer with `[[graphic: id]]`. The Worker strips the marker, drops any id not in the library, and keeps it only if the answer says at least one of the graphic's figures. At most two graphics per answer.

**Every number is traceable.** `build_index.py` refuses to build unless each row of a graphic quotes the phrase(s) from `about.md`, `practical.md` or `positions.md` it rests on (word for word), every number the row shows is in that quote, a bar's label says its value, the title, unit and note use only numbers from the graphic's own quotes, the source is a real page or report, and aliases belong to one graphic. The one made-up graphic, the marginal-rate illustration, is computed at build time so its total cannot disagree with its parts, is labeled **Illustration** with a note that the numbers are made-up and not HB2049's rates, and only ships if the conveyance position does.

**Public build.** A `--public` build checks each graphic against the approved text alone and leaves out any that rests on a draft position (today that is everything except the history timeline). Approving a position brings its graphics with it, with no other change.

The page draws bars, stat tiles, timelines, and the scoreboard from the data (`index.html`, `drawGraphic`), setting text only and bar widths: bars use the chart tokens (teal, ash for context), one series one color, thin with a rounded data end, every value printed on its bar, and the same numbers in a table. Verified at 375px and desktop.

To add a graphic: add it to `content/graphics.json` with proofs, run `python3 chatbot/build_index.py`, and add a golden case (`eval/golden.jsonl`, category `graphic`).

### Charts the assistant draws itself

When none of the vetted graphics fits (a comparison, breakdown, or change over time that the sources state in numbers), the model may end its answer with `[[chart: {json}]]`: bars, stat tiles, or a timeline. The Worker (`worker/src/charts.js`) shows it only if **every figure is quoted from the text the model was given**:

- each row carries a `quote` copied word for word from the one KNOWLEDGE section or excerpt it names (`ref`: `C37`, or `2` for excerpt [2]); the quote must really be in that text (case, quote marks, okina, and dashes aside);
- every number a row shows (label, display, year, value) must appear in that row's quote; a bar's value must be the number in its display, with the same scale word ("million") the quote uses;
- bars must compare like with like: all dollars, all percents, or all counts, at one scale, so "$300 million" can sit beside "$185 million" and "66 percent" cannot sit beside "$5.68 billion";
- 2–8 bars or timeline rows, 1–4 stat tiles, plain text only (anything with `<` or `>` is refused), and at least one source with a link;
- any failure drops the chart and keeps the answer. A vetted graphic that fits wins, so a drawn chart appears only when no vetted one does, and never on a ready-made or legal reply.

The page marks these **Drawn by the assistant**, says to check them against the sources, and the *Show the numbers* section lists the quoted passage behind each figure. The checks catch invented numbers, wrong scale, and mixed units; they cannot judge whether two real numbers *should* be compared, so the pilot's feedback buttons matter here. Turn it off with `DYNAMIC_GRAPHICS = "0"` in `wrangler.toml` (the prompt then omits the instructions and any marker is stripped). Staff should read a sample of drawn charts before the public launch and decide whether to keep it.

## Research links

Every answer links to Hawaiʻi Appleseed's research in three ways, none of which depends on the model remembering to:

1. **Citations.** The model cites what it uses as `[C12]` (a position or fact) or `[2]` (a report, blog, or testimony excerpt). The Worker turns those into numbered links, each shown in a **Sources** list with the report year and a **PDF** link. Links are built from the index, never from model text, and raw URLs in an answer are stripped.
2. **Curated reports per position.** Each position in `content/positions.md` has a `<!-- research: slug, slug -->` line naming the reports behind it (checked against the publication text, not just titles). The builder fails if a slug is not a real report. When a position is cited, or is the best match for the question, its reports appear under **Related research**.
3. **Search.** If the answer cited a retrieved excerpt, the best-scoring other reports from the search are added too (at most three in all).

Related research is left off for questions that cite no research ("who is the executive director?"), and for legal or refused replies. Testimony has no public URL, so it informs answers but cannot be linked.

## Positions: sign-off

Every position in `content/positions.md` has a status line. `python3 chatbot/build_index.py --public` (and `npm run deploy:public`) leaves out everything not marked `<!-- status: approved by NAME YYYY-MM-DD -->`, so a public launch can only say what staff have approved. A test enforces this. The pilot build includes drafts.

Lines starting "2026 outcome" were written from *Policy in Perspective 2026* (Aug 13, 2026) and the Legislature's feed. Where a bill has no outcome line, nobody checked its final status, and the assistant is told to say so (paid family leave HB2360, pay transparency HB2367, bridge coverage HB1546, and medical debt SB3025 have none).

## Internal pilot (staff only): deployed, locked until Access is set

Deployed 2026-10-21 as `https://ha-ask.dtomkatsu.workers.dev` (the same Cloudflare account as the staff hub). The page is served by the Worker itself (`GET /`), so one URL does everything, with no CORS and no Squarespace, and it runs on Haiku 5.5 with the staff-pilot notice on top.

**It is locked by construction.** `REQUIRE_ACCESS=1` makes `src/access.js` demand a valid Cloudflare Access token on every route (signature, issuer, expiry, audience) and answer 503 until `ACCESS_AUD` is set. The staff hub's README records why the Worker checks the token itself and does not trust "it sits behind Access": per-deployment URLs sit outside the Access application. Preview URLs are off.

To switch it on (about five minutes; 1 and 2 are yours):
1. **Anthropic key.** Console, new workspace "ha-ask" with a spend limit, then an API key in that workspace. Store it with `cd chatbot/worker && npx wrangler secret put ANTHROPIC_API_KEY` and paste when prompted.
2. **Access application.** Zero Trust > Access > Applications > Add > Self-hosted; domain `ha-ask.dtomkatsu.workers.dev`; policy Allow for your staff emails (reuse the hub's policy). Copy the application's **Audience tag**.
3. Put the tag in `ACCESS_AUD` in `wrangler.toml` and run `npm run deploy` (or `wrangler deploy --var ACCESS_AUD:<tag>`).
4. Open the URL, sign in, ask something. Spend is bounded by `DAILY_BUDGET_USD` ($3), `DAILY_CAP` (500), per-person `PER_DAY` (40), and the workspace limit.

Switch models with `MODEL` (Haiku 5.5 now). `wrangler tail ha-ask` shows request counts, token usage and uncited answers, never message text.

## Deploy (Cloudflare), the public launch version

1. `cd chatbot/worker && npm install && npx wrangler login`
2. `npx wrangler kv namespace create RATE`, then uncomment the `[[kv_namespaces]]` block in `wrangler.toml` with the id.
3. Secrets: `npx wrangler secret put ANTHROPIC_API_KEY`, `TURNSTILE_SECRET`, `RATE_SALT`. Create the API key in a **dedicated Console workspace** with its own spend limit.
4. Cloudflare dashboard: a rate-limiting rule on `/chat` is the hard backstop; the KV counters are approximate.
5. `npm run deploy` (pilot) or `npm run deploy:public` (approved positions only).
6. Set `data-endpoint` (the Worker URL) and `data-turnstile-sitekey` on `#ha-ask` in `index.html`, then publish with `python3 scripts/squarespace.py chatbot --go`.

**Pilot placement:** an unlisted Squarespace page is not private. Serve the widget from the staff hub (behind Cloudflare Access) and set `ALLOWED_ORIGINS` to that origin. Move to the public site only after sign-off and a clean live eval.

## Spend limits: what stops a runaway bill

From the hardest stop to the softest:

1. **Anthropic Console (cannot be bypassed by a code bug).** Give the bot its own workspace with its own spend limit, and lower the organization's monthly limit (it was $1,000, above the $400 credit). With no card on file, calls fail once the credit is gone and the widget says "unavailable".
2. **Daily dollar budget in the Worker.** `DAILY_BUDGET_USD` (pilot: 3) is counted from the token usage each answer reports, priced in `worker/src/pricing.js`; once it is spent the Worker answers 429 until the next UTC day. Needs the `RATE` KV namespace, like the limits below.
3. **Request limits.** Per visitor `PER_MINUTE` (6) and `PER_DAY` (40), whole site `DAILY_CAP` (500). A Cloudflare rate-limiting rule on `/chat` is the hard version of these; the KV counters are approximate.
4. **Per-request size.** User messages ≤ 800 characters, ≤ 8 messages of history, ≤ 700 output tokens, effort `low`, six excerpts, prompt cached for an hour, and the legal gate answers without a model call.
5. **Model choice.** Haiku 5.5 costs about 20 times less than Sonnet 5.5 for the same answers in the tests so far.

These limits do nothing until the KV namespace exists (deploy step 2). Raise them for a public launch.

## Cost (estimates from prompt size; confirm with the first live eval)

The cached prompt is about 8,300 tokens; excerpts add about 1,700 per question.

| Model | Per question, cache warm | Per 1,000 questions |
|---|---|---|
| `claude-sonnet-5-5` (default) | ≈ $0.0075 | ≈ $8 |
| `claude-haiku-5-5` | ≈ $0.0004 | ≈ $0.40 |

Cold-cache requests cost about three times as much. Set `MODEL` in `wrangler.toml` after comparing the two on the live eval. The whole-site `DAILY_CAP` (default 2,000 requests) bounds worst-case spend.

## Before it goes live

- [ ] Staff review and approve (or edit) each position; replace `draft` with `approved by …`.
- [ ] Run the live eval; fix prompt or content for any failure; compare Sonnet and Haiku.
- [ ] Confirm the legal-help reply (`LEGAL_REPLY` in `worker/src/legal.js`). It says Hawaiʻi Appleseed is not a direct service provider and points to the Hawaiʻi State Bar Association's legal assistance list, which is the referral the organization's own Contact page gives.
- [ ] Re-check `content/practical.md` against the live site before launch (`python3 chatbot/check_links.py`, then read the Contact, Subscribe, Support, and Opportunities pages): phone, email, giving levels, and the Quorum action center are copied from them.
- [ ] Confirm the privacy note on the page. It says messages go to Anthropic and Hawaiʻi Appleseed keeps no copy: the Worker logs counts and flags only, never message text.
- [ ] Decide who watches the Cloudflare logs and the Console spend dashboard, and what happens when credits run out (the assistant shows "unavailable" and stops; no card means no overage).
- [ ] The promotional API credit expires 2026-11-12. Production needs a payment method or invoicing on the Console organization.
- [ ] Optional: turn on server-side refusal fallback (`FALLBACKS=default`). Off by default: for Sonnet 5.5 it only reroutes cyber and frontier-AI declines, which this bot should not produce, and the beta request shape is untested here.

## CI

`.github/workflows/chatbot.yml` runs the Python and Worker tests, the offline eval, the design lint, a Wrangler bundling dry run, and the workerd runtime test on every pull request that touches `chatbot/` or the corpus. It needs no secrets and never deploys. The model-dependent eval and `check_links.py` are run by hand.

## Known limits

- Client-supplied assistant turns are untrusted (a visitor can forge history). Positions come only from the system prompt, never from the conversation, and answers are limited to the last 8 messages.
- Bill outcomes come from published material and a feed that can lag; the assistant points to capitol.hawaii.gov for final status.
- The index is rebuilt by hand. Wiring `build_index.py` into `refresh-corpus.yml` (so the Worker redeploys after each weekly scrape) is the natural next step once a deploy token exists as a repo secret.
