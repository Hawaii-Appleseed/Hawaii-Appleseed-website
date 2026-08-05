#!/usr/bin/env python3
"""
Eval harness for the Hawaiʻi Appleseed writing bot.

Runs golden test cases against the live retrieval (+ optional generation) and
reports per-assertion pass/fail. Exits non-zero if any required assertion fails
— suitable as a CI gate.

Test cases live in eval/golden.jsonl. One JSON record per case:

{"id": "...", "prompt": "...", "mode": "testimony|blog|op-ed",
 "topic": "tax-and-budget" | null, "year_min": 2024 | null,
 "must_retrieve_any": ["substring of source path", ...],
 "must_include": ["substring that must appear in output", ...],
 "must_not_include": ["substring that must NOT appear", ...],
 "voice_rules": ["uses-okina", "has-sources-section", "refusal-or-flag"]}

Run from the repo root:
  .venv/bin/python eval/run_eval.py                          # full run
  .venv/bin/python eval/run_eval.py --retrieval-only         # skip generation
  .venv/bin/python eval/run_eval.py --case hb2049-conveyance-support
  .venv/bin/python eval/run_eval.py --show-failures          # print failing output snippets
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import bot  # noqa: E402  — repo-root import after sys.path tweak

DEFAULT_CASES = ROOT / "eval" / "golden.jsonl"
OKINA = "ʻ"


@dataclass
class CheckResult:
    name: str
    passed: bool
    reason: str = ""


@dataclass
class CaseResult:
    case_id: str
    checks: list[CheckResult] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    output: str = ""
    error: str | None = None

    @property
    def all_passed(self) -> bool:
        return self.error is None and all(c.passed for c in self.checks)


# ---------------------------------------------------------------------------
# Assertion helpers
# ---------------------------------------------------------------------------

VOICE_CHECKS = {
    "uses-okina": lambda out: (
        OKINA in out,
        "missing ʻokina (U+02BB) in output",
    ),
    "has-sources-section": lambda out: (
        bool(re.search(r"(?im)^#*\s*sources\b", out)),
        'no "Sources" section header found',
    ),
    "refusal-or-flag": lambda out: (
        bool(re.search(r"(?i)\b(cannot|no position|not covered|flag|clarif)", out)),
        "expected refusal/flag language not present",
    ),
}


def check_retrieval(case: dict, sources: list[str]) -> list[CheckResult]:
    out = []
    for needle in case.get("must_retrieve_any", []):
        hit = any(needle in s for s in sources)
        out.append(CheckResult(
            f"must_retrieve_any[{needle!r}]",
            hit,
            "" if hit else f"no retrieved source path contained {needle!r}",
        ))
    # Ranking-sensitive: the #1 result must match one of these substrings.
    rank_first = case.get("must_rank_first", [])
    if rank_first:
        top = sources[0] if sources else ""
        hit = any(needle in top for needle in rank_first)
        out.append(CheckResult(
            f"must_rank_first[{rank_first}]",
            hit,
            "" if hit else f"#1 source {top!r} matched none of {rank_first}",
        ))
    return out


def check_content(case: dict, output: str) -> list[CheckResult]:
    out = []
    for needle in case.get("must_include", []):
        present = needle.lower() in output.lower()
        out.append(CheckResult(
            f"must_include[{needle!r}]",
            present,
            "" if present else f"{needle!r} not found in output",
        ))
    for needle in case.get("must_not_include", []):
        absent = needle.lower() not in output.lower()
        out.append(CheckResult(
            f"must_not_include[{needle!r}]",
            absent,
            "" if absent else f"{needle!r} appeared in output (banned)",
        ))
    for rule in case.get("voice_rules", []):
        fn = VOICE_CHECKS.get(rule)
        if fn is None:
            out.append(CheckResult(f"voice_rule[{rule}]", False, f"unknown voice rule {rule!r}"))
            continue
        ok, reason = fn(output)
        out.append(CheckResult(f"voice_rule[{rule}]", ok, "" if ok else reason))
    return out


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def load_cases(path: Path) -> list[dict]:
    cases = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases


def run_case(case: dict, *, collection, anthropic_client, retrieval_only: bool, n_results: int,
             use_bm25: bool = True, use_rerank: bool = True) -> CaseResult:
    res = CaseResult(case["id"])
    try:
        where = bot.build_where_filter(
            doc_type=None,
            topic=case.get("topic"),
            year_min=case.get("year_min"),
        )
        hits = bot.retrieve(collection, case["prompt"], n_results, where,
                            use_bm25=use_bm25, use_rerank=use_rerank)
        res.sources = [m.get("source", "?") for _, m in hits]
        res.checks.extend(check_retrieval(case, res.sources))

        if retrieval_only:
            return res

        text, _usage = bot.generate(case["prompt"], hits, mode=case.get("mode"), client=anthropic_client)
        res.output = text
        res.checks.extend(check_content(case, text))
    except Exception as e:
        res.error = f"{type(e).__name__}: {e}"
    return res


def format_report(results: list[CaseResult], *, show_failures: bool) -> str:
    lines = []
    total_checks = 0
    passed_checks = 0
    for r in results:
        status = "ERROR" if r.error else ("PASS" if r.all_passed else "FAIL")
        lines.append(f"\n[{status}] {r.case_id}")
        if r.error:
            lines.append(f"    ERROR: {r.error}")
            continue
        for c in r.checks:
            mark = "✓" if c.passed else "✗"
            total_checks += 1
            passed_checks += int(c.passed)
            line = f"    {mark} {c.name}"
            if not c.passed:
                line += f"  — {c.reason}"
            lines.append(line)
        if show_failures and not r.all_passed and r.output:
            lines.append("    --- output (first 400 chars) ---")
            lines.append("    " + r.output[:400].replace("\n", "\n    "))
    cases_passed = sum(1 for r in results if r.all_passed)
    n = len(results)
    n_errored = sum(1 for r in results if r.error)
    pct = (100.0 * passed_checks / total_checks) if total_checks else 0.0
    case_pct = (100.0 * cases_passed / n) if n else 0.0
    lines.append("\n" + "=" * 60)
    lines.append(
        f"Cases:  {cases_passed}/{n} pass ({case_pct:.0f}%)  |  "
        f"Checks: {passed_checks}/{total_checks} pass ({pct:.0f}%)  |  "
        f"Errors: {n_errored}"
    )
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cases-file", type=Path, default=DEFAULT_CASES)
    ap.add_argument("--case", help="run only the case with this id (substring match also accepted)")
    ap.add_argument("--retrieval-only", action="store_true",
                    help="skip generation; only check must_retrieve_any (no ANTHROPIC_API_KEY needed)")
    ap.add_argument("--n-results", type=int, default=bot.DEFAULT_N_RESULTS)
    ap.add_argument("--show-failures", action="store_true",
                    help="print the first 400 chars of output for failing cases")
    ap.add_argument("--no-bm25", action="store_true", help="dense + rerank only")
    ap.add_argument("--no-rerank", action="store_true", help="dense + BM25 fused only")
    args = ap.parse_args()

    cases = load_cases(args.cases_file)
    if args.case:
        cases = [c for c in cases if c["id"] == args.case or args.case in c["id"]]
        if not cases:
            print(f"no case matched {args.case!r}", file=sys.stderr)
            sys.exit(2)

    print(f"Loading index...")
    collection = bot.index_documents(force=False)

    anthropic_client = None
    if not args.retrieval_only:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("ANTHROPIC_API_KEY not set — falling back to --retrieval-only mode.", file=sys.stderr)
            args.retrieval_only = True
        else:
            import anthropic
            anthropic_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    print(f"Running {len(cases)} case(s) ({'retrieval-only' if args.retrieval_only else 'full'})...")
    results = []
    for case in cases:
        print(f"  · {case['id']}", flush=True)
        results.append(run_case(
            case,
            collection=collection,
            anthropic_client=anthropic_client,
            retrieval_only=args.retrieval_only,
            n_results=args.n_results,
            use_bm25=not args.no_bm25,
            use_rerank=not args.no_rerank,
        ))

    print(format_report(results, show_failures=args.show_failures))
    sys.exit(0 if all(r.all_passed for r in results) else 1)


if __name__ == "__main__":
    main()
