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

The `brand-*` cases test `brand-skill/appleseed-brand/` (the Claude.ai org skill), which the runner adds to the throwaway plugin; run just those with `--case 'brand-*'`. "Every hex a token" is a regex over `assets/tokens.css` values, so regenerate the three `off-palette-hex.md` graders if the palette changes.

## Run

```bash
scripts/run_skill_evals.sh                           # 7 cases × 3 runs, Sonnet, ~$2
scripts/run_skill_evals.sh --case 'testimony-*' --runs 1
scripts/run_skill_evals.sh --ablation with-without   # also run without the skills, ~$2
```

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

## Writing a grader

Things `plugin eval` actually accepts (found by testing, 2026-09):
- `tool_used` takes **one** tool name. `Read|Bash` silently never matches. To
  accept any of several tools, use `type: regex`, `target: trace` on
  `"name":"(Read|Bash)","input":{…}`, as `read-positions.md` does.
- `flags` is a string (`"im"`). An unscored indicator is `arm: with-only`.
- `scaffold_script` is a path to a script, and paths must stay inside the case directory.
- Give the LLM judge the rule, not the vibe: it can't see the skill's reference
  files, so say exactly what to check and what not to.
