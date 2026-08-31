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

Regenerate + copy to the clipboard in one step with the pipeline CLI
([`scripts/squarespace.py`](scripts/squarespace.py)):

```bash
python3 scripts/squarespace.py our-team        # rebuild, payload on clipboard
python3 scripts/squarespace.py our-team --go   # rebuild + push + open the editor
python3 scripts/squarespace.py                 # list every target
python3 scripts/squarespace.py --all           # rebuild everything, no copy
```

It resolves any target in the repo: pages built by `build_squarespace.py`
(copied from `squarespace-ready/`), hand-authored snippets like
`header-search` / `footer` / `video-hero` (copied as-is), and **any other
page or sub-site directory** via a generic embed builder — e.g.
`python3 scripts/squarespace.py snap-medicaid-timeline` regenerates
`snap-medicaid-timeline/squarespace-inject.html`. The generic builder
auto-scopes CSS under a wrapper id for standalone pages, rewrites
`window.onload`/`DOMContentLoaded` init to survive post-load injection,
absolutizes assets, remaps internal links, attaches the ʻokina fonts, and
entity-encodes non-ASCII. To make a brand-new page embeddable, just run it
through the CLI — no per-page code needed.

(`python3 scripts/build_squarespace.py` alone still works and only rebuilds
`squarespace-ready/`.)

### Fully automated publish (no clipboard, no DevTools)

`scripts/publish_squarespace.py` does the whole thing — rebuild, open the
editor, replace the Code Block, click SAVE:

```bash
.venv/bin/python scripts/publish_squarespace.py --login          # once, ever
.venv/bin/python scripts/publish_squarespace.py our-team --dry-run
.venv/bin/python scripts/publish_squarespace.py our-team
```

`--login` opens Chrome so you can sign in to Squarespace once; the session
lives in `.sqs-profile/` (gitignored) and is reused from then on. It drives
the Google Chrome already installed on the machine, in its own profile
directory, so it never fights your running browser.

After that, one command per page. `--dry-run` does everything except the
final SAVE click and leaves the window open to inspect. The payload is
injected straight from the local file, so this needs **no push and no Pages
round trip** — unlike `--snippet` below.

If SAVE comes back greyed out, that is not a failure: the live page already
matched the payload byte for byte.

Page targets map to sidebar titles in `PAGE_TITLES` (filename != slug !=
title — `our-story` is "Our History", `food-security` is "Food Equity"); an
unknown target falls back to the live site's own title for that slug.

### One command: `--go`

The whole ritual, minus the two things a human should keep doing (eyeball the
payload, click SAVE):

```bash
python3 scripts/squarespace.py our-team --go
```

That rebuilds the payload, commits + pushes it, **waits for the GitHub Pages
deploy to actually serve the new bytes**, puts a self-driving console snippet on
the clipboard, and opens Squarespace's Pages panel in your real Chrome. Then:

1. DevTools (`Cmd+Opt+I`) → Console → paste → Enter. The snippet picks the page
   in the sidebar, clicks **EDIT**, opens the Code Block, and pastes the payload.
2. Eyeball it, then click **SAVE**.

`--no-push` skips the commit and push (it still refuses to hand you a snippet
that would paste stale bytes).

Before any of that, `--go` checks the **live page** and stops if it is already
running this exact payload — about a second, versus a push, a ~90s deploy wait
and a whole editor session to discover the same thing when SAVE turns out
greyed. `--force` goes through the motions anyway.

### `--status`: which live pages have drifted

```bash
python3 scripts/squarespace.py --status            # every target
python3 scripts/squarespace.py our-team --status   # just one
```

Squarespace serves a Code Block verbatim, so a page's whole payload appears
character-for-character in the live HTML. That makes drift directly checkable:

| | |
|---|---|
| `current` | the live page contains this exact payload |
| `STALE` | it has an older paste of this payload — republish |
| `alternate` | another variant is the one live at that URL (`our-mission` vs `our-mission-light`) |
| `absent` | none of the payload is there; that page isn't driven by this Code Block (`blog`, `publications` and `in-the-news` are native Squarespace collection pages) |

Two things this got wrong before they were fixed, worth not re-introducing:
sweeping every page as fast as possible earns a **429** from Squarespace (the
sweep is paced and retries once), and "is some version of this payload live?"
must NOT be keyed on the generated `PASTE-READY` header — pastes predating that
header are still real pastes, and the SNAP/Medicaid timeline is one. It samples
verbatim chunks from the payload's interior instead.

Pages missing from `INTERNAL_LINK_MAP` (it only lists link targets) need an
entry in `LIVE_PATH_EXTRA`; generic injects are assumed to live at `/<dir>`.

There is no per-page URL to open instead, which is why the snippet does the
navigating: Squarespace 7.1 keeps the URL at `/config/pages` no matter which
page is selected, and `/config/<slug>` redirects to Home — both verified live.
The snippet finds the page by its **sidebar title**, which comes from
`PAGE_TITLES` in `publish_squarespace.py` (filename ≠ live slug ≠ sidebar
title), falling back to the live site's own title for the slug. A target with no
known title still works — open the page yourself first, and the snippet skips
straight to the EDIT/paste steps.

