"""freshness.py and the weekly corpus check: how far behind the corpus the deployed assistant is, and the session year.
Run: python3 -m unittest discover -s chatbot/tests"""
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import build_index as b  # noqa: E402
import freshness as fr  # noqa: E402


def git(cwd, *a, env=None):
    import os
    return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True, check=True, env={**os.environ, **(env or {})}).stdout.strip()


class Freshness(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp(prefix="ha-fresh-"))
        git(self.d, "init", "-q")
        git(self.d, "config", "user.email", "t@example.com")
        git(self.d, "config", "user.name", "T")

    def commit(self, path, text, date):
        f = self.d / path
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")
        git(self.d, "add", "-A")
        env = {"GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date}
        git(self.d, "commit", "-q", "-m", f"change {path}", env=env)
        return git(self.d, "rev-parse", "--short", "HEAD")

    def test_only_corpus_files_count_and_the_oldest_change_sets_the_age(self):
        base = self.commit("writing-bot/publications/a.txt", "a", "2026-10-01T12:00:00+00:00")
        self.commit("writing-bot/reference/notes.txt", "internal", "2026-10-02T12:00:00+00:00")   # never indexed
        self.commit("website/index.html", "x", "2026-10-03T12:00:00+00:00")                       # not the corpus
        self.commit("writing-bot/blog-posts/2026/new.txt", "new post", "2026-10-05T12:00:00+00:00")
        self.commit("tax-fairness/data/bill-status.json", "{}", "2026-10-09T12:00:00+00:00")
        r = fr.report({"sourceCommit": base, "deployedAt": "2026-10-01T13:00:00Z"}, self.d, now=datetime(2026, 10, 20, tzinfo=timezone.utc))
        self.assertTrue(r["known"])
        self.assertEqual([c["path"] for c in r["changed"]], ["writing-bot/blog-posts/2026/new.txt", "tax-fairness/data/bill-status.json"])
        self.assertEqual(r["daysBehind"], 14, "from the oldest undeployed change (Oct 5) to Oct 20")

    def test_nothing_changed_means_up_to_date(self):
        base = self.commit("writing-bot/publications/a.txt", "a", "2026-10-01T12:00:00+00:00")
        self.commit("chatbot/worker/src/handler.js", "code", "2026-10-02T12:00:00+00:00")  # code, not content
        r = fr.report({"sourceCommit": base}, self.d)
        self.assertEqual((r["known"], r["changed"], r["daysBehind"]), (True, [], 0))

    def test_unknown_when_the_deploy_was_never_recorded_or_the_commit_is_missing(self):
        self.commit("writing-bot/publications/a.txt", "a", "2026-10-01T12:00:00+00:00")
        self.assertFalse(fr.report(None, self.d)["known"])
        self.assertFalse(fr.report({"sourceCommit": "deadbee"}, self.d)["known"])


class SessionYear(unittest.TestCase):
    def test_the_session_is_recorded_in_the_index_and_drives_the_generated_section(self):
        idx = b.build(public=False)
        self.assertEqual(idx["session"]["covered"], b.session_year())
        self.assertTrue(any(c["title"] == f"{b.session_year()} bill outcomes" for c in idx["core"]))

    def test_strict_mode_fails_on_a_new_report_without_a_topic(self):
        from unittest import mock
        real = b.pub_catalog()
        url = next(iter(real))
        fake = {**real, url: {**real[url], "a": []}}
        with mock.patch.object(b, "pub_catalog", return_value=fake):
            idx = b.build(public=False)
        self.assertIn(real[url]["t"], idx["_report"]["untopiced"])


if __name__ == "__main__":
    unittest.main()
