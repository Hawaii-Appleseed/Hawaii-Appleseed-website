#!/usr/bin/env python3
"""Self-test for media_watch_approve.py (no network)."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(__file__))
import media_watch_approve as ap

BODY = """# Media watch — 2026-10-26

3 new stories mentioning Hawaiʻi Appleseed.

## Names Hawaiʻi Appleseed

- [Kauaʻi Wildfire Bill: A ‘Fight’ <Over> Numbers & More](https://www.civilbeat.org/2026/10/a/) — Honolulu Civil Beat, 2026-10-06  
  _names Hawaiʻi Appleseed_
- [Second story](https://example.org/b_(1)) — Example, 2026-10-07  
  _names Hawaiʻi Appleseed_

## Its work or its staff

- [Third story](https://example.org/c) — Example, 2026-10-08  
  _work: Hawaii Tax Fairness Coalition_

---
**To send to #communications:** reply `post`.
"""


class Approve(unittest.TestCase):
    def test_commands(self):
        self.assertEqual(ap.parse_command("post"), "all")
        self.assertEqual(ap.parse_command("  Post \n\nOn Mon, someone wrote:\n> post 9"), "all")
        self.assertEqual(ap.parse_command("post 3 1"), [1, 3])
        self.assertEqual(ap.parse_command("post 1, 3"), [1, 3])
        self.assertEqual(ap.parse_command("POST: 2"), [2])
        for no in ("", "posting this", "please post", "post it now", "do not post", "> post"):
            self.assertIsNone(ap.parse_command(no), no)

    def test_items_keep_order_and_odd_urls(self):
        items = ap.digest_items(BODY)
        self.assertEqual([i[0] for i in items][1:], ["Second story", "Third story"])
        self.assertEqual(items[1][1], "https://example.org/b_(1)")
        self.assertEqual(items[0][2], "Honolulu Civil Beat, 2026-10-06")

    def test_post_all_and_some_with_slack_escaping(self):
        payload, nums, _ = ap.build(BODY, "post", [])
        self.assertEqual(nums, [1, 2, 3])
        self.assertIn("*3 new media mentions*", payload["text"])
        self.assertIn("&lt;Over&gt; Numbers &amp; More", payload["text"])
        payload, nums, _ = ap.build(BODY, "post 2", [])
        self.assertEqual(nums, [2])
        self.assertIn("*1 new media mention*", payload["text"])
        self.assertNotIn("Third story", payload["text"])

    def test_never_posts_twice_and_refuses_a_bad_number(self):
        marker = ["Posted 1 and 2.\n<!-- posted:1,2 -->"]
        payload, nums, reply = ap.build(BODY, "post", marker)
        self.assertEqual(nums, [3])
        self.assertNotIn("Second story", payload["text"])
        payload, nums, reply = ap.build(BODY, "post 1 2", marker)
        self.assertEqual((payload, nums), (None, []))
        self.assertIn("already posted", reply)
        payload, nums, reply = ap.build(BODY, "post 7", [])
        self.assertEqual((payload, nums), (None, []))
        self.assertIn("no story 7", reply)

    def test_non_approval_does_nothing(self):
        self.assertEqual(ap.build(BODY, "thanks!", []), (None, [], ""))
        self.assertEqual(ap.build("no stories here", "post", [])[0], None)

    def test_cli_writes_slack_json_only_when_posting(self):
        with tempfile.TemporaryDirectory() as d:
            def w(name, text):
                with open(os.path.join(d, name), "w", encoding="utf-8") as f:
                    f.write(text)
                return os.path.join(d, name)
            args = ["--issue-body", w("i", BODY), "--posted", w("p", json.dumps("x <!-- posted:1 -->") + "\n"),
                    "--out", os.path.join(d, "slack.json")]
            ap.main(args + ["--comment-body", w("c", "hello")])
            self.assertFalse(os.path.exists(os.path.join(d, "slack.json")))
            ap.main(args + ["--comment-body", w("c", "post")])
            with open(os.path.join(d, "slack.json"), encoding="utf-8") as f:
                self.assertEqual(json.load(f)["text"].count("•"), 2)


if __name__ == "__main__":
    unittest.main()
