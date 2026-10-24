#!/usr/bin/env python3
"""Record what a Worker deploy shipped in chatbot/deployed.json (run by `npm run deploy` after it succeeds).

    {deployedAt, builtAt, sourceCommit, uncommittedContent, public}

freshness.py compares the corpus against `sourceCommit`. `uncommittedContent` says the index was built from files that were
not committed, in which case the commit is only an approximation and freshness errs toward "behind". Commit the file with the
deploy so the weekly corpus check can see it.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import freshness  # noqa: E402


def main() -> int:
    idx = json.loads((HERE / "worker" / "src" / "index.json").read_text(encoding="utf-8"))
    commit = freshness.git("rev-parse", "--short", "HEAD").strip()
    dirty = bool(freshness.git("status", "--porcelain", "--", *freshness.CORPUS_PATHS).strip())
    rec = {"deployedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "builtAt": idx.get("built"),
           "sourceCommit": commit, "uncommittedContent": dirty, "public": bool(idx.get("public"))}
    freshness.DEPLOYED.write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8")
    print(f"recorded {freshness.DEPLOYED.relative_to(freshness.ROOT)}: commit {commit}{' (content has uncommitted changes)' if dirty else ''}; commit it with the deploy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
