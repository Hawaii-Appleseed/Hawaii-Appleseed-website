# Generated — do not hand-edit

Every file in this directory is built from `../../writing-bot/` by
`.github/workflows/deploy-content-search.yml` and committed by CI. Hand edits
are silently overwritten on the next corpus change.

| File | What it is |
| --- | --- |
| `chunks.json` | Passage-level corpus chunks with metadata (source, year, doc type, topic). |
| `bm25.json` | Precomputed BM25 statistics (idf, term frequencies, doc lengths). |
| `docs.json` | Per-document metadata: title, stance, external refs. |
| `embeddings.bin` | Float32 `[n × 384]` embedding matrix, row-major, L2-normalized. |
| `embeddings.meta.json` | Model, dtype, dim, count, sha256 — validated against `chunks.json` at load. |
| `positions.json` | Appleseed's issue positions, from `writing-bot/positions.md`. |
| `topics.json` | Topic facet values. |
| `tokenizer_fixture.json` | Tokenizer cases pinning the JS port to Python's behavior. |
| `corpus/` | Full source text, for the in-app "read full source" view. Wiped and rewritten each build. |

## To change what's here

Change the **inputs**, not these files:

- Corpus content → `writing-bot/` (usually via `refresh-corpus.yml`)
- Positions → `writing-bot/positions.md`
- Chunking / export logic → `writing-bot/tools/build_static.py`
- Embeddings → `writing-bot/tools/embed_corpus.mjs`

Then let CI rebuild:

```bash
gh workflow run deploy-content-search.yml --ref main
```

## Why it's committed rather than built at deploy time

The site's Pages deploy (`deploy.yml`) is a plain upload with **no build step**
— a deliberate constraint (see `CLAUDE.md`). Committing the bundle keeps that
true: only `deploy-content-search.yml` runs the heavy Python/Node build, and
only when `writing-bot/**` actually changes.

**CI output is canonical.** A local build will differ byte-wise (float jitter
across architectures), so don't commit one to "fix" a diff.
