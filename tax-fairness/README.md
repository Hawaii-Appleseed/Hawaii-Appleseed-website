# Tax Fairness Coalition pages — notes for Claude

This file is written for an AI assistant (Claude) operating this repo on
behalf of a partner organization, not for a human reading it cold. If you
are Claude and were asked to "add a bill," "update the tracker," or "why
isn't the bill status updating," start here.

## What this directory is

Static HTML/CSS/JS for the Hawai'i Tax Fairness Coalition site
(hitaxfairness.org), deployed two ways:

- **Squarespace paste-in**: `*_squarespace.html` files are self-contained
  fragments (no `<html>`/`<head>`/`<body>`) pasted into Squarespace's code
  injection blocks. `wealth_taxes_squarespace.html` is the live wealth-taxes
  page.
- **GitHub Pages**: this whole repo is also published at
  `https://hawaii-appleseed.github.io/Hawaii-Appleseed-website/`. The
  wealth-taxes page itself isn't served from there — Squarespace is — but
  Pages is used as free, CORS-friendly hosting for the bill-status *data* and
  the tracker *script*, both of which the Squarespace-hosted page loads
  cross-origin. That's the mechanism the rest of this doc explains.

## The bill-status pipeline

Before August 2026 this page fetched RSS feeds from `capitol.hawaii.gov`
directly from the visitor's browser on every page load, routed through a
free public CORS proxy (`api.allorigins.win`) because that RSS endpoint
doesn't send CORS headers. That proxy has no SLA and is a single point of
failure for a feature on a live advocacy page — see `git log` around
August 2026 for the change that replaced it.

**Current design:**

```
.github/workflows/fetch-bill-status.yml   (runs every 30 min, GitHub Actions)
  → tax-fairness/scripts/fetch-bill-status.mjs
      - discovers which bills to track (see "Where the bill list lives" below)
      - fetches each bill's RSS from capitol.hawaii.gov directly (no proxy —
        GitHub's runners aren't subject to browser CORS rules)
      - writes tax-fairness/data/bill-status.json
  → commits bill-status.json to main
      → GitHub Pages republishes it at:
        https://hawaii-appleseed.github.io/Hawaii-Appleseed-website/tax-fairness/data/bill-status.json

tax-fairness/bill-tracker.js   (loaded by <script src> from GitHub Pages,
                                 even when the page itself is on Squarespace)
  - fetches that JSON once per page load (same-origin as far as GH Pages'
    `access-control-allow-origin: *` is concerned — no proxy needed)
  - renders the per-proposal mini trackers AND the "Bill Status Tracker"
    summary table from it
```

Freshness is bounded by the 30-minute cron interval, not by anything in the
browser. If a bill's status seems stale, check whether the workflow is
actually running (`gh run list --workflow=fetch-bill-status.yml`) before
assuming the page is broken.

## Where the bill list lives — this is the part a partner edits

**There is no separate config file listing which bills to track.** The list
is discovered by scanning `wealth_taxes_squarespace.html` itself (see
`TRACKED_PAGES` in `fetch-bill-status.mjs`) for two patterns:

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
will pick it up automatically.

**Don't hand-edit `tax-fairness/data/bill-status.json`** — it's generated.
Edits will be overwritten within 30 minutes.

## Adapting this for a different state's legislature

If a partner org outside Hawai'i wants to reuse this, two things are
Hawai'i-specific and need to change together — changing only one silently
breaks the other:

1. **`RSS_BASE_URL` in `fetch-bill-status.mjs`** — currently
   `https://www.capitol.hawaii.gov/sessions/session{year}/rss/{TYPE}{NUMBER}.xml`.
   Most state legislatures do NOT publish per-bill RSS. Check first; if none
   exists, the realistic replacement is a paid/free-tier aggregator API
   (e.g. LegiScan, Open States) rather than a direct feed, which means
   rewriting `fetchBillStatus()`, not just the URL.
2. **The status-parsing heuristics** — `getStatusBadge()`,
   `isHearingTitle()`, and the hearing-date regex in `fetch-bill-status.mjs`
   all pattern-match on the specific English phrasing Hawaii's Legislature
   uses in its RSS item titles (e.g. "passed third reading", "carried
   over"). A different legislature's feed (or an aggregator's status
   vocabulary) will use different phrasing and needs its own mapping.

Everything else — `bill-tracker.js`, the workflow, the discovery-from-HTML
approach — is not Hawai'i-specific and can be reused as-is.

## Known rough edges (not yet cleaned up)

- `wealth_taxes.html` (the non-Squarespace standalone version) still has a
  dead search box: the JS wires up `#searchInput` but no such element exists
  in that file's markup. Search silently does nothing. Not touched by this
  change.
- `bill_tracker_widget.js` and `bill_tracker_component.html` in this
  directory are older, separate copies of tracker logic that predate the
  consolidation above and are not used by `wealth_taxes_squarespace.html`
  anymore. They're still referenced by `bill_tracker_demo.html`. Treat them
  as legacy/reference, not something to keep in sync — if a page still
  loads one of them, it's using the old live-proxy-fetch approach.
- Card revenue figures, descriptions, and the revenue-comparison bar chart
  widths are still hand-typed HTML/CSS, not generated from data. Only the
  bill-status pipeline was rebuilt in this pass.

## Unrelated: `scripts/generate_departmental_reports.py`

This directory also has a standalone script, unrelated to the pages or the
bill tracker above: it generates department-style budget report HTML pages
and an index page from a CSV of budget allocations (originally from
BudgetPrimerFinal). Usage:
`python scripts/generate_departmental_reports.py path/to/budget_allocations.csv --output-dir data/output/departmental_reports`
(needs `pip install -r requirements.txt` first). Its CSV schema expectations
(`department_code`, `section`, `fund_type`, `amount`, etc.) are documented in
the script itself.

## Quick diagnostics

- Is the workflow running? `gh run list --workflow=fetch-bill-status.yml --limit 5`
- Is the JSON fresh? `curl -s https://hawaii-appleseed.github.io/Hawaii-Appleseed-website/tax-fairness/data/bill-status.json | jq .generatedAt`
- Force a refresh: `gh workflow run fetch-bill-status.yml`
- Test the discovery/fetch logic locally: `node tax-fairness/scripts/fetch-bill-status.mjs`
  (writes to your local `tax-fairness/data/bill-status.json` — don't commit
  a manual run's output over the workflow's).
