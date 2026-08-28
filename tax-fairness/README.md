# Tax Fairness Coalition pages — notes for Claude

This file is written for an AI assistant (Claude) operating this repo on
behalf of a partner organization, not for a human reading it cold. If you
are Claude and were handed this code to adapt for a different state, start
with the checklist immediately below. If you're just here to add a bill or
debug the tracker, skip to "Where the bill list lives."

## Adapting this for a different state's legislature — do this, in order

1. **Read `tax-fairness/scripts/status-rules.mjs` first.** Its header
   explains what it is. Everything in that file is Hawaii-specific; nothing
   else described below should need to change to make the *mechanism* work
   for a new state.
2. **Confirm your state's legislature publishes per-bill machine-readable
   status** (RSS, JSON API, anything fetchable). Most don't. If none exists,
   the realistic path is a paid/free-tier aggregator (LegiScan, Open States)
   instead — that means rewriting `fetchBillStatus()` in
   `fetch-bill-status.mjs` to call that API, not just changing a URL. Don't
   proceed past this step assuming RSS exists; verify it first (fetch one
   known bill's feed URL directly and confirm you get real content back).
3. **Edit exactly one line**: `RSS_URL_TEMPLATE` near the top of
   `fetch-bill-status.mjs`, marked with a comment banner. It's a function
   `({year, type, number}) => url`.
4. **Rewrite `status-rules.mjs`** to match your state's phrasing:
   `getStatusBadge()` (what phrases mean "passed," "deferred," etc.),
   `isHearingTitle()`, `toDescription()` (strips your legislature's own
   filler text, e.g. Hawaii's "with Representative(s) X voting no"),
   `extractHearingDate()` (only needs changing if hearing dates aren't in
   `M/D/YY` format). Test in isolation — these are pure functions, no
   network needed: `node -e "import('./status-rules.mjs').then(m => console.log(m.getStatusBadge('Passed Third Reading')))"`
5. **`bill-tracker.js` needs no edits.** It locates its own data file
   relative to wherever it was loaded from (see the `SELF_URL` comment near
   the top) — this is true regardless of what domain hosts the fork.
6. **Verify locally before touching the workflow**, in this order:
   - `node tax-fairness/scripts/fetch-bill-status.mjs` — writes a real
     `tax-fairness/data/bill-status.json` from your state's live feeds.
     Check it by eye first.
   - `python3 -m http.server 8000` from the repo root, then open
     `http://localhost:8000/tax-fairness/<your-page>.html` in a browser.
     Because `bill-tracker.js` self-locates, this works with **no file
     edits or query params** — it'll load the JSON you just generated from
     the same local server. Check the browser console for errors and
     confirm at least one tracker renders real status text, not "Error" or
     "N/A" for every bill.
7. **Only after step 6 passes**, point `.github/workflows/fetch-bill-status.yml`
   at your fork (repo checkout is automatic via `actions/checkout`; nothing
   else in that file is Hawaii-specific) and confirm GitHub Pages is
   enabled so the JSON it commits becomes fetchable.

If you get stuck, don't guess — the "Quick diagnostics" section at the
bottom of this file has copy-pasteable commands for each stage of the
pipeline, and will tell you which stage is actually broken.

## What this directory is

Static HTML/CSS/JS for the Hawaiʻi Tax Fairness Coalition site
(hitaxfairness.org), deployed two ways:

- **Squarespace paste-in**: `*_squarespace.html` files are self-contained
  fragments (no `<html>`/`<head>`/`<body>`) pasted into Squarespace's code
  injection blocks. `wealth_taxes_squarespace.html` is the live wealth-taxes
  page.
- **GitHub Pages**: this whole repo is also published at
  `https://hawaii-appleseed.github.io/Hawaii-Appleseed-website/`. The
  wealth-taxes page itself isn't served from there — Squarespace is — but
  Pages is used as free, CORS-friendly hosting for the bill-status *data*
  that page loads cross-origin. That's the mechanism the next section
  explains.

## The bill-status pipeline

Before August 2026 this page fetched RSS feeds from `capitol.hawaii.gov`
directly from the visitor's browser on every page load, routed through a
free public CORS proxy (`api.allorigins.win`) because that RSS endpoint
doesn't send CORS headers. That proxy had no SLA and was a single point of
failure for a feature on a live advocacy page — see `git log` around
August 2026 for the change that replaced it.

**Current design:**

```
.github/workflows/fetch-bill-status.yml   (runs every 30 min, GitHub Actions)
  → tax-fairness/scripts/fetch-bill-status.mjs
      - discovers which bills to track (see "Where the bill list lives")
      - fetches each bill's status (RSS_URL_TEMPLATE) directly — GitHub's
        runners aren't subject to browser CORS rules, so no proxy needed
      - interprets each update via status-rules.mjs
      - writes tax-fairness/data/bill-status.json — but ONLY if the content
        actually changed (see "Why the workflow doesn't spam commits" below)
  → commits bill-status.json to main
      → GitHub Pages republishes it at:
        https://hawaii-appleseed.github.io/Hawaii-Appleseed-website/tax-fairness/data/bill-status.json

tax-fairness/bill-tracker.js   (loaded by <script src>, from GitHub Pages,
                                 even when the embedding page is on Squarespace)
  - locates that JSON relative to its OWN <script src> (document.currentScript),
    not the embedding page's origin — see the SELF_URL comment in the file.
    This means forking to a different GitHub Pages project needs zero edits
    here, and testing locally needs no file edits either (see the runbook
    above).
  - renders the per-proposal mini trackers AND the "Bill Status Tracker"
    summary table from it
```

Freshness is bounded by the 30-minute cron interval, not by anything in the
browser. If a bill's status seems stale, check whether the workflow is
actually running (`gh run list --workflow=fetch-bill-status.yml`) before
assuming the page is broken.

### Why the workflow doesn't spam commits

`fetch-bill-status.mjs` reads the *existing* `bill-status.json`, computes
the new content, and compares them **excluding the `generatedAt` field**
before deciding whether to write anything. This matters: an earlier version
stamped a fresh timestamp on every run unconditionally, which meant the
file differed on every single run even when zero bills changed status, and
the workflow's git-diff-based "did anything change" check committed every
~30 minutes forever. If you're touching this script, preserve that
comparison — don't go back to an unconditional write.

## Where the bill list lives — this is the part a partner edits day-to-day

**There is no separate config file listing which bills to track.** The list
is discovered by scanning the tracked HTML page(s) — see `TRACKED_PAGES` in
`fetch-bill-status.mjs` — for two patterns:

1. `<div class="tfc-bill-tracker" data-tracker-id="..." data-issue-area="..."
   data-hb="..." data-sb="..." data-year="...">` — one per proposal card.
   This is what renders the little "Legislation" tracker under each card.
2. Client-side "policy toggle" JS objects with `hbNumbers: '...'` /
   `sbNumbers: '...'` pairs (e.g. `capGainsPolicies`,
   `millionairesTaxPolicies` — used when a card lets the user pick between
   two versions of a bill). These are picked up by a separate regex pass
   (`discoverPolicyToggleBills`) since they aren't in a tracker div.

**To add a new bill to an existing proposal card:** add its number to the
`data-hb` or `data-sb` attribute (comma-separated for multiple bills).

**To add a whole new proposal card:** copy an existing `.tfc-card-wrapper`
block (card + `.tfc-bill-tracker` div + optional sample-testimony block),
give the tracker div a unique `data-tracker-id` and a `data-issue-area`
label, and set `data-hb`/`data-sb`/`data-year`. Nothing else needs to change
— the next workflow run (or a manual `gh workflow run fetch-bill-status.yml`)
picks it up automatically.

**To track a whole new page**, add its repo-relative path to
`TRACKED_PAGES` in `fetch-bill-status.mjs`.

**Don't hand-edit `tax-fairness/data/bill-status.json`** — it's generated.
Edits will be overwritten within 30 minutes.

## Known rough edges (not yet cleaned up)

- `wealth_taxes.html` (the non-Squarespace standalone version) still has a
  dead search box: the JS wires up `#searchInput` but no such element exists
  in that file's markup. Search silently does nothing.
- Card revenue figures, descriptions, and the revenue-comparison bar chart
  widths are still hand-typed HTML/CSS, not generated from data. Only the
  bill-status pipeline has been rebuilt to be config-free.

## Unrelated: `scripts/generate_departmental_reports.py`

This directory also has a standalone script, unrelated to the pages or the
bill tracker above: it generates department-style budget report HTML pages
and an index page from a CSV of budget allocations (originally from
BudgetPrimerFinal). Usage:
`python scripts/generate_departmental_reports.py path/to/budget_allocations.csv --output-dir data/output/departmental_reports`
(needs `pip install -r requirements.txt` first). Its CSV schema expectations
(`department_code`, `section`, `fund_type`, `amount`, etc.) are documented in
the script itself.

## Unrelated: `scripts/fetch-polis-report.py`

Also standalone, also unrelated to the bill tracker: pulls a Pol.is member
poll (topic, every idea's agree/disagree/pass tally, and the opinion-group
clustering) into one JSON file, stdlib-only, no auth. Reverse-engineered from
the four public API calls a `pol.is/report/<id>` page itself makes — see the
script's own header for the full endpoint list and what it deliberately
leaves out (how many people were *invited* to vote isn't knowable from
Pol.is; neither is any editorial read of the numbers). Usage:
`python3 scripts/fetch-polis-report.py <report-id-or-url> -o data/polis/<name>.json`.
`data/polis/tfc-2027-priorities.json` is a real pull (the coalition's 2027
priorities poll, also written up at
`primer-editor/projects/tfc-2027-priorities`) kept as a worked example —
regenerate it the same way if that poll's votes change.

Its companion, `scripts/polis-sync-primer.py`, takes that JSON and gets the
vote-derived numbers into a primer-editor report's `content.md` — the format
docsync actually consumes — touching only the slots a per-project map file
names (never prose, never anything editorial). Usage:
`python3 scripts/polis-sync-primer.py POLIS_JSON CONTENT_MD MAP_JSON --check`
to see drift without writing anything, then drop `--check` to apply. The
`--check` run against `primer-editor/projects/tfc-2027-priorities` is what
caught the 102-vs-101 discrepancy above — every other mapped slot already
matched. `primer-editor/projects/tfc-2027-priorities/polis-map.json` is the
worked example for a map file, including what it deliberately doesn't cover.

## Quick diagnostics

Work through these in order — each one isolates a different stage of the
pipeline, so stop at the first one that shows a problem:

1. **Is bill discovery finding the right bills?**
   `node tax-fairness/scripts/fetch-bill-status.mjs` — prints each bill it
   fetches. Wrong count or missing bills means `discoverTrackers`/
   `discoverPolicyToggleBills` in `fetch-bill-status.mjs` isn't matching
   your HTML (e.g. after a markup restructure).
2. **Is the status-interpretation correct for what you got back?** Open the
   `tax-fairness/data/bill-status.json` that step 1 just wrote and read a
   `bills.<BILL>.updates[0]` entry by eye. Wrong badge/description means
   `status-rules.mjs` needs adjusting for your legislature's phrasing.
3. **Does it render?** `python3 -m http.server 8000` from repo root, open
   `http://localhost:8000/tax-fairness/wealth_taxes_squarespace.html`,
   check the browser console. No file edits needed — see the runbook above
   for why.
4. **Is the scheduled workflow actually running in CI?**
   `gh run list --workflow=fetch-bill-status.yml --limit 5`
5. **Is the published JSON fresh?**
   `curl -s https://hawaii-appleseed.github.io/Hawaii-Appleseed-website/tax-fairness/data/bill-status.json | jq .generatedAt`
6. **Force a refresh**: `gh workflow run fetch-bill-status.yml`
