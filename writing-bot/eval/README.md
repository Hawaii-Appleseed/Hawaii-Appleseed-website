# Eval harness

Golden test cases for retrieval + generation. Run before merging changes that touch `bot.py`, `retrieval.py`, `positions.md`, or the index.

## Run

```bash
.venv/bin/python eval/run_eval.py                    # full run (needs ANTHROPIC_API_KEY)
.venv/bin/python eval/run_eval.py --retrieval-only   # cheap; only checks must_retrieve_any
.venv/bin/python eval/run_eval.py --case hb2049      # one case (id substring match)
.venv/bin/python eval/run_eval.py --show-failures    # print failing-case output snippets
```

Exit code is non-zero if any assertion fails.

## Case format (`golden.jsonl`)

One JSON object per line:

| Field | Required | Meaning |
|---|---|---|
| `id` | yes | stable case name (kebab) |
| `prompt` | yes | the user prompt fed to the bot |
| `mode` | no | `testimony` / `blog` / `op-ed`, passed to `bot.generate` |
| `topic` | no | restricts retrieval to a `testimony/<topic>/` folder (`tax-and-budget`, `housing`, etc.) |
| `year_min` | no | restricts retrieval to docs from this year or later |
| `must_retrieve_any` | yes | list of substrings; for each, at least one retrieved source path must contain it |
| `must_include` | yes | substrings that must appear in the generated output (case-insensitive) |
| `must_not_include` | yes | substrings that must NOT appear in the output (case-insensitive) |
| `voice_rules` | yes | named checks (see below) |

### Voice rules

- `uses-okina` — output must contain `ʻ` (U+02BB)
- `has-sources-section` — output must have a `Sources` header
- `refusal-or-flag` — output must contain refusal language (`cannot`, `no position`, `not covered`, `flag`, `clarif`). Use for prompts asking for stances not in `positions.md`.

## Adding a case

1. Pick a real situation HA cares about. Write the prompt the way staff would.
2. Identify 1–3 source files the bot SHOULD draw on. Use distinctive substrings of their paths in `must_retrieve_any` (substring of slug is fine — e.g., `"empty-homes-tax-honolulu"`).
3. Add bill numbers / key phrases to `must_include`. Add `low-income` to `must_not_include` for any testimony (positions.md banned phrase).
4. Add `uses-okina` and `has-sources-section` for testimony / op-ed. Always add `uses-okina`.
5. Run `.venv/bin/python eval/run_eval.py --case <your-id>` and iterate.

## Baselines

| Date | Eval mode | Pass-rate (cases / checks) | Notes |
|------|-----------|----------------------------|-------|
| 2026-05-29 | retrieval-only | 5/12 (42%) / 22/32 (69%) | Baseline. MiniLM embeddings, dense-only retrieval, no rerank. |
| 2026-05-29 | retrieval-only | 6/12 (50%) / 23/32 (72%) | MiniLM + dense + BM25 (no rerank). Best MiniLM config. |
| 2026-05-29 | retrieval-only | 6/12 (50%) / 21/32 (66%) | MiniLM + dense + BM25 + rerank. Cross-encoder slightly hurts on weak base — full lift comes after the OpenAI embeddings switch. |
| 2026-05-30 | retrieval-only | 6/12 (50%) / 21/32 (66%) | After bill-number tokenization fix (`_BILL_SPACE_RE` + `_apply_bill_boost`). No general-eval regression; bill-number lookup now exact-match correct (verified separately via `ui_probe`). |
| 2026-06-01 | retrieval-only | 8/16 (50%) / 28/41 (68%) | Golden expanded to 16 cases (added 2 alias + 2 ranking probes). Pre-A1 numbers under new harness. |
| 2026-06-01 | retrieval-only | 9/16 (56%) / 29/41 (71%) | A1: bill-form normalization in `_tokenize` ("House Bill 1800" / "house-bill-1800" → "hb1800") + query-side acronym alias map (GET, SNAP, CTC, EITC, TAT, TANF, TOD, PFML, ADA, LIH, LIHTC). `alias-hb1800-housebill` now ranks canonical doc #1. `alias-get-grocery-tax` still fails on a `general-excise` substring that doesn't exist in any filename. |

## UI testing (search.py)

`eval/ui_probe.py` drives the real Streamlit app headlessly via `streamlit.testing.v1.AppTest`
(simulates typed queries + filter/toggle changes, asserts on rendered elements). Single or batch mode;
forces local embeddings. Two workflow harnesses exercise it across relevance / exact-match / filters /
robustness / links-render dimensions (`eval/search_analysis_workflow.js` is the lean, contention-free
variant — collect probe data once, fan out judgment). 2026-05-30 sweep: 0 exceptions across 36 edge-case
scenarios; bill-number search bug found + fixed; all other dimensions clean.
