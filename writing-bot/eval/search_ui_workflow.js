export const meta = {
  name: 'search-ui-extensive-test',
  description: 'Extensively test the Appleseed search UI through Streamlit AppTest across 5 dimensions, verifying reported bugs adversarially',
  phases: [
    { title: 'Probe', detail: 'one agent per test dimension, drives the real app via eval/ui_probe.py' },
    { title: 'Verify', detail: 'adversarially re-run each reported bug to confirm or refute' },
  ],
}

const REPO = '/Users/devinthomas/.openclaw/workspace/appleseed-writing-bot'

const CTX = `
You are testing a LOCAL Streamlit search app for the Hawaiʻi Appleseed writing bot. It is a $0,
no-API semantic+keyword search over HA's corpus (testimony, blog posts, publications, reference docs).
The point of the app: a user types a topic/phrase/bill-number and gets ranked SOURCE PASSAGES with
links back to the original. NO AI generation is involved.

HOW TO DRIVE THE REAL APP (do not re-implement it — use the provided probe which runs the actual
search.py through Streamlit's AppTest harness):

1. cd ${REPO}
2. Write your scenarios to a UNIQUE temp file, e.g. /tmp/probe_<dimension>.json — a JSON array of objects:
     [{"query":"conveyance tax","doc_type":"publication","topic":"housing","year_min":2024,"n":8,"no_bm25":false,"no_rerank":false}, ...]
   Only "query" is required. Defaults: doc_type "(any)", topic "(any)", year_min 2016, n 10, bm25 on, rerank on.
3. Run ONE batch (loads the model once — much faster than many single runs):
     ./.venv/bin/python eval/ui_probe.py --scenarios /tmp/probe_<dimension>.json 2>/dev/null | grep '^PROBE_RESULTS:' | sed 's/^PROBE_RESULTS://'
   That prints a JSON array, one result object per scenario:
     {query, filters, ok, exceptions:[], rendered_result_count, sources_in_order:[paths],
      distinct_sources:bool, any_highlight_marks:bool, result_blocks_with_links:int,
      info_messages:[], warning_messages:[], expander_count}

HARD CONSTRAINTS on inputs (these are the real widget limits — violating them is a TEST bug, not an app bug):
- n must be an integer in [5, 25] (slider min 5, max 25). n below 5 is silently clamped.
- year_min in [2016, 2030].
- doc_type in: (any), testimony, blog, publication, reference.
- topic in: (any), labor, tax-and-budget, housing, food-equity, transportation.

CORPUS ORIENTATION (filenames are descriptive slugs — use them to judge whether a result is on-topic):
- publications/ are dated PDFs e.g. 2026-01-28_fair-tax-code-thriving-hawaii.txt, 2024-09-09_empty-homes-tax-honolulu.txt
- blog-posts/<year>/<title-slug>.txt e.g. millionaires-taxes-are-having-a-moment-..., when-disaster-strikes-who-feeds-us
- testimony/<topic>/ e.g. testimony/labor/HB2360_2026_Paid_Family_Medical_Leave.txt, testimony/housing/sample_HB2049_2026.txt
- Topics map: labor & wages, tax fairness & budget, housing & renters, food equity, transportation.

JUDGMENT: a result is "good" if the top sources are plausibly on-topic for the query (judge by the slug).
For filtered queries, EVERY returned source path must match the filter (e.g. doc_type=publication => every
path starts with publications/; topic=housing => testimony/housing/ for testimony hits — note: topic only
filters testimony docs, other doc types may still appear, which is expected since they have no topic).
Report concrete issues with severity. Mark is_bug=true ONLY for genuine app defects (exceptions, wrong
filtering, broken links, duplicate sources, missing highlight, crashes) — NOT for inherent behavior like
"vector search returns nearest neighbors even for gibberish" (note those as observations, is_bug=false).
`

const FINDINGS_SCHEMA = {
  type: 'object',
  required: ['dimension', 'scenarios_run', 'summary', 'issues'],
  properties: {
    dimension: { type: 'string' },
    scenarios_run: { type: 'integer' },
    summary: { type: 'string' },
    issues: {
      type: 'array',
      items: {
        type: 'object',
        required: ['severity', 'query', 'expected', 'observed', 'is_bug'],
        properties: {
          severity: { type: 'string', enum: ['high', 'medium', 'low', 'observation'] },
          query: { type: 'string' },
          filters: { type: 'string' },
          expected: { type: 'string' },
          observed: { type: 'string' },
          is_bug: { type: 'boolean' },
        },
      },
    },
  },
}

