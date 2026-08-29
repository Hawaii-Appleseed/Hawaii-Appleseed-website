# Hawaiʻi Appleseed Writing Bot

> Migrated 2026-08-05 from the standalone `appleseed-writing-bot` repo into
> this website repo (minus the internal `relationship-memory/` module, which
> stays private). The static search app moved again 2026-08-29 to
> `Hawaii-Appleseed/staff-updates-internal` (`content-search/` there) — it was
> never linked from the public site, so it now lives behind that repo's
> Cloudflare Access gate instead of on public GitHub Pages. This repo keeps
> the corpus and the build engine; `.github/workflows/deploy-content-search.yml`
> rebuilds the bundle here and pushes it to the hub repo. New corpus content
> arrives via `.github/workflows/refresh-corpus.yml`, which scrapes
> hiappleseed.org every Sunday in GitHub Actions.

RAG-powered writing assistant. Generates testimony, blog posts, and op-eds in Hawaiʻi Appleseed's voice, anchored to a curated `positions.md` and grounded in retrieved excerpts from HA's prior writing.

**Stack:** ChromaDB (semantic retrieval) + Claude Sonnet 4.6 (generation) with prompt caching.

---

## Setup

```bash
pip install -r requirements.txt
```

### API keys

```bash
export ANTHROPIC_API_KEY=sk-ant-...   # required
export OPENAI_API_KEY=sk-...          # optional — better embeddings
```

Without `OPENAI_API_KEY` the bot falls back to local sentence-transformer embeddings (no API cost, slightly weaker retrieval).

---

## How it works

Every generation receives three things:

1. **`positions.md`** — HA's curated stances, voice rules, and language conventions. **This is the most important file in the repo.** It is injected verbatim into every prompt and treated as authoritative.
2. **Retrieved context** — semantically relevant chunks from `testimony/`, `blog-posts/`, `publications/`, and `reference/`, tagged with metadata (doc type, topic, year, bill, support/oppose).
3. **Your task** — what you want written.

Output cites sources inline (`[1]`, `[2]`) and lists them at the end. The bot is instructed to flag — not invent — positions that aren't in `positions.md`.

---

## Daily use

### Source search UI (no API key, $0)

A local search tool over the whole corpus — semantic + keyword, with links back
to the source. No AI generation, so it needs no API key and costs nothing per
query. Good when you want to *find the right prior passage and write it yourself*.

```bash
./run_search.sh          # opens localhost:8501
```

Runs on local MiniLM embeddings + BM25 + a local cross-encoder rerank. The
launcher unsets `OPENAI_API_KEY` so it always uses the local (free) index.

### Build the index (first run, and after adding new docs)

```bash
python bot.py --reindex
```

### Generate

```bash
# Testimony — restricted to recent testimony in the right topic
python bot.py "Draft testimony in support of HB2049 expanding the conveyance tax" \
    --mode testimony --topic tax-and-budget --year-min 2024

# Blog post — pull from blog corpus
python bot.py "Write a blog post about why Hawaiʻi needs paid family leave" \
    --mode blog --doc-type blog

# Quick generation with default retrieval
python bot.py "Draft sample testimony supporting universal school meals" --mode testimony

# Debug — see what was retrieved before generation
python bot.py "..." --show-sources
```

### Editing positions

Edit `positions.md` directly. **No reindex needed** — the bot reads it fresh on every run. Items marked `[REVIEW]` or `[ADD]` are flagged for policy staff to confirm or fill in.

---

## Flags

| Flag | Purpose |
|------|---------|
| `--reindex` | Rebuild the ChromaDB index. Run after adding new `.txt` files. |
| `--mode {testimony,blog,op-ed}` | Hint the bot to follow that mode's structural conventions. |
| `--doc-type {testimony,blog,publication,reference,relationship_memory}` | Restrict retrieval to one document type. `relationship_memory` queries the coalition/meeting/people notes directly. |
| `--topic <name>` | Restrict retrieval to one testimony topic folder (`labor`, `housing`, `tax-and-budget`, `food-equity`, `transportation`). |
| `--year-min <yyyy>` | Only retrieve documents from this year or later. |
| `-n / --n-results <int>` | Number of chunks to retrieve (default 8). |
| `--memory` | Fold in **relationship memory** (coalition/meeting/people notes) as internal background context. Off by default. |
| `--memory-n <int>` | Number of relationship-memory chunks to include with `--memory` (default 6). |
| `--show-sources` | Print full retrieved chunks before generation. Useful when output looks off. |

If a filtered query returns nothing, the bot retries without the filter rather than generating from no context.

---

## Library structure

```
appleseed-writing-bot/
├── bot.py                # Main script
├── positions.md          # ← Curated HA stances. Edit freely.
├── README.md
├── requirements.txt
├── .chroma/              # ChromaDB index (auto-created, gitignored)
├── testimony/
│   ├── labor/
│   ├── tax-and-budget/
│   ├── transportation/
│   ├── food-equity/
│   └── housing/
├── blog-posts/<year>/
├── publications/         # Auto-scraped reports (YYYY-MM-DD_slug.txt)
├── reference/            # Long-form reference docs
├── relationship-memory/  # Internal coalition/meeting/people memory module (see its METHODOLOGY.md)
│   ├── data/             #   structured memory — indexed as doc_type=relationship_memory
│   └── ingest/           #   Slack/email/meeting ingestion + synthesis pipeline
└── scrape_publications.py
```

### Relationship Memory module

`relationship-memory/` adds an internal layer of coalition and meeting
intelligence — Slack, email, and shared meeting notes distilled into people
dossiers, meeting summaries, projects, decisions, and action items. The bot can
draw on it as **background context** for framing and targeting drafts, but it is
never quoted, cited, or attributed in published output (excluded from retrieval
by default; opt in with `--memory` or the UI checkbox). See
[`relationship-memory/METHODOLOGY.md`](relationship-memory/METHODOLOGY.md).
**Confidential** — keep this repo private.

### File naming hints (improves metadata extraction)

The bot infers metadata from path + filename:

- **Bill number:** include in filename (e.g. `HB2360_2026_Paid_Family_Medical_Leave.txt`)
- **Year:** include 4-digit year in filename or in the path
- **Sample/template:** prefix with `sample_` so it's still indexed but flagged as non-canonical
- **Topic:** lives in the `testimony/<topic>/` folder

The bot also derives `position` (support/oppose/comment) from the testimony's opening paragraph.

---

## What's coming next (Week 2+)

Currently the bot is a CLI run by one person. Planned:

- Streamlit UI on Cloud Run — non-Devin staff can use it
- Inline-citation rendering (instead of `[1]` markers)
- Structured testimony output (committee, position, key points, ask, citations as JSON)
- Hybrid retrieval (BM25 + dense) and recency decay
- Per-mode exemplar anchoring (always include the strongest recent testimony as a structural template)
- Eval harness — 15–20 hand-curated prompts with reference outputs to catch voice regressions
- Auto-ingest pipeline (scrape nightly, diff-based reindex)
