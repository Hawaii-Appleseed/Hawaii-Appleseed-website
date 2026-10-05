# HawaiiAppleseed (website) — Claude rules

## HARD rules — NEVER violate

- **Brand palette is canonical**: Ash / Teal / Slate / Charcoal. **NEVER** use the original sage-green prototype colors (`--sage-*`, `--appleseed: #3a7811`) for new work. Migrate sage-green to brand palette when touching any page.
- **Mobile-first verification at 375px**: every layout / typography / padding change must be verified at 375px mobile width, NOT just desktop. Use ≤700px media queries with tighter padding (64–80px vs 110px), 20px page padding, smaller eyebrows, stacked CTAs.
- **Brand fonts** (per the Appleseed brand guide): **Manrope** for headings / display (H1–H4, hero titles, captions/labels — approximates Glober), **Poppins** for body text (approximates Source Sans Pro). **No other fonts** — do NOT introduce Fraunces or any serif. Italic editorial accents (taglines, pull-quotes, emphasis words) use **Poppins italic** (Manrope has no real italic on Google Fonts, so it would faux-slant — never set `font-style:italic` on Manrope). Arial is the approved fallback when custom fonts aren't available.

## Hard rules — engineering

- **Repo-relative paths only** in commits/prompts. Madison's workdir is `~/repos/HawaiiAppleseed/`.
- **No build step**: hand-rolled HTML/CSS, no SSG, no JS framework. Don't introduce one without explicit approval.
- **Static hosting**: GitHub Pages or drop-in to existing site.
- **Publishing to Squarespace goes through `--go`**, always:
  `python3 scripts/squarespace.py <target> --go`. It is the preferred and only
  route — it rebuilds, commits, pushes, waits for the Pages deploy, checks the
  live page first, and hands you a snippet that drives the editor. Do **not**
  hand-run the strip/encode/pbcopy recipe, hand-paste from `squarespace-ready/`,
  or drive the editor ad hoc; those are how stale and half-published pages
  happen. `--status` shows which live pages have drifted from the repo.
  The final **SAVE click stays human** — that click is the publish.

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

`.claude/skills/` holds the three house skills — **`appleseed-voice`**,
**`appleseed-testimony`**, **`appleseed-report`**. They load automatically when
Claude is opened in this repo, and every staff member gets them everywhere else
as the `appleseed-writing` plugin: `Hawaii-Appleseed/claude-skills` is a
marketplace that points at this folder **on the `skills-stable` branch**. There
is no second copy anywhere; this folder is the source of truth.

Skills must work from any directory on anyone's machine:

