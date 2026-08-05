# Hawaiʻi Appleseed Content Search

A fully static, client-side search over Hawaiʻi Appleseed's testimony, blog
posts, publications, and policy positions. Hybrid retrieval (BM25 + MiniLM
dense + RRF + cross-encoder rerank) with **all ML running in the browser** via
[Transformers.js](https://huggingface.co/docs/transformers.js) — no server, no
API cost. Served by GitHub Pages at `/content-search/`.

Ported from the writing bot's Streamlit Source Search (`../writing-bot/search.py`
lineage); the engine and corpus live in [`../writing-bot/`](../writing-bot/).

## How it works

- **Build time** (`../writing-bot/tools/`): the corpus is chunked, BM25
  statistics are computed, per-document stance/title/links are precomputed, and
  the corpus is **embedded with the exact same model + dtype the browser uses**
  (`Xenova/all-MiniLM-L6-v2`, q8, 256-token cap) so query and corpus share one
  embedding space.
- **Query time** (`js/`): a Web Worker embeds the query and runs the
  cross-encoder (models lazy-load on first search intent, ~44 MB one-time);
  everything else (tokenizing, BM25 scoring, RRF, bill boost, recency,
  grouping, highlighting) is a bit-for-bit JS port of the Python retrieval.

## Public API — for other projects

Everything under this directory is a public, CORS-enabled (GitHub Pages sends
`Access-Control-Allow-Origin: *`) static endpoint. Base URL:

    https://dtomkatsu.github.io/Hawaii-Appleseed-website/content-search/

| Endpoint | What it is |
|---|---|
| `api.json` | **Poll this.** Small manifest: `generatedAt`, per-file `sha256`, doc/chunk counts, model info. A change in any `sha256` (or `generatedAt`) means a new bundle shipped. |
| `data/docs.json` | Per-document metadata: title, stance, doc_type, topic, year, source links. Keyed by source path. |
| `data/positions.json` | Curated policy positions: title, stance, core argument, standard ask, associated bills. |
| `data/topics.json` | Topic list (testimony subject areas). |
| `data/chunks.json` | All public text chunks with metadata (the retrieval corpus). |
| `data/bm25.json` | BM25 statistics (idf, per-chunk tf) for keyword scoring. |
| `data/embeddings.bin` + `data/embeddings.meta.json` | Corpus embeddings, Float32 LE row-major; meta records model/dtype/dim/sha. |
| `data/corpus/<source-path>` | Full text of any source document (paths from `docs.json`). |

Polling pattern (e.g. from another repo's workflow or app):

```bash
curl -s https://dtomkatsu.github.io/Hawaii-Appleseed-website/content-search/api.json \
  | jq -r '.generatedAt, .counts.documents'
```

Compare `files["chunks.json"].sha256` against your last-seen value to detect
new content cheaply, then fetch only what changed.

## Build the data bundle

Normally CI does this (see Deploy below). Manually, from `../writing-bot/`:

```bash
python3 -c "import bot; bot.index_documents(force=False)"   # Chroma index
python3 tools/build_static.py --verify                       # data/* + api.json
python3 eval/static_dump.py > ../content-search/test/fixtures.json
cd tools && npm ci && node embed_corpus.mjs                  # embeddings.bin (q8)
```

`data/` and `api.json` are **committed** (the site's Pages deploy is a plain
upload with no build step; the bundle must exist in the repo).

## Run locally

```bash
python3 -m http.server 8531 --directory content-search
# open http://localhost:8531  (models lazy-load from the HF CDN on first search)
```

## Tests & parity

- **Model-free unit tests** (CI gate): `node content-search/test/run_all.mjs` —
  asserts the JS tokenizer, query expansion, pure-bill detection, BM25 public
  search, and `group_sections` match Python bit-for-bit.
- **Model quality probe** (after a dtype/model change):
  `node ../writing-bot/tools/probe_quality.mjs` compares dense top-K overlap and
  reranker rank-correlation between two embedding spaces (validated the
  fp32 → q8 switch: top-1 identical on all probe queries, mean Spearman 0.987).

## Deploy

`.github/workflows/deploy-content-search.yml` fires on pushes touching
`writing-bot/**` or this app's source. It rebuilds the bundle, skips out early
when content is byte-identical (modulo `api.json`'s `generatedAt`), otherwise
commits the new bundle and dispatches the site's plain Pages deploy
(`deploy.yml`). New corpus content arrives via the weekly content-monitor
(laptop launchd job → scrape → commit → push), which triggers exactly that
chain.
