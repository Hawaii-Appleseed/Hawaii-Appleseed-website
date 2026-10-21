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
      8. hand-off (handoff.js): if the assistant could not answer, say so to the page so it can offer "Ask a person"
  ← { answer, sources[], related[], graphics[], handoff, flags }
```

| Path | What it is |
|---|---|
| `content/about.md` | Organization facts, written from the site pages. Edit and rebuild. |
| `content/practical.md` | How to subscribe, give, contact, apply, follow bills. Each section carries the live page it came from, checked 2026-10-20. |
| `content/staff.json` | Who is on staff (name, title, work email, as on the Our Team page) and which topics go to whom, for "who's the best person to talk to about this?". Checked against the Staff list in `about.md` by the build. A draft until staff approve it (see *Ask a person*). |
| `vendor.py` | Copies the few files the assistant reads from the rest of the website repo into `vendor/` (see *Vendoring* below). |
| `check_links.py` | Fetches every link the assistant can show (pages, reports, PDFs) and reports any that fail. Run before each deploy. |
| `content/faq.json` | Ready-made answers to the 23 questions asked most (mission, history, leadership, how to give, contact, jobs, ...). The quickest file for staff to review. |
| `figures.py`, `check_figures.py` | The figure cross-check (see below) and its command-line report; `content/figures.json` lists figures a person has accepted. |
| `content/bill-status-snapshot.json`, `snapshot_bills.py` | The last good copy of the Legislature bill feed's latest action per bill. The feed is refreshed every 30 minutes by `fetch-bill-status.yml`, and capitol.hawaii.gov sometimes answers 403; `build_index.py` uses the live feed for every bill that has data and this snapshot for the rest (and warns), so one bad refresh cannot crash a build or erase what the assistant knows. Re-save it with `python3 chatbot/snapshot_bills.py` (it refuses unless nearly every bill has data). |
| `worker/src/stats.js` | The daily counts-only roll-up and the `/stats` page (see *Usage roll-up*). |
| `corpus_check.sh`, `freshness.py`, `record_deploy.py`, `content/session.json` | Keeping it current: the one-command weekly check, how far behind the deployed assistant is (`deployed.json`), and the covered-session switch. |
| `signoff_doc.py` | Builds the staff sign-off review as a Google Doc, and reads the decisions back (see *Positions: sign-off*). |
| `ROADMAP.md` | What to do next, in order, what is blocked on people, and what is parked. |
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

The assistant shows small, plain charts under an answer when one explains the point better than words: where conveyance tax revenue would go, how a marginal rate works, capital gains versus ordinary income, REITs, the empty homes tax, the school meals income cliff, where Hawaiʻi's transportation money goes, the pay gap, the minimum wage law, the 2026 bill scoreboard, a history timeline, and (added later) the prison budget beside the Hawaiian Home Lands budget, what Act 46 costs and the fix proposed, the millionaire's surcharge, medical debt, SNAP certification and the ESAP waiver, the evidence cited on rent control, and how many households rent. Eighteen in all. Each has a **Show the numbers** table and links its source.

**Sharing a chart.** Every chart has **Copy as image** and **Copy the table**, for reporters, legislative staff and partners. The picture is drawn on a canvas in the visitor's browser from the same data (no library, nothing fetched): the chart, its unit and note, its source, and a "Hawaiʻi Appleseed · hiappleseed.org" footer, so it keeps its source wherever it is pasted; a chart the assistant drew itself also says so, and a made-up illustration says it is made up. It goes to the clipboard when the browser allows (Safari needs the picture handed over as a promise during the click, which is how it is done), otherwise it is saved as a file. The table copies as tab-separated text with the note and source. If the browser refuses the clipboard altogether, the text is shown selected to copy by hand. The wording is `SHARE` in `index.html` and is quoted in the sign-off review, Part 3.

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
- bars must also be **side by side in the source**: every bar quoted from the same section or excerpt (the same `ref`) and within about 900 characters of the others, or else one sentence of a source that carries all of the numbers. A "$300 million" from one report and a "$185 million" from another, or the same measure in different years from different reports, is refused (`different_sources`, `far_apart`). A bar chart also needs a unit (`no_unit`), a label that uses a distinctive word from the text around its own quote (`label_not_in_quote`; it may spell out an acronym that text spells out), and at most six bars;
- 2–8 bars or timeline rows, 1–4 stat tiles, plain text only (anything with `<` or `>` is refused), and at least one source with a link;
- any failure drops the chart and keeps the answer. A vetted graphic that fits wins, so a drawn chart appears only when no vetted one does, and never on a ready-made or legal reply.

**What this still cannot catch:** two real numbers from the same paragraph that measure different things (a one-time appropriation beside a yearly budget), because no check reads meaning. So the Worker keeps the first 20 charts of each day that passed every check (the chart only: title, rows, quotes and sources, all from our own publications, no visitor text, 45 days) and shows them at `/stats/charts` (behind the Access gate, linked from `/stats`). Read a sample before deciding whether to leave drawn charts on in the public build (`DYNAMIC_GRAPHICS`); a pattern of misleading ones means turn them off.

The page marks these **Drawn by the assistant**, says to check them against the sources, and the *Show the numbers* section lists the quoted passage behind each figure. The checks catch invented numbers, wrong scale, and mixed units; they cannot judge whether two real numbers *should* be compared, so the pilot's feedback buttons matter here. Turn it off with `DYNAMIC_GRAPHICS = "0"` in `wrangler.toml` (the prompt then omits the instructions and any marker is stripped). Staff should read a sample of drawn charts before the public launch and decide whether to keep it.

## Figure cross-check

The positions are adapted from a staff file whose entries are marked `[REVIEW]`, and the stance answers repeat them word for word with no model in between, so a wrong figure in `positions.md` goes out as fact. `figures.py` ties every figure to something Hawaiʻi Appleseed has published.

```
python3 chatbot/check_figures.py              the positions (also runs in every build_index.py)
python3 chatbot/check_figures.py --matches    also show, beside each figure, the published sentence it was matched to
python3 chatbot/check_figures.py --all        also about.md and practical.md (those come from site pages, not the corpus)
python3 chatbot/check_figures.py --strict     exit 1 on anything unexplained (for CI)
```

It pulls out dollar amounts, percents, counts of 1,000 or more, and bill and Act numbers (spelled-out "sixty-six percent" counts), and compares each with the reports, blog posts, and testimony in the corpus and the Legislature's bill feed. A figure is only **backed** when a published sentence states it *about the same thing*: the words around it overlap ours (the label right before it counts double), or it shares a bill number or another of our figures. A bare "6,000" proves nothing, because with 43 reports some unrelated page always says it. Each figure ends up as:

| Status | Meaning | `--public` build |
|---|---|---|
| backed | a published sentence says this about this | passes |
| qualifier | the published wording is qualified (*up to*, *capped at*, *at least*) and ours is not | **fails** |
| topic | only a report on the same subject states it; read it against the source | passes, listed |
| none | no published source | **fails** |
| accepted | a person read the source and said it is fine | passes |

Accept a figure in `content/figures.json` with the source and a reason; the tests fail if an accepted entry no longer matches any figure (so the list cannot rot). A pilot build only prints the counts. The public build checks the positions it is about to ship, so approving a position is also where its figures get cleared.

**What it found the first time.** The conveyance tax position said revenue would go to "affordable housing (20 percent), DHHL (30 percent), DURF (20 percent), conservation (5 percent)". The published post says *up to* 20 percent (or $40 million, whichever is less), *up to* 30 percent (capped at $60 million a year), 20 percent for DURF, and *up to* 5 percent (or $10 million): the shares are maximums. The position and its chart now say so. It also caught "about 70 percent" (published: over 70), "$900 million" (published: more than $900 million), and "5 percent of income or more" (published: at least). And it showed that the staff file's "DHHL waitlist is 6,000 families ($800M backlog)" ran two published figures together: nearly 30,000 families are on the waitlist (*Policy in Perspective 2026*), while $800 million is DHHL's estimate for building homes for nearly 6,000 families (the conveyance tax post). The position now says both.

**What it cannot do.** It shows that a figure was published in a similar context, not that our sentence means what the published one means: "waitlist is 6,000 families" would still pass, because the same published sentence holds both 6,000 and $800 million. That is why `--matches` prints the published sentence beside ours; staff sign-off should read those pairs (roadmap item 2 builds the page for it).

## Ask a person

When the assistant cannot answer, the page offers a way to reach the team instead of leaving a dead end: **Email our team** (a `mailto:` link to the office address with the visitor's question already in the message), **Call (808) 587-7605**, and a **Contact page** link. The visitor sends the email from their own mail app, so nothing goes anywhere unless they choose to send it, and the assistant still never contacts anyone or collects anything.

- **When it appears** (`worker/src/handoff.js`): the model ends its answer with `[[staff]]` (the prompt asks for it when it says it lacks the information, when the question is about the visitor's own situation, or when only a staff member could decide: a press interview, a partnership, a volunteer role); or the answer plainly says it has nothing ("I don't have that", "no stated position"); or the reply is the fixed "no published position" one. **Never** on a legal-help reply (the bar association's list is the answer there; the office does not take cases), and not on a stated position or a ready-made answer.
- **Where the details come from:** `index.contact`, built from the "Contact the office" section of `content/practical.md` (the build fails if it has no email, phone, or page), so the button cannot drift from what the assistant says in words.
- **The wording** (`PERSON` in `index.html`) is quoted in the sign-off review, Part 3, so staff approve the button text and the prefilled email.
- The marker is stripped from the answer; a half-typed one is stripped too. The page checks the email, phone, and link before drawing anything.

### Who to talk to about this

Asked "who's the best person to talk to about this?" (or "who should I contact about housing?", "who works on transit?"), the assistant names the one or two staff whose titles match, says in a few words what their title covers, and the page puts an **Email {first name}** button under the answer for each, next to the office buttons. "About this" means the topic of the conversation so far.

- **Where it comes from:** `content/staff.json`: the 12 people on the Our Team page (names, titles, work emails) and 10 `routes` from a topic to the people whose titles fit. `build_index.py` appends it to the knowledge as a "Who to talk to about what" section, and **the build fails** if a name or title disagrees with the Staff list in `content/about.md`, an email is not an `@hiappleseed.org` address, or a route names someone who is not listed. The routes are inferred from titles and bios, not a staff list of who handles what, so **they are a draft that staff review** (Part 4 of the sign-off Doc); where no title fits (wages and labor) the section says so and the assistant points to the office.
- **How the page learns who:** the model ends its answer with `[[staff: arjuna-heim, kamakani-albano]]`, ids exactly as the section gives them. The Worker keeps only ids that are in `index.staff` (at most two), so a made-up name names no one and the button falls back to the office. A public build with no approved routing has no section and no `index.staff`, so the assistant says the Our Team page lists the staff.
- **Only what is published:** the emails are the ones the Our Team page already shows, the prefilled message goes from the visitor's own mail app, and the assistant never promises that anyone will reply or when. Nothing about who was named is stored but the id, counted on `/stats` ("Staff the assistant pointed people to").
- **Keeping it right:** a person joining, leaving, or changing title means editing `staff.json` and `about.md` together (the build checks they agree). Re-read the Our Team page every few months; the weekly corpus check does not look at it.
- A question that asks *who* never matches a ready-made answer built from "what can I ask" (`worker/src/canned.js`); "Who do I contact?" still gets the office's details.

## Usage roll-up (counts only)

`GET /stats` on the Worker (behind the same Cloudflare Access gate as everything else) shows what the assistant did each day, and `/stats.json?days=30` has the same numbers as data. It is for deciding things: is Haiku enough, are ready-made answers carrying the load, is it coming up empty, are drawn charts earning their keep.

- **What is counted** (`worker/src/stats.js`): answers per day and distinct people (a person is a hash of their Access email, counted once a day); where each answer came from (ready-made answer by id, stated position by title, no-position deferral, legal reply, model, refusal, error); model answers with no source ("came up empty"); how often "ask a person" was offered and why (marker, wording, deferral); charts shown with an answer (by id) and charts the model drew that were shown or refused, with the reason code (`quote_not_found`, `mixed_units`, `scale`, ...); tokens and spend per day; requests turned away (rate limit, budget, failed verification, malformed); and Yes/No ratings.
- **What is never kept there:** any question or answer text, any email, any IP address. The tests assert it (`worker/test/stats.test.mjs` runs every route and checks the stored document for the question words, the IP, and any "@"). Rated answers with their text are the separate opt-in feedback entries in KV (90 days), pulled with `eval/pull_feedback.mjs`.
- **How it is stored:** one small JSON document per day in the same KV namespace (`stats:YYYY-MM-DD`, kept 400 days), updated once per request. KV is not atomic, so two answers finishing together can lose a count: read the numbers as accurate to a few percent. A failed count never fails an answer.
- **KV limits.** The Cloudflare account is on the free plan, whose KV allows 1,000 writes a day. Each request now writes about five times (three limiter counters, the day's spend, and this roll-up), which is roughly 200 requests a day before KV refuses. Fine for the staff pilot; **move to Workers Paid before the public launch**, or the limiters themselves start failing.
- **Weekly routine:** open `/stats`, then pull the week's ratings (`eval/pull_feedback.mjs`) and turn each "No" into a golden eval case or an alias. A position asked for often that deferred, or a rejected-chart reason that keeps appearing, is the next thing to fix.

## Keeping it current

Three things move underneath the assistant, and each now has a check.

**1. The corpus.** `refresh-corpus.yml` adds reports, blog posts and testimony every Sunday, and the bill feed refreshes every 30 minutes, but the Worker only knows what it was built with. Committing with `GITHUB_TOKEN` does not trigger `chatbot.yml`, so the weekly **`chatbot-corpus.yml`** (Mondays, a day after the refresh) runs `chatbot/corpus_check.sh` against `main`: the index build in strict mode (a published report with no entry in `content/topics.json` fails, and the build lists the names), every figure in the positions against the published corpus, all the Python and Worker tests, the offline eval, the links the assistant can show, and `freshness.py`. It keeps one issue open (label `chatbot-drift`) while anything fails and closes it when green. You can run the same thing by hand: `./chatbot/corpus_check.sh`. It deploys nothing; the Cloudflare deploy needs a token and stays a person's decision.

**2. How far behind the deployed assistant is.** `npm run deploy` finishes by running `record_deploy.py`, which writes `chatbot/deployed.json` (commit it with the deploy). `python3 chatbot/freshness.py` lists the corpus files that changed since that commit and fails if the oldest is more than `--max-days` (14 in the weekly check) old. After a deploy: `cd chatbot/worker && npm run deploy`, then commit `chatbot/deployed.json`. (Re-vendoring on a schedule, the first idea, only matters once `chatbot/` lives in its own repo, since `vendor/` is local; `vendor.py --check` and this cover the difference.)

**3. The legislative session.** `content/session.json` says which session the content covers (2026). The generated bill-outcomes section and the cached rules use it, and **once the calendar year passes it** the assistant says what it knows is from that session: a stated position gets "This reflects the 2026 legislative session. The Legislature has met since, so check capitol.hawaii.gov for what has changed", and a model answer is told in its per-question block (the cached rules do not change with the date) that a newer session may be underway and not to guess at newer bills. The switch is the January 1 after the covered year, deliberately early: the Legislature convenes in the third week of January, and saying "may be out of date" a few weeks early costs less than citing last session as current. **When a new session's bills and outcomes are in the content, change `covered`** (and the position and outcome text) and rebuild.

**4. The model.** `chatbot-live-eval.yml` runs every golden case through the real model each night (Haiku by default, about 60 model calls, a few cents; `--max-usd 1` stops it at $1) and keeps one issue (`chatbot-eval`) open while any case fails. **It does nothing until a repository secret `ANTHROPIC_API_KEY` exists**: add a key from a dedicated Console workspace with its own spend limit, deliberately. Expect failures on the first live run: no case has ever run against the real API, only replays of Haiku and Sonnet answers through the same checks.

## Research links

Every answer links to Hawaiʻi Appleseed's research in three ways, none of which depends on the model remembering to:

1. **Citations.** The model cites what it uses as `[C12]` (a position or fact) or `[2]` (a report, blog, or testimony excerpt). The Worker turns those into numbered links, each shown in a **Sources** list with the report year and a **PDF** link. Links are built from the index, never from model text, and raw URLs in an answer are stripped.
2. **Curated reports per position.** Each position in `content/positions.md` has a `<!-- research: slug, slug -->` line naming the reports behind it (checked against the publication text, not just titles). The builder fails if a slug is not a real report. When a position is cited, or is the best match for the question, its reports appear under **Related research**.
3. **Search.** If the answer cited a retrieved excerpt, the best-scoring other reports from the search are added too (at most three in all).

Related research is left off for questions that cite no research ("who is the executive director?"), and for legal or refused replies. Testimony has no public URL, so it informs answers but cannot be linked.

## Positions: sign-off

Four kinds of words go out without a model checking them, and each has an approval status. A **public build** (`build_index.py --public`, `npm run deploy:public`) ships only what is approved; the pilot build includes drafts.

| What | Where its status lives | Not approved means |
|---|---|---|
| a stated **position** | `<!-- status: ... -->` in `content/positions.md` | left out of the public build (a visitor's question about it goes to the model, which says there is no stated position) |
| a **ready-made answer** | `status` in `content/faq.json` | left out (the question goes to the model, which answers from the organization's pages; more model calls, so more cost) |
| the **who-to-talk-to routing** (the people, titles, emails and which topics go to whom) | `status` in `content/staff.json` | left out (the assistant says the Our Team page lists the staff, and the page offers only the office) |
| a **fixed reply or page text** (legal-help reply, error messages, welcome line, privacy note, "ask a person" and chart-sharing wording) | `content/fixed.json` | **the public build refuses to run** until every one is approved: there is no fallback for words the page always uses |

A status is `draft` or `approved by NAME YYYY-MM-DD`. **Approval is of the exact words** (`approval.py`): `signoff_doc.py --apply` also records a `reviewed` hash of the words the reviewer saw (`<!-- reviewed: ... -->` for a position), and the build treats an approved item whose words have changed since as not approved ("changed since it was approved" in the build's skipped list). `--apply` itself refuses an approval whose Doc fingerprint no longer matches the content, so refresh the Doc and approve again. Writing `approved by NAME DATE` by hand, with no hash, still works and is not bound to the words, so use the review. Fixed replies live in the Worker's JavaScript and in `index.html`; `fixed.py` is the one place that knows where, so the review and the build read the same words (it needs `node`).

**The review lives in a Google Doc** ("Ask Hawaiʻi Appleseed: Sign-off Review (Draft)" in the shared Drive, Communications & Media › Website; this repo is public, so the link is not recorded here). It lists everything the assistant says without a model checking it: each position word for word with its chart, research links, aliases, and every figure beside the published sentence it was matched to; the ready-made answers; the fixed replies and page text (legal-help reply, no-position reply, error messages, welcome line, privacy note); and the who-to-talk-to routing (Part 4). Each item has a decision box (change ☐ to ☒), a reviewer line, and a notes line, so reviewers can tick, edit, and comment in the Doc itself.

```
P=~/internal-tools/appleseed-drive/.venv/bin/python        # the Drive pipeline's Python (it has the Google libraries)
$P chatbot/signoff_doc.py --html out.html                  render only (no Google needed)
$P chatbot/signoff_doc.py --update <docId>                 refresh the Doc after content changes (refuses if anyone has ticked a box)
$P chatbot/signoff_doc.py --read <docId>                   list the decisions
$P chatbot/signoff_doc.py --read <docId> --apply           mark ticked, named "Approve as written" positions approved in positions.md
```

`--apply` records an approval (and the hash of the words) for a position, ready-made answer or fixed reply only when exactly one box is ticked, it is "Approve as written", a reviewer name is filled in, and the words are still the ones in the Doc; edits, holds, removals, double-ticks and stale approvals are listed for a person to handle. An approved position still needs `build_index.py --public` and a deploy, and that build checks its figures against the published corpus again.

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
