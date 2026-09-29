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

## Run

```bash
scripts/run_skill_evals.sh                           # 4 cases × 3 runs, Sonnet, ~$1
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

Open issues this surfaced:
- **appleseed-voice skipped positions.md in 2 of 3 runs**, despite Step 1 saying
  to read it on every use.
- In one earlier run, testimony cited a source ("ALICE in the Crosscurrents",
  United for ALICE, 2024) that is in neither `citations.md` nor the corpus. The
  skill's sourcing order forbids that, and no grader can see the citation
  library, so check footnotes by hand.

## Writing a grader

Things `plugin eval` actually accepts (found by testing, 2026-09):
- `tool_used` takes **one** tool name. `Read|Bash` silently never matches. To
  accept any of several tools, use `type: regex`, `target: trace` on
  `"name":"(Read|Bash)","input":{…}`, as `read-positions.md` does.
- `flags` is a string (`"im"`). An unscored indicator is `arm: with-only`.
- `scaffold_script` is a path to a script, and paths must stay inside the case directory.
- Give the LLM judge the rule, not the vibe: it can't see the skill's reference
  files, so say exactly what to check and what not to.
