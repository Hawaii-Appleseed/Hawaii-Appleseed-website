# Hawaiʻi Appleseed — website & tools

Source for the Hawaiʻi Appleseed Center for Law & Economic Justice web presence,
plus the data tools that feed it.

**Start here if you're new (human or AI):** read this file, then
[`CLAUDE.md`](CLAUDE.md) for the non-negotiable brand/engineering rules.

---

## The two deploy models (read this first — it explains most of the layout)

This repo publishes in **two different ways**, and confusing them is the
single most common mistake.

### 1. Squarespace paste-in pages

`hiappleseed.org` runs on **Squarespace**. The main marketing pages here are
*not* served from this repo — they're built into paste-ready blobs and manually
injected into Squarespace Code Blocks.

```
<page>.html  ──(scripts/build_squarespace.py)──►  squarespace-ready/<page>.html  ──(paste by hand)──►  hiappleseed.org/<slug>
```

**Always paste from `squarespace-ready/`, never the raw root file** — the raw
file has un-rewritten asset paths and internal links, and pasting it produces
missing images plus a duplicated footer.

Regenerate with:

```bash
python3 scripts/build_squarespace.py
```

### 2. GitHub Pages sub-sites

Everything under a sub-directory with its own `index.html` is served directly
from GitHub Pages at `https://hawaii-appleseed.github.io/Hawaii-Appleseed-website/<dir>/`,
and embedded into or linked from Squarespace. These deploy automatically on
push to `main` via `deploy.yml` (a plain upload — **no build step**).

---

## Root pages → live URLs

Canonical mapping lives in `INTERNAL_LINK_MAP` in
[`scripts/build_squarespace.py`](scripts/build_squarespace.py) — if you change a
slug, change it there.

| Source file | Live URL |
| --- | --- |
| `index.html` | `/` |
| `issues.html` | `/issues` |
| `our-mission.html` | `/our-mission` |
| `our-story.html` | `/our-history` |
| `our-team.html` | `/our-team` |
| `board-of-directors.html` | `/board-of-directors` |
| `publications.html` | `/publications` |
| `in-the-news.html` | `/in-the-news` |
| `blog.html` | `/blog` |
| `support.html` | `/support` |
| `taxes-budget.html` | `/taxes-budget` |
| `food-security.html` | `/food-equity` |
| `housing.html` | `/affordable-housing` |
| `transportation.html` | `/transportation-equity` |
| `wages-labor.html` | `/wages-labor` |

Note the several places where **filename ≠ slug** (`our-story` → `/our-history`,
`food-security` → `/food-equity`).

`our-mission-light.html` and `our-story-light.html` are light-background
**variants** of those two pages — use one or the other, not both.

The five issue deep-dives (`taxes-budget`, `housing`, `food-security`,
`transportation`, `wages-labor`) share a mandatory common structure — see
CLAUDE.md before making any structural change to one of them.

---

## Directories

| Path | What it is |
| --- | --- |
| `assets/` | Shared images, fonts, `okina.css`. Referenced by absolute Pages URLs after the Squarespace build. |
| `content-search/` | **Content Search** static app — client-side semantic + keyword search over Appleseed's writing. Live at [`/content-search/`](https://hawaii-appleseed.github.io/Hawaii-Appleseed-website/content-search/). See its [README](content-search/README.md). |
| `writing-bot/` | RAG writing assistant + **the corpus** (testimony, blog posts, publications) that Content Search indexes. See its [README](writing-bot/README.md). |
| `tax-fairness/` | Tax Fairness Coalition sub-site (`/tax-fairness/`). Formerly its own repo. |
| `tax-timeline/` | Hawaiʻi tax history timeline (`/tax-timeline/`). |
| `millionaire-report/` | Millionaire tax report page (`/millionaire-report/`). |
| `ufsm/` | Universal Free School Meals dashboard (`/ufsm/`). |
| `rxkids/` | RxKids program page (`/rxkids/`). |
| `snap-medicaid-timeline/` | SNAP/Medicaid federal-cuts timeline (`/snap-medicaid-timeline/`). |
| `video-hero/` | Squarespace hero-video injection snippet. |
| `preview/` | Scratch preview page — not a production surface. |
| `scripts/` | Build + sync scripts (see below). |
| `squarespace-ready/` | **Generated.** Paste-ready output of `build_squarespace.py`. |
| `.github/workflows/` | Automation (see below). |

`ufsm`, `tax-fairness`, and `rxkids` are listed in `PAGES_SUBSITES` in the build
script: links to them get absolutized to the Pages host, because a bare relative
href resolves against the Squarespace slug and 404s.

---

## Automation

| Workflow | Trigger | Does |
| --- | --- | --- |
| `deploy.yml` | push to `main`, or dispatch | Uploads the whole repo to GitHub Pages. Plain upload, no build. |
| `sync-publications.yml` | nightly 22:00 UTC | Pulls blog/press/publications JSON from hiappleseed.org into `news.json` + `publications.json`, then dispatches `deploy.yml`. |
| `refresh-corpus.yml` | Sundays 15:00 UTC (5 AM HST), or dispatch | Scrapes hiappleseed.org for new posts/publications into `writing-bot/`, then dispatches the Content Search rebuild. |
| `deploy-content-search.yml` | push touching `writing-bot/**` or `content-search/js|index.html`, or dispatch | Rebuilds the search bundle (`content-search/data/`), runs the parity gate, commits, dispatches `deploy.yml`. |

**None of this depends on a personal machine** — the whole chain runs in Actions.

> **Gotcha that bit us repeatedly:** a push made with the default `GITHUB_TOKEN`
> does **not** fire another workflow's `on: push` (GitHub's recursion guard).
> Every workflow above that needs a downstream job dispatches it explicitly with
> `gh workflow run`. If you add automation that must trigger a deploy, do the same.

---

## Generated files — do not hand-edit

Edits to these are silently overwritten on the next run.

| Path | Regenerated by |
| --- | --- |
| `squarespace-ready/**` | `scripts/build_squarespace.py` |
| `content-search/data/**`, `content-search/api.json` | `deploy-content-search.yml` (CI) |
| `news.json` | `sync-publications.yml` (nightly) |
| `publications.json` | `sync-publications.yml` (nightly) |
| `writing-bot/blog-posts/`, `writing-bot/publications/` | `refresh-corpus.yml` (weekly scrape) |

To change what lands in these, change the generator — not the output.

---

## Common tasks

```bash
# Rebuild the paste-ready Squarespace blobs after editing a root page
python3 scripts/build_squarespace.py

# Refresh blog/press data by hand (normally nightly in CI)
python3 scripts/sync-news.py

# Force a Content Search rebuild (e.g. after a model change)
gh workflow run deploy-content-search.yml --ref main

# Pull in new hiappleseed.org content now instead of waiting for Sunday
gh workflow run refresh-corpus.yml --ref main

# Deploy (normally automatic on push)
gh workflow run deploy.yml --ref main
```

> Never `gh run rerun` a failed Pages deploy — it fails with a duplicate-artifact
> error. Start a fresh run with `gh workflow run deploy.yml` instead.
