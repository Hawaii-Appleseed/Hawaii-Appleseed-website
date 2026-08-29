# HawaiiAppleseed (website) — Claude rules

## HARD rules — NEVER violate

- **Brand palette is canonical**: Ash / Teal / Slate / Charcoal. **NEVER** use the original sage-green prototype colors (`--sage-*`, `--appleseed: #3a7811`) for new work. Migrate sage-green to brand palette when touching any page.
- **Mobile-first verification at 375px**: every layout / typography / padding change must be verified at 375px mobile width, NOT just desktop. Use ≤700px media queries with tighter padding (64–80px vs 110px), 20px page padding, smaller eyebrows, stacked CTAs.
- **Brand fonts** (per the Appleseed brand guide): **Manrope** for headings / display (H1–H4, hero titles, captions/labels — approximates Glober), **Poppins** for body text (approximates Source Sans Pro). **No other fonts** — do NOT introduce Fraunces or any serif. Italic editorial accents (taglines, pull-quotes, emphasis words) use **Poppins italic** (Manrope has no real italic on Google Fonts, so it would faux-slant — never set `font-style:italic` on Manrope). Arial is the approved fallback when custom fonts aren't available.

## Hard rules — engineering

- **Repo-relative paths only** in commits/prompts. Madison's workdir is `~/repos/HawaiiAppleseed/`.
- **No build step**: hand-rolled HTML/CSS, no SSG, no JS framework. Don't introduce one without explicit approval.
- **Static hosting**: GitHub Pages or drop-in to existing site.

## Orientation

**Read [`README.md`](README.md) first** — it maps the two deploy models
(Squarespace paste-in vs. GitHub Pages sub-sites), every root page to its live
URL, what each directory is, and which files are generated.

Things that file will tell you and are easy to get wrong:

- Filename ≠ live slug for several pages (`our-story.html` → `/our-history`,
  `food-security.html` → `/food-equity`). `INTERNAL_LINK_MAP` in
  `scripts/build_squarespace.py` is the source of truth.
- Paste into Squarespace from `squarespace-ready/`, **never** the raw root file.
- The legacy sage-green `<style>` block is **gone** — `index.html` was migrated
  to the brand palette in `63ef507` / `422c211`. `--sage-*` and `#3a7811` now
  appear nowhere in the repo except the prohibition above. Don't "migrate" it
  again; every hex in `index.html` is already a brand token value.

## Skills

`.claude/skills/` ships two project skills. They load automatically for anyone who
opens this repo in Claude Code — no install step, no copying into `~/.claude/`:

- **`appleseed-voice`** — house voice for anything going out under HA's name
  (blog posts, testimony, op-eds, web copy). Reads `writing-bot/positions.md`
  fresh on every use; that file is authoritative and policy-staff-maintained.
- **`appleseed-report`** — house structure and brand system for reports and
  briefs (cover, exec summary, recommendations, endnotes, figures).

Paths inside them are **repo-root-relative**, so launch Claude from the repo
root. Everything they read (`positions.md`, the 112-post corpus, the brand
tokens) lives in this repo, so a fresh clone works with no setup. The single
external dependency is `appleseed-report`'s primer-editor output step, which
needs `Hawaii-Appleseed/primer-editor` cloned separately — the skill gives the
clone command inline.

**Edit them here, not in `~/.claude/skills/`.** A personal copy silently drifts
from what everyone else is running.

## Issue deep-dive pages — MIRROR FORMAT

The five issue deep-dive pages share a single canonical format:

- `taxes-budget.html`
- `housing.html`
- `food-security.html`
- `transportation.html`
- `wages-labor.html`

**Structural mirror requirement:** any structural change (tabs added/removed/renamed, section reorder, hero treatment, CTA placement, footer columns) made to *one* issue page must be applied to *all five* in the same commit. The pages should always share:

