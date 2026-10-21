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
  ← { answer, sources[], related[], flags }
```

| Path | What it is |
|---|---|
| `content/about.md` | Organization facts, written from the site pages. Edit and rebuild. |
| `content/practical.md` | How to subscribe, give, contact, apply, follow bills. Each section carries the live page it came from, checked 2026-10-20. |
| `vendor.py` | Copies the few files the assistant reads from the rest of the website repo into `vendor/` (see *Vendoring* below). |
| `check_links.py` | Fetches every link the assistant can show (pages, reports, PDFs) and reports any that fail. Run before each deploy. |
| `content/positions.md` | Public positions, each tagged `<!-- status: draft -->` or `approved by …`. |
| `build_index.py` | Builds `worker/src/index.json` (core text + BM25 index over publications, blog, testimony). Generates the bill-outcomes section from `tax-fairness/data/bill-status.json`. |
| `worker/src/` | `index.js` Worker entry · `handler.js` one chat turn · `legal.js` the gate · `prompt.js` rules · `retrieve.js` BM25 · `tokenize.js` |
| `index.html` | The embeddable widget (own wrapper, tokens only, DOM-built rendering). `squarespace-inject.html` is its generated paste payload. |
| `worker/src/research.js` | Picks the "Related research" list shown under each answer (see below). |
| `eval/` | `golden.jsonl` (82 cases, including multi-turn follow-ups) + `run_eval.mjs`. |
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

**Moving `chatbot/` to its own (private) repo.** Everything except the widget builds on its own: `git subtree split --prefix=chatbot -b chatbot-standalone` keeps the history; in the new repo remove the `vendor/` ignore, run `python3 vendor.py --from <website checkout>`, and commit `vendor/`. Keep `index.html` and `squarespace-inject.html` in the website repo: they are the public widget (no positions in them) and depend on `assets/tokens.css` and `scripts/squarespace.py`. Refresh the snapshot after each weekly corpus refresh, the way `deploy-content-search.yml` pushes to the private hub repo. A copy of `chatbot/` with no website repo around it was verified to pass every suite (Worker, workerd runtime, Python, offline eval).

## Research links

Every answer links to Hawaiʻi Appleseed's research in three ways, none of which depends on the model remembering to:

1. **Citations.** The model cites what it uses as `[C12]` (a position or fact) or `[2]` (a report, blog, or testimony excerpt). The Worker turns those into numbered links, each shown in a **Sources** list with the report year and a **PDF** link. Links are built from the index, never from model text, and raw URLs in an answer are stripped.
2. **Curated reports per position.** Each position in `content/positions.md` has a `<!-- research: slug, slug -->` line naming the reports behind it (checked against the publication text, not just titles). The builder fails if a slug is not a real report. When a position is cited, or is the best match for the question, its reports appear under **Related research**.
3. **Search.** If the answer cited a retrieved excerpt, the best-scoring other reports from the search are added too (at most three in all).

Related research is left off for questions that cite no research ("who is the executive director?"), and for legal or refused replies. Testimony has no public URL, so it informs answers but cannot be linked.

## Positions: sign-off

Every position in `content/positions.md` has a status line. `python3 chatbot/build_index.py --public` (and `npm run deploy:public`) leaves out everything not marked `<!-- status: approved by NAME YYYY-MM-DD -->`, so a public launch can only say what staff have approved. A test enforces this. The pilot build includes drafts.

Lines starting "2026 outcome" were written from *Policy in Perspective 2026* (Aug 13, 2026) and the Legislature's feed. Where a bill has no outcome line, nobody checked its final status, and the assistant is told to say so (paid family leave HB2360, pay transparency HB2367, bridge coverage HB1546, and medical debt SB3025 have none).

## Deploy (Cloudflare)

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
