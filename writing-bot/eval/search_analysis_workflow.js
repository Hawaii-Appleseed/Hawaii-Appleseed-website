export const meta = {
  name: 'search-ui-analysis',
  description: 'Analyze pre-computed Appleseed search-UI probe results across 4 dimensions, adversarially verify any reported bugs',
  phases: [
    { title: 'Analyze', detail: 'one agent per dimension reads its slice of the rendered results and judges' },
    { title: 'Verify', detail: 'adversarially re-check each reported bug against the data (and a targeted re-probe if needed)' },
  ],
}

const REPO = '/Users/devinthomas/.openclaw/workspace/appleseed-writing-bot'
const DATA = '/tmp/probe_corpus_results.json'

const CTX = `
You are analyzing test output from a LOCAL Streamlit search app for the Hawaiʻi Appleseed writing bot —
a $0, no-API semantic+keyword search over HA's corpus (testimony, blog posts, publications, reference).
A user types a topic/phrase/bill and gets ranked SOURCE PASSAGES linking back to the original. No AI
generation. The data was already collected by driving the REAL app (search.py) through Streamlit's
AppTest harness; you do NOT need to run the app — just read and judge.

THE DATA: ${DATA} is a JSON array, one object per query scenario:
  { query, filters:{doc_type,topic,year_min,n,bm25,rerank}, ok, exceptions:[],
    rendered_result_count, sources_in_order:[corpus-relative paths in rank order],
    distinct_sources:bool, any_highlight_marks:bool, result_blocks_with_links:int,
    info_messages:[], warning_messages:[], expander_count }

Read it with:  cd ${REPO} && ./.venv/bin/python -c "import json; [print(r) for r in json.load(open('${DATA}'))]"
(or read the file directly). Each agent: focus ONLY on the scenarios relevant to your dimension.

CORPUS ORIENTATION (paths are descriptive — judge on-topic-ness by the slug):
- publications/<YYYY-MM-DD>_<slug>.txt   (dated PDFs)
- blog-posts/<year>/<title-slug>.txt
- testimony/<topic>/<file>.txt           topics: labor, tax-and-budget, housing, food-equity, transportation
- reference/<file>.txt

WHAT CORRECT LOOKS LIKE:
- No scenario should have exceptions or error (any exception = HIGH bug).
- Empty/whitespace query → rendered_result_count 0 AND an info message (the "type a topic" prompt).
- Non-empty query with results → distinct_sources true (no duplicate source path).
- doc_type filter → EVERY path in sources_in_order is under that doc type (testimony→testimony/, blog→blog-posts/,
  publication→publications/, reference→reference/).
- topic filter → testimony hits must be under testimony/<that-topic>/. NOTE: topic only filters testimony docs;
  blog/publication/reference have no topic and may still appear — that is EXPECTED, not a bug.
- year_min filter → dated paths (publications/<date>, blog-posts/<year>) older than year_min should NOT appear;
  testimony/reference often lack a parseable year and may still appear — acceptable.
- Non-empty query with results → any_highlight_marks true; expander_count == rendered_result_count;
  result_blocks_with_links > 0 whenever publications/blogs appear (those resolve to live URLs/PDF).
- Injection queries (<script>, <img onerror>, SQL) must NOT crash and must still render (the snippet HTML-escapes).

Mark is_bug=true ONLY for genuine defects (exception/crash, wrong filtering, duplicate sources, missing
highlight on a normal query, expander/result mismatch, missing links where pubs/blogs appear). Inherent
behavior (vector search returning nearest neighbors for gibberish/emoji/punctuation; topic filter letting
non-testimony through) → is_bug=false, severity "observation".
`

