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
| `content/positions.md` | Public positions, each tagged `<!-- status: draft -->` or `approved by …`. |
| `build_index.py` | Builds `worker/src/index.json` (core text + BM25 index over publications, blog, testimony). Generates the bill-outcomes section from `tax-fairness/data/bill-status.json`. |
| `worker/src/` | `index.js` Worker entry · `handler.js` one chat turn · `legal.js` the gate · `prompt.js` rules · `retrieve.js` BM25 · `tokenize.js` |
| `index.html` | The embeddable widget (own wrapper, tokens only, DOM-built rendering). `squarespace-inject.html` is its generated paste payload. |
| `worker/src/research.js` | Picks the "Related research" list shown under each answer (see below). |
| `eval/` | `golden.jsonl` (56 cases) + `run_eval.mjs`. |
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
cd chatbot/worker && npm test                     # tokenizer parity, legal gate, retrieval, handler
node chatbot/eval/run_eval.mjs --offline          # legal gate + retrieval on the golden set, no key
node chatbot/eval/run_eval.mjs                    # LIVE: all 56 cases through the model (spends credits)
node chatbot/eval/run_eval.mjs --model claude-haiku-5-5   # compare models
```

The offline pass is in CI-able shape today. The live pass is the one that tells you whether answers are right; run it before any launch and again after any change to `prompt.js` or the content files.

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

## Cost (estimates from prompt size; confirm with the first live eval)

The cached prompt is about 6,700 tokens; excerpts add about 1,700 per question.

| Model | Per question, cache warm | Per 1,000 questions |
|---|---|---|
| `claude-sonnet-5-5` (default) | ≈ $0.0075 | ≈ $8 |
| `claude-haiku-5-5` | ≈ $0.0004 | ≈ $0.40 |

Cold-cache requests cost about three times as much. Set `MODEL` in `wrangler.toml` after comparing the two on the live eval. The whole-site `DAILY_CAP` (default 2,000 requests) bounds worst-case spend.

## Before it goes live

- [ ] Staff review and approve (or edit) each position; replace `draft` with `approved by …`.
- [ ] Run the live eval; fix prompt or content for any failure; compare Sonnet and Haiku.
- [ ] Confirm what the legal-help reply should say. It is generic ("a licensed attorney or a legal aid organization") and names no organization; naming one is a staff decision (`LEGAL_REPLY` in `worker/src/legal.js`).
- [ ] Confirm the privacy note on the page. It says messages go to Anthropic and Hawaiʻi Appleseed keeps no copy: the Worker logs counts and flags only, never message text.
- [ ] Decide who watches the Cloudflare logs and the Console spend dashboard, and what happens when credits run out (the assistant shows "unavailable" and stops; no card means no overage).
- [ ] The promotional API credit expires 2026-11-12. Production needs a payment method or invoicing on the Console organization.
- [ ] Optional: turn on server-side refusal fallback (`FALLBACKS=default`). Off by default: for Sonnet 5.5 it only reroutes cyber and frontier-AI declines, which this bot should not produce, and the beta request shape is untested here.

## Known limits

- Client-supplied assistant turns are untrusted (a visitor can forge history). Positions come only from the system prompt, never from the conversation, and answers are limited to the last 8 messages.
- Bill outcomes come from published material and a feed that can lag; the assistant points to capitol.hawaii.gov for final status.
- The index is rebuilt by hand. Wiring `build_index.py` into `refresh-corpus.yml` (so the Worker redeploys after each weekly scrape) is the natural next step once a deploy token exists as a repo secret.
