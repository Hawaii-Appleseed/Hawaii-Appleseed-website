# Behavioural evals for the house skills

`scripts/check_skills.py` proves the skills' plumbing works. These check what
Claude actually **does** with them, on the failure modes that would embarrass
us in public:

| Case | Asks Claude to… | Graded on |
|---|---|---|
| `testimony-hearing-placeholders` | draft support testimony with no hearing notice | committee/date/time left as `[PLACEHOLDERS]`, nothing invented (LLM judge), positions.md consulted, every figure footnoted or `CITATION NEEDED`, skill triggers from a plain request |
| `testimony-conflicting-position` | write testimony *opposing* universal school meals, which HA supports | flags the conflict and asks instead of drafting (LLM judge), positions.md consulted |
| `voice-house-style` | write a blog opening, prompt spelled "Hawaii" | ʻokina (no bare or fake-apostrophe Hawaii), no `!`, no `%`, house voice (LLM judge), positions.md consulted |
| `report-subject-sections` | outline a GET report | no generic Background/Analysis/Findings, bookends present (LLM judge) |
| `brand-flyer` | make an HTML flyer for an EITC workshop (never says "brand") | Deep Teal accent, Charcoal text, every hex a token, Manrope + Poppins, no serif, overall look (LLM judge), brand skill triggers |
| `brand-chart` | write matplotlib code for a 4-series ALICE chart | first four categorical chart colours in order, no off-palette hex, brand font, source note, colour-blind usable (LLM judge) |
| `brand-slide` | write python-pptx code for a 3-slide board deck | starts from `templates/appleseed-slides.pptx`, no off-palette hex, slide rules incl. ʻokina (LLM judge) |

The `brand-*` cases test `.claude/skills/appleseed-brand/`, shipped with the other house skills (and to Claude.ai as `brand-skill/appleseed-brand.zip`); run just those with `--case 'brand-*'`. "Every hex a token" is a regex over `assets/tokens.css` values, so regenerate the three `off-palette-hex.md` graders if the palette changes.

## Run

```bash
scripts/run_skill_evals.sh --changed                 # only cases for what you changed vs origin/main, 1 run each
scripts/run_skill_evals.sh --case 'testimony-*'      # one group, 1 run each
scripts/run_skill_evals.sh --release                 # all 7 cases × 3 runs, ~$2–3
scripts/run_skill_evals.sh --ablation with-without   # also run without the skills
```

Iterate with 1 run; use `--release` (3 runs) before shipping. Each agent run
costs about $0.08–0.20 (flyer is the dearest), and a run is capped at $5 total
(`--max-cost-usd` overrides). A release PR into `skills-stable` runs
`--changed origin/skills-stable --release` in CI when the API key secret is set.

Needs a Claude Code build with `plugin eval` out of early access (`claude update`,
or `CLAUDE_BIN=` pointing at a newer binary). It uses your Claude login and
counts against your usage. Results and an HTML report land in `evals/results/`
(gitignored).

The runner assembles a throwaway plugin (the skills, these cases, and a corpus
snapshot) because `plugin eval` wants cases inside the plugin, and `.claude/`
ships to every staff member. `_scaffold.sh` copies the corpus to
`~/HawaiiAppleseed` inside the eval sandbox, where a colleague's clone would be.

## Baseline — 2026-09-29, Sonnet, 3 runs per arm

| Case | with skills | without |
|---|---|---|
| report-subject-sections | 1.00 | 0.33 |
| testimony-conflicting-position | 0.89 | 0.00 |
| testimony-hearing-placeholders | 1.00 | 0.73 |
| voice-house-style | 0.83 | 0.61 |

Fixed since (2026-09-29, 3 runs each, same graders, before → after):
- **appleseed-voice skipped a full read of positions.md** (it grepped for the
  topic, or skipped the file): 0/3 → 3/3 after Step 1 was made explicit
  (Read tool, whole file). voice-house-style 0.83 → 1.00.
- **Footnote provenance.** The testimony skill now forbids citing from memory
  and checks each footnote against `citations.md` before delivering.
  Provenance stated in the handoff went from 2/3 to 3/3; testimony-hearing-placeholders
  went from 0.96 to 1.00. All 12 footnotes across the 3 runs are in the library.
  (An earlier note here called an "ALICE in the Crosscurrents" footnote
  fabricated. It isn't: `citations.md` carries it as "Crosscur**e**nts", a typo
  from HA's original footnote, which Claude silently corrected. When checking
  provenance by hand, match loosely.)

## Brand baseline — 2026-10-11, Sonnet, 3 runs, with skills only

| Case | first run | after fixes |
|---|---|---|
| brand-chart | 0.89 | 1.00 |
| brand-flyer | 1.00 | 0.96 |
| brand-slide | 0.93 | 0.87 |

What changed between the two columns:
- **Charts drew years as separate lines in the light sequential greens** (faint
  on white, hard to tell apart). The skill now says any per-series line/bar
  uses the categorical order, sequential is for shading only.
- **Slide scripts guessed layout names** and one hard-coded the eval sandbox's
  template path. The skill now lists the template's layouts by index and says
  to copy the template or take its path as an argument.
- **Graders:** `palette-in-order` also accepts the four colours as named
  constants in order (it only matched hex literals); `on-brand-slides` no
  longer asks for colours/fonts restated in code when the script builds on the
  template's layouts, which is what the skill tells it to do.

The remaining flyer/slide misses are the Haiku judge splitting on output that
follows every stated rule (read the evidence before "fixing" the skill for them).

## Writing a grader

Things `plugin eval` actually accepts (found by testing, 2026-09):
- `tool_used` takes **one** tool name. `Read|Bash` silently never matches. To
  accept any of several tools, use `type: regex`, `target: trace` on
  `"name":"(Read|Bash)","input":{…}`, as `read-positions.md` does.
- `flags` is a string (`"im"`). An unscored indicator is `arm: with-only`.
- `scaffold_script` is a path to a script, and paths must stay inside the case directory.
- Prefer regex graders whenever the rule is checkable in the text (a palette,
  a layout index, the ʻokina, a banned font). They're free and give the same
  verdict every time; the Haiku judge splits on identical-looking output, and
  chasing its votes cost more than the runs themselves (2026-10-11). Keep an
  LLM judge for what a pattern can't see (overall look, argument, tone).
- Give the LLM judge the rule, not the vibe: it can't see the skill's reference
  files, so say exactly what to check and what not to.
