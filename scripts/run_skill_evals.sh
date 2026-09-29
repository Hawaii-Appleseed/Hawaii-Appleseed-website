#!/bin/bash
# Behavioural evals for the house skills (appleseed-voice / -testimony / -report).
#
# scripts/check_skills.py proves the plumbing works; this checks what Claude
# DOES with the skills: leaves unknown hearing details as placeholders, reads
# positions.md, refuses to argue against HA's stated position, writes the
# ʻokina, names report sections for their subject. Cases: evals/skills/.
#
# `claude plugin eval` wants its cases inside the plugin, and the plugin
# (.claude/) ships to every staff member, so the cases live in evals/skills/ and
# this script assembles a throwaway plugin for each run: the skills, the cases,
# and a snapshot of the corpus that each case's scaffold copies to
# ~/HawaiiAppleseed inside the eval sandbox, where a colleague's clone would be.
#
#   scripts/run_skill_evals.sh                        # all cases, 3 runs each, Sonnet
#   scripts/run_skill_evals.sh --case 'testimony-*' --runs 1
#   scripts/run_skill_evals.sh --ablation with-without # also run without the skills
#
# Extra args go to `claude plugin eval`. Costs real usage: a full run is about
# 12 agent runs plus Haiku judging. Needs Claude Code with GA `plugin eval`
# (CLAUDE_BIN overrides which binary); results land in evals/results/.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
CLAUDE_BIN="${CLAUDE_BIN:-claude}"

probe="$(cd "$(mktemp -d)" && "$CLAUDE_BIN" plugin eval . </dev/null 2>&1 || true)"
if grep -q "early access" <<<"$probe"; then
  echo "This Claude Code build predates 'plugin eval'. Run 'claude update', or set CLAUDE_BIN" >&2
  echo "to a newer binary (the desktop app bundles one under ~/Library/Application Support/Claude/claude-code/)." >&2
  exit 2
fi

WORK="$(mktemp -d)"   # in $TMPDIR; not removed, since exec replaces this shell
P="$WORK/appleseed-writing"
mkdir -p "$P/corpus/writing-bot" "$P/corpus/assets"
mkdir -p "$P/.claude-plugin"   # without a manifest the folder isn't loaded as a plugin
printf '{"name": "appleseed-writing", "description": "House voice, testimony and report skills (eval build)"}\n' > "$P/.claude-plugin/plugin.json"
rsync -a --exclude __pycache__ "$REPO/.claude/skills/" "$P/skills/"
rsync -a --exclude results --exclude README.md --exclude _scaffold.sh "$REPO/evals/skills/" "$P/evals/"
for c in "$P"/evals/*/; do install -m 755 "$REPO/evals/skills/_scaffold.sh" "$c/_scaffold.sh"; done
cp "$REPO/writing-bot/positions.md" "$REPO/writing-bot/requirements.txt" "$P/corpus/writing-bot/"
rsync -a "$REPO/writing-bot/testimony" "$REPO/writing-bot/blog-posts" "$P/corpus/writing-bot/"
cp "$REPO/assets/okina.css" "$P/corpus/assets/"

out="$REPO/evals/results/$(date +%Y-%m-%dT%H-%M-%S)"
exec "$CLAUDE_BIN" plugin eval "$P" --scaffold --allow-tools Bash \
  --ablation none --model sonnet --max-cost-usd 15 --no-publish \
  --output-dir "$out" --report "$out/report.html" "$@"