1. **Same nav + announcement bar** (the `px-*` chrome at top)
2. **Same hero structure**: eyebrow + h1 + lead paragraph + tabs row
3. **Same two tabs in the same order**: `Overview`, `Priorities` — panels
   `#ha-{ns}-panel-overview` and `#ha-{ns}-panel-priorities`. ("Vision" is not a
   tab; it's the `.ha-{ns}__vision` sub-block that opens the Overview panel.)
4. **Same sticky-tabs behavior** (`.ha-{slug}__stuck-tabs` reveals on scroll)
5. **Same panel skeleton** inside each tab (heading, body, supporting blocks)
6. **Same trailing sections**: Research & News → CTA → Footer
7. **Same brand palette + fonts + spacing tokens**

What *differs* between pages (and SHOULD differ):

- The CSS namespace prefix (`.ha-tax__*` → `.ha-housing__*` etc.)
- Per-page copy, stats, and pull-quotes
- SVG icons / charts specific to the issue

All five pages are **token-identical** — same eight `--ha-*` custom properties,
no per-page accent. The per-issue tint lives one level up, in `issues.html`'s
hub cards (`--section-bg` / `--section-accent`). If you want an issue to read as
"its" color, set it there, not in the deep-dive page.

**When in doubt about a format change:** ask "would this make sense if applied to all five pages?" If no, the change probably belongs in a *content* block (where pages diverge), not the *structure*.

## When touching layout / type / padding

1. Open the page in a browser at **375px wide** (Chrome DevTools device emulation → iPhone SE or custom 375).
2. Verify nav, headlines, CTAs, body text all render readably WITHOUT horizontal scroll.
3. Only after that's good, check desktop ≥1024px.

## Companion docs (in vault)

- `~/.openclaw/workspace/projects/HawaiiAppleseed.md` — full project context.
- `~/.openclaw/workspace/tasks/HawaiiAppleseed.md` — active worklist.
- The RAG writing bot was **merged into this repo** on 2026-08-05 (`writing-bot/`
  + `content-search/`). The standalone `appleseed-writing-bot` repo is superseded
  and now private — don't work there. `content-search/` moved again 2026-08-29
  to `Hawaii-Appleseed/staff-updates-internal` (private, Cloudflare Access) —
  see below.

## Content Search / writing-bot subsystem

`writing-bot/` (in **this** repo) holds the RAG engine and the corpus.
`content-search/`, the static browser app that indexes it, lives in
**`Hawaii-Appleseed/staff-updates-internal`** — it was never linked from the
public site, so it moved behind that repo's access gate 2026-08-29 rather than
staying on public GitHub Pages. `deploy-content-search.yml` in this repo still
does the actual build (Chroma index, embeddings, parity tests) and pushes the
result there; nothing content-search-related is committed in this repo anymore
except the engine. Full detail in `content-search/README.md` in the hub repo —
the rules that will bite you:

- **The hub's `content-search/data/`, `api.json`, and `test/fixtures.json` are
  committed but CI-generated.** Never hand-edit them there.
  `deploy-content-search.yml` (in *this* repo) rebuilds them from
  `writing-bot/` and pushes the result — CI output is canonical (local builds
  differ byte-wise). `index.html`/`css/`/`README.md` in the hub, by contrast,
  ARE hand-maintained there (hub nav integration) — this workflow never
  touches them.
- **Model dtype must stay in lockstep** between the hub's `content-search/js/worker.js`
  (`DTYPE`) and this repo's `writing-bot/tools/embed_corpus.mjs`. Query and
  corpus embeddings must live in the same space — changing one without the
  other silently corrupts relevance rather than erroring. This is now a
  cross-repo convention with no automated check — grep both by hand when
  touching either.
- **The parity gate is model-free.** `content-search/test/run_all.mjs` (in the
  hub repo, run from *this* repo's checkout via
  `deploy-content-search.yml`'s symlink trick) checks the BM25/tokenizer/
  grouping core against Python fixtures. It will happily pass through a bad
  model change — validate those separately
  (`writing-bot/tools/probe_quality.mjs`).
- **`content-search/js/app.js` contains a byte that makes `grep` treat it as
  binary.** Use `grep -a`.
- Corpus scraping is idempotent via **two** mechanisms: the output filename and
  `writing-bot/content-monitor/blog-urls.json`. The URL manifest short-circuits
  *before* fetching, so to force a re-ingest you must remove both.

## Pol.is poll data (tax-fairness)

`tax-fairness/scripts/fetch-polis-report.py` pulls a Pol.is member poll
(topic, every idea's agree/disagree/pass tally, opinion-group clustering)
into one JSON file — stdlib-only, no auth, reverse-engineered from the four
public API calls a `pol.is/report/<id>` page makes itself. Its companion,
`polis-sync-primer.py`, refreshes a primer-editor report's `content.md` from
that JSON via a per-project map file, touching only the vote-derived slots
the map names — never prose. `--check` reports drift without writing.
`tax-fairness/README.md`'s two "Unrelated:" sections have full usage; a real
worked pull lives at `tax-fairness/data/polis/tfc-2027-priorities.json`,
feeding `primer-editor/projects/tfc-2027-priorities` (a separate repo — its
own `polis-map.json` is the worked example for a map file). Pol.is only
knows who voted, never who was invited — that number stays hand-entered
wherever a report shows it.

## Automation rules

- **`GITHUB_TOKEN` pushes do not trigger other workflows** (GitHub's recursion
  guard). Any workflow that must kick off a downstream one dispatches it
  explicitly via `gh workflow run` and needs `actions: write`. This has caused
  silent no-deploy bugs twice — follow the existing pattern.
- **Never `gh run rerun` a failed Pages deploy** — it errors on a duplicate
  artifact. Start a fresh run: `gh workflow run deploy.yml --ref main`.
- Workflows that regenerate data guard on *real content change*, not just a
  dirty tree — several generators restamp a timestamp on every run, so a naive
  `git diff --quiet` is never quiet and would deploy on every tick.
- The whole refresh chain runs in **GitHub Actions**; no personal machine is in
  the loop. Don't reintroduce a laptop cron/launchd dependency.

## Verifying changes

- Site pages: check at **375px first** (see the mobile rule above), then desktop.
- Content Search: it's a real app, but it now lives in `staff-updates-internal`
  — run and exercise it from that repo (`python3 -m http.server 8532 --directory
  content-search`), not this one. Changes here only affect the corpus/build
  engine (`writing-bot/`), verified via `deploy-content-search.yml`'s parity
  gate, not by loading a page.
- Don't trust a screenshot of an embedded/injected page to prove a fix; several
  of these render blank in screenshots. Verify via DOM evaluation.