const FINDINGS_SCHEMA = {
  type: 'object',
  required: ['dimension', 'scenarios_examined', 'summary', 'issues'],
  properties: {
    dimension: { type: 'string' },
    scenarios_examined: { type: 'integer' },
    summary: { type: 'string' },
    issues: {
      type: 'array',
      items: {
        type: 'object',
        required: ['severity', 'query', 'expected', 'observed', 'is_bug'],
        properties: {
          severity: { type: 'string', enum: ['high', 'medium', 'low', 'observation'] },
          query: { type: 'string' },
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
        required: ['query', 'is_real_bug', 'explanation'],
        properties: {
          query: { type: 'string' },
          is_real_bug: { type: 'boolean' },
          explanation: { type: 'string' },
        },
      },
    },
  },
}

const DIMENSIONS = [
  { key: 'relevance', brief: `DIMENSION: Topical relevance. Examine the 10 topical queries (conveyance tax, renters eviction, school meals, pedestrian safety, paid family leave, empty homes, SNAP, affordable housing/ADU, minimum wage, transit) plus the 3 extra ones (food insecurity, climate disaster, income inequality). For each, judge whether the top 1-3 sources_in_order are plausibly on-topic by their slugs. Flag clearly off-topic top results.` },
  { key: 'filters', brief: `DIMENSION: Filter correctness. Examine the doc_type scenarios (testimony/blog/publication/reference), the topic scenarios (housing/food-equity/labor/transportation/tax-and-budget), and the year_min=2026 scenarios. Verify every path obeys its doc_type filter; testimony hits obey the topic filter; year_min drops older DATED paths. Report any leak as a bug (respecting that topic only constrains testimony, and undated docs may pass year_min).` },
  { key: 'robustness', brief: `DIMENSION: Edge cases & robustness. Examine: empty "", whitespace "   ", the 400+ word long query, the ʻokina/Hawaiian query, the two injection queries (<script>, <img onerror>), emoji, single char "a", digits "2049", punctuation "!@#$%^&*()", and the SQL-ish string. ZERO of these may have exceptions/error (any → HIGH bug). Empty/whitespace must show info + 0 results. The rest must render without crashing. Confirm injection queries still produced results without error (HTML-escaping happens in the app).` },
  { key: 'links-render', brief: `DIMENSION: Dedup, links, highlight, expander integrity. Across ALL non-empty scenarios verify: distinct_sources is true; any_highlight_marks is true (non-empty w/ results); expander_count == rendered_result_count; result_blocks_with_links > 0 whenever the sources_in_order include publications/ or blog-posts/ paths. Tally any violations.` },
]

const results = await pipeline(
  DIMENSIONS,
  (d) => agent(
    `${CTX}\n\n${d.brief}\n\nRead the relevant scenarios from ${DATA}, judge each, and return findings. ` +
    `scenarios_examined = how many you actually inspected. Be concrete: quote the exact query for each issue.`,
    { label: `analyze:${d.key}`, phase: 'Analyze', schema: FINDINGS_SCHEMA }
  ),
  async (findings, d) => {
    const bugs = (findings?.issues || []).filter((i) => i.is_bug)
    if (!bugs.length) return { dimension: d.key, findings, verify: { verdicts: [], note: 'no is_bug issues' } }
    const verify = await agent(
      `${CTX}\n\nA prior analyst flagged these as BUGS (dimension ${d.key}). Independently re-check each ` +
      `against ${DATA}. If a claim is borderline you MAY run ONE targeted re-probe (cd ${REPO} && ` +
      `./.venv/bin/python eval/ui_probe.py --query "..." [--doc-type ..] [--topic ..] [--year-min ..] [--n ..] ` +
      `2>/dev/null | grep '^PROBE_RESULT:' | sed 's/^PROBE_RESULT://'). Default is_real_bug=false unless clearly a real defect.\n\n` +
      `Flagged bugs (JSON):\n${JSON.stringify(bugs, null, 2)}`,
      { label: `verify:${d.key}`, phase: 'Verify', schema: VERDICT_SCHEMA }
    )
    return { dimension: d.key, findings, verify }
  }
)

return { results: results.filter(Boolean) }