- the skill's own files via `${CLAUDE_SKILL_DIR}`, never `.claude/skills/...`
- this repo via `$W` = `${APPLESEED_WEBSITE:-$HOME/HawaiiAppleseed}`, spelled out
  as an absolute path in each command (cd and shell variables don't persist
  between Claude's tool calls)
- no `$1`/`$ARGUMENTS` in SKILL.md code blocks (Claude Code substitutes them)
- nothing from one laptop: no `/Users/...`, no personal accounts

`python scripts/check_skills.py --smoke` checks all of that and runs the bundled
scripts from outside the repo; the **Skills check** workflow runs it on every PR.

**Reference files follow the corpus on their own.** After each corpus refresh,
the *Refresh skill reference files* workflow rebuilds `citations.md` (generated,
committed to `main`) and opens one issue when `testimony-profile.md` or
`style-profile.md` has drifted 10% from the corpus size it measured. Those two
are hand-written around measured numbers, so a person re-measures them; don't
overwrite them with script output. `python scripts/refresh_skill_reference.py`
runs the same check locally.

**Behaviour, not just plumbing:** `scripts/run_skill_evals.sh` runs Claude with
the skills on the cases in `evals/skills/` (placeholders for unknown hearing
details, refusing to argue against positions.md, ʻokina, subject-named report
sections) and grades the result. It costs real usage, so run it before a release
that changes skill wording; see `evals/skills/README.md`.

**Shipping a skill change:** merge to `main` as usual, then open a PR from `main`
into `skills-stable` and merge it with a merge commit once Skills check passes.
That branch is protected — no direct pushes, the check can't be skipped — so a
commit to `main` never reaches staff on its own.

**Edit skills here, not in `~/.claude/skills/`.** A personal copy silently drifts
from what everyone else is running.

## Issue deep-dive pages — MIRROR FORMAT

The five issue deep-dive pages share a single canonical format:

- `taxes-budget.html`
- `housing.html`
- `food-security.html`
- `transportation.html`
- `wages-labor.html`

**Styles and behaviour are shared, not copied:** all five use one class prefix,
`ha-topic`, and link `assets/issue-page.css` + `assets/issue-page.js` from inside
their BEGIN/END block (`build_squarespace.py` inlines both into the payloads).
Change those files once and every page follows. Per-page settings sit on the root
element — `<section class="ha-topic" data-category="housing" data-pubs="6">`:
the category regex for the publications/news lists and how many publications to
show. The only page-specific script is the revenue pie inline in `taxes-budget.html`.

**Structural mirror requirement:** any structural change (tabs added/removed/renamed, section reorder, hero treatment, CTA placement, footer columns) made to *one* issue page must be applied to *all five* in the same commit. The pages should always share:

1. **Same nav + announcement bar** (the `px-*` chrome at top)
2. **Same hero structure**: eyebrow + h1 + lead paragraph + tabs row
3. **Same two tabs in the same order**: `Overview`, `Priorities` — panels
   `#ha-topic-panel-overview` and `#ha-topic-panel-priorities`. ("Vision" is not a
   tab; it's the `.ha-topic__vision` sub-block that opens the Overview panel.)
4. **Same sticky-tabs behavior** (`.ha-topic__stuck-tabs` reveals on scroll)
5. **Same panel skeleton** inside each tab (heading, body, supporting blocks)
6. **Same trailing sections**: Research & News → CTA → Footer
7. **Same brand palette + fonts + spacing tokens**

What *differs* between pages (and SHOULD differ):

- Per-page copy, stats, and pull-quotes
- SVG icons / charts specific to the issue

All five pages are **token-identical** — no per-page accent. The per-issue tint lives one level up, in `issues.html`'s
hub cards (`--section-bg` / `--section-accent`). If you want an issue to read as
"its" color, set it there, not in the deep-dive page.

**When in doubt about a format change:** ask "would this make sense if applied to all five pages?" If no, the change probably belongs in a *content* block (where pages diverge), not the *structure*.

## Design

Spec: [`DESIGN.md`](DESIGN.md). Tokens: [`assets/tokens.css`](assets/tokens.css), linked from every page before its `<style>`. **No raw hex/rgba in page CSS — use `var(--ha-*)`;** add missing values to `tokens.css`, never per page. Squarespace can't load the file, so `build_squarespace.py` inlines `tokens.css` into every `squarespace-ready/` payload; the hand-authored `*squarespace*` snippets keep their own inline copies. Type sizes and spacing have tokens too (`--ha-fs-*`, `--ha-space-*`); px `font-size` is out. The **Design system** workflow lints changed lines for new raw colours/px font sizes, checks WCAG contrast and chart palettes, and fails if `brand-skill/` is stale — run `python3 scripts/build_brand_skill.py` after editing `DESIGN.md` or `tokens.css` (DESIGN.md → Checks).

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
- **Embeddings are reused for unchanged chunks** (`writing-bot/tools/embed_reuse.mjs`,
  keyed by sha256 of chunk text; previous vectors come from the hub's git HEAD, not
  its working tree). Bumping model, dtype, `MAX_TOKENS` or the transformers.js pin in
  `embed_corpus.mjs` changes the cache key and forces a full re-embed automatically;
  the workflow's `force` input does too. Test: `node writing-bot/tools/embed_reuse.test.mjs`.
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

## Tax testimony theme analysis (separate repo)

Not in this repo. `Hawaii-Appleseed/Legislative-Research-Tool` (private) extracts
Hawaiʻi tax-bill testimony and tallies which arguments testifiers actually make,
per side, measured against a committed theme file — `testimony/arguments.py`,
data in `themes/{session}/{slug}.yml`. Cross-campaign output lives at
`analysis/themes.md` / `analysis/themes.json` there. It also writes
`staff-updates-internal`'s legislator/committee roster
(`data/legislators.json`, `data/committees.json`). Clone it separately; nothing
about it is linked from this repo.

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
