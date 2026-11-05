#!/usr/bin/env python3
"""How far behind the published corpus is the deployed assistant?

The Worker's index is built when someone runs `npm run deploy`, from the reports, blog posts, testimony and bill feed in this
repo. refresh-corpus.yml adds new ones every Sunday, so the deployed assistant slowly falls behind. `record_deploy.py` writes
chatbot/deployed.json when a deploy happens; this lists what has changed in the corpus since, and exits 1 when the oldest
undeployed change is older than --max-days (the weekly corpus check opens an issue on that).

    python3 chatbot/freshness.py                 # a summary
    python3 chatbot/freshness.py --max-days 14   # exit 1 if the assistant is more than two weeks behind
    python3 chatbot/freshness.py --json
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DEPLOYED = HERE / "deployed.json"

# What the index is built from (build_index.py). writing-bot/reference is internal and never indexed, so it never counts.
CORPUS_PATHS = [
    "writing-bot/publications", "writing-bot/blog-posts", "writing-bot/testimony", "writing-bot/sources.py",
    "tax-fairness/data/bill-status.json", "chatbot/content",
]


def git(*args: str, cwd: Path = ROOT) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout


def changes_since(commit: str, cwd: Path = ROOT, paths: list[str] = CORPUS_PATHS) -> list[dict] | None:
    """Corpus files touched by commits after `commit`: [{path, date}], oldest change first. None when the commit is not in
    this checkout (a shallow clone, or history rewritten)."""
    try:
        git("cat-file", "-e", f"{commit}^{{commit}}", cwd=cwd)
        out = git("log", "--reverse", "--name-only", "--format=@@%cI", f"{commit}..HEAD", "--", *paths, cwd=cwd)
    except subprocess.CalledProcessError:
        return None
    seen: dict[str, str] = {}
    date = ""
    for line in out.splitlines():
        if line.startswith("@@"):
            date = line[2:]
        elif line.strip() and line not in seen:
            seen[line] = date
    return [{"path": p, "date": d} for p, d in seen.items()]


def report(deployed: dict | None, cwd: Path = ROOT, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    if not deployed or not deployed.get("sourceCommit"):
        return {"known": False, "message": "chatbot/deployed.json is missing: `npm run deploy` writes it (record_deploy.py)"}
    ch = changes_since(deployed["sourceCommit"], cwd)
    if ch is None:
        return {"known": False, "message": f"commit {deployed['sourceCommit']} is not in this checkout (shallow clone?); fetch full history"}
    oldest = datetime.fromisoformat(ch[0]["date"]) if ch else None
    return {"known": True, "deployedAt": deployed.get("deployedAt"), "sourceCommit": deployed["sourceCommit"], "changed": ch,
            "daysBehind": (now - oldest).days if oldest else 0}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--max-days", type=int, default=None, help="exit 1 if the oldest undeployed corpus change is older than this")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    r = report(json.loads(DEPLOYED.read_text(encoding="utf-8")) if DEPLOYED.exists() else None)
    if a.json:
        print(json.dumps(r, indent=1))
    elif not r["known"]:
        print(f"freshness unknown: {r['message']}")
    elif not r["changed"]:
        print(f"up to date: nothing in the corpus has changed since the deploy of {r['deployedAt']} (commit {r['sourceCommit']}).")
    else:
        print(f"{len(r['changed'])} corpus files changed since the deploy of {r['deployedAt']} (commit {r['sourceCommit']}); the oldest change is {r['daysBehind']} days old:")
        for c in r["changed"][:25]:
            print(f"  {c['date'][:10]}  {c['path']}")
        if len(r["changed"]) > 25:
            print(f"  ... and {len(r['changed']) - 25} more")
        print("Redeploy to pick them up (cd chatbot/worker && npm run deploy), then commit chatbot/deployed.json.")
    return 1 if a.max_days is not None and r.get("known") and r["daysBehind"] > a.max_days else 0


if __name__ == "__main__":
    raise SystemExit(main())