const VERDICT_SCHEMA = {
  type: 'object',
  required: ['dimension', 'verdicts'],
  properties: {
    dimension: { type: 'string' },
    verdicts: {
      type: 'array',
      items: {
        type: 'object',
        required: ['query', 'reproduced', 'is_real_bug', 'explanation'],
        properties: {
          query: { type: 'string' },
          reproduced: { type: 'boolean' },
          is_real_bug: { type: 'boolean' },
          explanation: { type: 'string' },
        },
      },
    },
  },
}

const DIMENSIONS = [
  {
    key: 'relevance',
    brief: `DIMENSION: Topical relevance across all 5 policy areas. Build ~12 realistic on-topic queries a
HA staffer would actually type, spread across tax fairness, housing/renters, food equity, transportation,
labor & wages (no filters, or only year_min). For each, judge whether the top 1-3 sources_in_order are
plausibly on-topic by their slugs. Flag queries where the top results look off-topic (is_bug only if
clearly broken — weak-but-related is an observation).`,
  },
  {
    key: 'exact-match',
    brief: `DIMENSION: Bill-number and exact-term retrieval (BM25's job). Build ~12 queries that are exact
tokens: bill numbers (HB2049, SB3125, HB1800, HB2360, SB2362, HB1779), program names (SNAP, ALICE, Keiki
Ride Free, conveyance tax, empty homes tax), and acronyms. Verify the matching source surfaces in the top
results. Also run a few with no_bm25=true to confirm BM25 actually helps exact matches (compare).`,
  },
  {
    key: 'filters',
    brief: `DIMENSION: Filter correctness. For each doc_type (testimony, blog, publication, reference) run
a query and verify EVERY returned source path matches that doc_type. For topic in (labor, tax-and-budget,
housing, food-equity, transportation) run a query and verify testimony hits come from testimony/<topic>/.
Test year_min boundaries (e.g. 2026 should drop older docs — check dated publication/blog paths). Test a
filter combination that yields few/zero results and confirm graceful behavior (warning shown, no exception).`,
  },
  {
    key: 'robustness',
    brief: `DIMENSION: Edge cases & robustness. Build queries: "" (empty), "   " (whitespace), a 600+ char
query, Hawaiian/ʻokina text (e.g. "keiki kūpuna ʻohana housing"), HTML/script injection
("<script>alert(1)</script> tax", "<img src=x onerror=alert(1)>"), emoji ("🏠 housing 🌺"), single char
("a"), digits only ("2049"), punctuation only ("!@#\\$%"), and a SQL-ish string. The app MUST NOT raise an
exception on ANY of these. Empty/whitespace should show an info prompt and 0 results. Injection queries must
still render with highlight marks AND must be HTML-escaped (no raw <script> executes — the snippet div uses
unsafe_allow_html, so escaping matters). Flag any exception as a HIGH bug.`,
  },
  {
    key: 'links-render',
    brief: `DIMENSION: Source-link resolution, dedup, and render integrity. Run ~10 queries spanning
publications, blogs, and testimony. Verify: (a) distinct_sources is true for every query (no duplicate
source in results); (b) result_blocks_with_links > 0 whenever publications/blogs appear (publications link
to live URL+PDF, blogs to live URL); (c) any_highlight_marks is true for non-empty queries with results;
(d) expander_count == rendered_result_count (every result has a "read full source" expander). Flag mismatches.`,
  },
]

const results = await pipeline(
  DIMENSIONS,
  // Stage 1: probe the dimension
  (d) => agent(
    `${CTX}\n\n${d.brief}\n\nRun your batch via eval/ui_probe.py, parse PROBE_RESULTS, judge every scenario, ` +
    `and return your findings. Be concrete: include the exact query and filters for each issue. ` +
    `scenarios_run = how many queries you actually ran.`,
    { label: `probe:${d.key}`, phase: 'Probe', schema: FINDINGS_SCHEMA }
  ),
  // Stage 2: adversarially verify the bugs this dimension reported
  async (findings, d) => {
    const bugs = (findings?.issues || []).filter((i) => i.is_bug)
    if (!bugs.length) {
      return { dimension: d.key, findings, verify: { verdicts: [], note: 'no is_bug issues to verify' } }
    }
    const verify = await agent(
      `${CTX}\n\nA prior tester reported these as BUGS in the search app (dimension: ${d.key}). ` +
      `Independently RE-RUN each one through eval/ui_probe.py and decide if it's a REAL app bug or a ` +
      `misjudgment (e.g. invalid input that was clamped, or inherent vector-search behavior). ` +
      `Default to is_real_bug=false unless you reproduce it and it's a genuine defect.\n\n` +
      `Reported bugs (JSON):\n${JSON.stringify(bugs, null, 2)}`,
      { label: `verify:${d.key}`, phase: 'Verify', schema: VERDICT_SCHEMA }
    )
    return { dimension: d.key, findings, verify }
  }
)

return {
  dimensions: results.filter(Boolean).map((r) => r?.dimension || '?'),
  results,
}
