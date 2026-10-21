#!/usr/bin/env bash
# Everything that can notice the corpus moving under the assistant, in one go. Writes a markdown report ($REPORT, default
# corpus-check.md) and exits 1 if any check failed. The weekly workflow (chatbot-corpus.yml) runs it and opens an issue; run it by
# hand before a deploy. It deploys nothing.
cd "$(git rev-parse --show-toplevel)" || exit 2
REPORT="${REPORT:-corpus-check.md}"
: > "$REPORT"
fail=0
step() {
  local title="$1"; shift
  local out rc
  out=$("$@" 2>&1); rc=$?
  { echo "### $([ $rc -eq 0 ] && echo ok || echo FAILED): $title"; echo; echo '```'; printf '%s\n' "$out" | tail -n "${TAIL:-30}"; echo '```'; echo; } >> "$REPORT"
  [ $rc -eq 0 ] || fail=1
  echo "$([ $rc -eq 0 ] && echo ok || echo FAILED): $title"
}
step "Build the index (every published report needs a topic in content/topics.json; every figure in a position needs a source)" python3 chatbot/build_index.py --strict
step "Figures in the positions against the published corpus" python3 chatbot/check_figures.py --strict
step "Index builder, figures, graphics and sign-off tests" python3 -m unittest discover -s chatbot/tests
step "Worker tests" bash -c 'cd chatbot/worker && npm test'
step "Offline eval (legal gate, retrieval, ready-made answers, stances)" node chatbot/eval/run_eval.mjs --offline
step "Links the assistant can show" python3 chatbot/check_links.py
step "How far behind the deployed assistant is (redeploy if more than ${MAX_DAYS:-14} days)" python3 chatbot/freshness.py --max-days "${MAX_DAYS:-14}"
exit $fail