Every step it can't do it names, so you do that one by hand and re-run the
snippet; the later steps still run. The two cases worth knowing: more than one
Code Block on the page, or a sidebar title that matches more than one row
(*Media* and *Blog* each appear twice — under Main Navigation and Not Linked).

### Pasting from the browser (no manual copy/paste)

Payloads run 15–126 KB, which is miserable to hand-paste. `--snippet` skips it:

```bash
python3 scripts/squarespace.py our-team --snippet
```

That puts a one-line **console snippet** on the clipboard which pulls the
payload straight from GitHub Pages and drops it into the open Code Block
editor. Then:

1. Squarespace → the page → **EDIT** → double-click the Code Block. Its editor
   opens on the right; leave **Display Source Code OFF**.
2. DevTools (`Cmd+Opt+I`) → Console → paste the snippet → Enter. It prints
   `pasted N chars` and the **SAVE** button lights up.
3. Eyeball it, then click **SAVE** yourself.

Because the snippet reads from Pages, **push first** — `--snippet` checks the
served bytes against your local file and warns loudly if Pages is stale, so a
forgotten push can't silently re-paste the old payload.

Two things that look broken but aren't: the block renders a grey *"embedded
scripts are disabled"* placeholder while you're logged in and editing (use
Preview or a logged-out window), and pasting identical content leaves SAVE
greyed out — that means the page already matches the repo.

Mechanics, in case it ever breaks: the editor is **CodeMirror 6** and exposes
no `EditorView` on the DOM, so the snippet drives the two events CM6 itself
listens for — a synthetic `Mod-A` keydown (its keymap selects the whole
*state*; a DOM Selection can't, since CM6 only renders visible lines) then a
synthetic `paste` carrying a `DataTransfer`. Squarespace's change tracking
does observe that paste. Three things that do **not** work: a real `Cmd+V`
(automation key events don't drive a native paste), `navigator.clipboard.
readText()` (needs a focused tab plus a one-time permission grant, and hangs
the tab while the prompt is up), and `fetch` to a `localhost` server (Private
Network Access blocks it and the promise never settles).

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
| `writing-bot/` | RAG writing assistant + **the corpus** (testimony, blog posts, publications) that Content Search indexes. See its [README](writing-bot/README.md). Content Search itself moved to `Hawaii-Appleseed/staff-updates-internal` (`content-search/`) 2026-08-29 — this repo builds its data bundle but no longer serves the app. |
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
| `deploy-content-search.yml` | push touching `writing-bot/**`, or dispatch | Rebuilds the search bundle, runs the parity gate, and pushes it straight into `Hawaii-Appleseed/staff-updates-internal` (private) — nothing lands in this repo. |
| `fetch-bill-status.yml` | every 30 min (cron), or dispatch | Fetches bill RSS from capitol.hawaii.gov into `tax-fairness/data/bill-status.json`. Bill list is discovered from `data-hb`/`data-sb` attributes in the tracked pages — adding a bill is a content edit, not a workflow edit. |
| `canary.yml` | hourly, or dispatch | Watches the other scheduled workflows for a **silently dropped trigger**. Opens/updates a `canary-alert` issue and fails when one goes quiet; comments and auto-closes when it recovers. |

**None of this depends on a personal machine** — the whole chain runs in Actions.

> **Gotcha that bit us repeatedly:** a push made with the default `GITHUB_TOKEN`
> does **not** fire another workflow's `on: push` (GitHub's recursion guard).
> Every workflow above that needs a downstream job dispatches it explicitly with
> `gh workflow run`. If you add automation that must trigger a deploy, do the same.

### Why `canary.yml` exists

GitHub Actions sometimes **fails to fire a cron trigger at all** (it did on
2026-08-26, dropping a `sync-publications.yml` run and stalling
`fetch-bill-status.yml` for hours). When that happens no run object is ever
created — and GitHub's only built-in notification is "a *run* failed," so a
dropped trigger is completely silent. The symptom is stale content on the live
site with a green Actions tab.

The canary closes that gap by checking each watched workflow's **last-run age**
against a threshold, alerting via an issue plus a real job failure (which *does*
notify).

Thresholds are calibrated off **observed** gaps, not the cron's stated interval.
`fetch-bill-status.yml` says "every 30 minutes" but real-world gaps of 50–82 min
are routine on a perfectly healthy day, so a naive 35-min threshold would alert
constantly on nothing. If you add a workflow to the canary, measure its actual
cadence first and leave generous headroom.

**It can't catch its own dropped trigger** — no in-repo monitor can. That needs an
external pinger, which we've deliberately not built.

---

## Generated files — do not hand-edit

Edits to these are silently overwritten on the next run.

| Path | Regenerated by |
| --- | --- |
| `squarespace-ready/**` | `scripts/build_squarespace.py` |
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
