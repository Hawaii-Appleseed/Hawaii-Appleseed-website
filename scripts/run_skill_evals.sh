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
#   scripts/run_skill_evals.sh                        # all cases, 1 run each (iterating)
#   scripts/run_skill_evals.sh --changed              # only cases for skills changed vs origin/main
#   scripts/run_skill_evals.sh --changed origin/skills-stable --release   # what a release PR runs
#   scripts/run_skill_evals.sh --release              # all cases, 3 runs each
#   scripts/run_skill_evals.sh --case 'testimony-*'
#   scripts/run_skill_evals.sh --ablation with-without # also run without the skills
#
# --changed [BASE] maps files changed vs BASE (default origin/main, working tree
# included) to cases: .claude/skills/appleseed-<x>/ -> <x>-* cases, an
# evals/skills/<case>/ dir -> that case, writing-bot/ -> voice-* + testimony-*,
# DESIGN.md / assets/tokens.css -> brand-*, this script or _scaffold.sh -> all.
# --release sets 3 runs per case (default 1). Other args go to `claude plugin
# eval`. Costs real usage, ~$0.08-0.20 per agent run plus Haiku judging; capped
# at $5 per invocation (--max-cost-usd overrides). Needs Claude Code with GA `plugin eval`
# (CLAUDE_BIN overrides which binary); results land in evals/results/.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
CLAUDE_BIN="${CLAUDE_BIN:-claude}"

RUNS=1 CHANGED="" PASS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --release) RUNS=3 ;;
    --changed)
      if [ $# -gt 1 ] && [ "${2#-}" = "$2" ]; then CHANGED="$2"; shift; else CHANGED="origin/main"; fi ;;
    --changed=*) CHANGED="${1#--changed=}" ;;
    *) PASS+=("$1") ;;
  esac
  shift
done

# Which case dirs to copy into the throwaway plugin (all unless --changed).
CASES=""
for d in "$REPO"/evals/skills/*/; do CASES="$CASES $(basename "$d")"; done
if [ -n "$CHANGED" ]; then
  files="$(cd "$REPO" && { git diff --name-only "$CHANGED" --; git ls-files --others --exclude-standard; })"
  pick=""
  add() { for c in $CASES; do case "$c" in $1) pick="$pick $c" ;; esac; done; }
  while IFS= read -r p; do
    case "$p" in
      .claude/skills/appleseed-*/*) s="${p#.claude/skills/appleseed-}"; add "${s%%/*}-*" ;;
      evals/skills/_scaffold.sh|scripts/run_skill_evals.sh) add "*" ;;
      evals/skills/*/*) s="${p#evals/skills/}"; add "${s%%/*}" ;;
      writing-bot/*) add "voice-*"; add "testimony-*" ;;
      DESIGN.md|assets/tokens.css) add "brand-*" ;;
    esac
  done <<<"$files"
  CASES="$(tr ' ' '\n' <<<"$pick" | sed '/^$/d' | sort -u | tr '\n' ' ')"
  if [ -z "${CASES// /}" ]; then
    echo "No skill or eval changes vs $CHANGED; nothing to run."
    exit 0
  fi
  echo "Changed vs $CHANGED -> cases: $CASES"
fi

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
mkdir -p "$P/evals"
for c in $CASES; do rsync -a "$REPO/evals/skills/$c" "$P/evals/"; done
for c in "$P"/evals/*/; do install -m 755 "$REPO/evals/skills/_scaffold.sh" "$c/_scaffold.sh"; done
cp "$REPO/writing-bot/positions.md" "$REPO/writing-bot/requirements.txt" "$P/corpus/writing-bot/"
rsync -a "$REPO/writing-bot/testimony" "$REPO/writing-bot/blog-posts" "$P/corpus/writing-bot/"
cp "$REPO/assets/okina.css" "$P/corpus/assets/"

out="$REPO/evals/results/$(date +%Y-%m-%dT%H-%M-%S)"
# --trust-plugin: the plugin is assembled above from this repo's own skills and cases.
exec "$CLAUDE_BIN" plugin eval "$P" --scaffold --allow-tools Bash --trust-plugin \
  --ablation none --model sonnet --runs "$RUNS" --max-cost-usd 5 --no-publish \
  --output-dir "$out" --report "$out/report.html" ${PASS[@]+"${PASS[@]}"}
