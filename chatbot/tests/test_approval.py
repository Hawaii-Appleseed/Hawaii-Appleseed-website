"""Approvals are of exact text, and a public build ships only what is approved: positions, ready-made answers and fixed replies.
Run: python3 -m unittest discover -s chatbot/tests"""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import approval  # noqa: E402
import build_index as b  # noqa: E402
import fixed  # noqa: E402


class Judge(unittest.TestCase):
    def test_a_hash_is_stable_short_and_sensitive_to_every_word(self):
        h = approval.position_hash("Minimum wage", "Text one.")
        self.assertEqual(h, approval.position_hash("Minimum wage", "  Text one.  "), "surrounding whitespace is not a change")
        self.assertNotEqual(h, approval.position_hash("Minimum wage", "Text one!"))
        self.assertNotEqual(h, approval.position_hash("Minimum wages", "Text one."))
        self.assertRegex(h, r"^[0-9a-f]{10}$")
        self.assertNotEqual(approval.faq_hash("A [1]", ["https://x/a"]), approval.faq_hash("A [1]", ["https://x/b"]), "a changed source is a change")

    def test_judge(self):
        ok = lambda *a: approval.judge(*a)[0]
        self.assertFalse(ok("draft", None, "abc"))
        self.assertFalse(ok("", "abc", "abc"))
        self.assertTrue(ok("approved by Kai 2026-10-28", None, "abc"), "a hand-written approval with no hash still works")
        self.assertTrue(ok("approved by Kai 2026-10-28", "abc", "abc"))
        self.assertEqual(approval.judge("approved by Kai 2026-10-28", "abc", "xyz"), (False, "changed since it was approved"))


class BuildInATempCopy(unittest.TestCase):
    """The helpers the build tests share: a temp copy of content/ and a public build over it (no tests of its own)."""

    @classmethod
    def setUpClass(cls):
        cls.src = HERE / "content"

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ha-approval-"))
        shutil.copytree(self.src, self.tmp / "content")
        self.faq_path = self.tmp / "content" / "faq.json"
        self.pos_path = self.tmp / "content" / "positions.md"

    def build(self):
        with mock.patch.object(b, "HERE", self.tmp):
            idx = b.build(public=True)
        return idx, idx["_report"]["skipped"]

    def edit_faq(self, entry_id, **fields):
        d = json.loads(self.faq_path.read_text(encoding="utf-8"))
        e = next(x for x in d["entries"] if x["id"] == entry_id)
        e.update(fields)
        self.faq_path.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        return e

    def hash_of(self, entry_id):
        e = next(x for x in json.loads(self.faq_path.read_text(encoding="utf-8"))["entries"] if x["id"] == entry_id)
        return approval.faq_hash(e["answer"], [s["url"] for s in e["sources"]])


class PublicBuild(BuildInATempCopy):
    def test_nothing_is_shipped_until_it_is_approved_and_the_pilot_build_still_has_everything(self):
        idx, skipped = self.build()
        self.assertEqual(idx["faq"], [])
        self.assertEqual(skipped["ready-made answer not approved (public build)"], 24)
        self.assertNotIn("status", json.dumps(idx["faq"]))
        pilot = b.build(public=False)
        self.assertEqual(len(pilot["faq"]), 24)

    def test_an_approved_answer_ships_and_so_does_its_chart(self):
        self.edit_faq("history", status="approved by Kai Tanaka 2026-10-28", reviewed=self.hash_of("history"))
        idx, _ = self.build()
        self.assertEqual([e["id"] for e in idx["faq"]], ["history"])
        self.assertTrue(set(idx["faq"][0]) <= {"id", "variants", "answer", "graphic", "sources"}, "no approval bookkeeping in the shipped index")
        self.assertIn("appleseed-history", {g["id"] for g in idx["graphics"]})

    def test_words_edited_after_approval_stop_shipping(self):
        self.edit_faq("mission", status="approved by Kai Tanaka 2026-10-28", reviewed=self.hash_of("mission"))
        self.assertEqual([e["id"] for e in self.build()[0]["faq"]], ["mission"])
        self.edit_faq("mission", answer=json.loads(self.faq_path.read_text(encoding="utf-8"))["entries"][0]["answer"])  # a no-op edit
        d = json.loads(self.faq_path.read_text(encoding="utf-8"))
        next(x for x in d["entries"] if x["id"] == "mission")["answer"] += " (edited)"
        self.faq_path.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        idx, skipped = self.build()
        self.assertEqual(idx["faq"], [])
        self.assertEqual(skipped["ready-made answer changed since it was approved (public build)"], 1)

    def test_a_hand_written_approval_with_no_hash_still_ships(self):
        self.edit_faq("contact", status="approved by Kai Tanaka 2026-10-28")
        self.assertEqual([e["id"] for e in self.build()[0]["faq"]], ["contact"])

    def test_a_position_edited_after_approval_stops_shipping(self):
        text = self.pos_path.read_text(encoding="utf-8")
        sec = b.parse_sections(self.pos_path)
        wage = next(s for s in sec if s["title"] == "Minimum wage")
        h = approval.position_hash(wage["title"], wage["text"])
        self.pos_path.write_text(text.replace("### Minimum wage\n<!-- status: draft -->", f"### Minimum wage\n<!-- status: approved by Kai Tanaka 2026-10-28 -->\n<!-- reviewed: {h} -->", 1), encoding="utf-8")
        idx, _ = self.build()
        self.assertIn("Minimum wage", [c["title"] for c in idx["core"]])
        self.pos_path.write_text(self.pos_path.read_text(encoding="utf-8").replace(wage["text"][-30:], wage["text"][-30:] + " Edited after approval.", 1), encoding="utf-8")
        idx, skipped = self.build()
        self.assertNotIn("Minimum wage", [c["title"] for c in idx["core"]])
        self.assertEqual(skipped["position changed since it was approved (public build)"], 1)


class StaffRouting(BuildInATempCopy):
    """Who to talk to: checked against the Staff list, and in a public build left out until staff approve it (people and routes)."""

    def staff(self):
        return json.loads((self.tmp / "content" / "staff.json").read_text(encoding="utf-8"))

    def save(self, d):
        (self.tmp / "content" / "staff.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")

    def test_the_pilot_build_has_the_section_and_the_index_names_twelve_people(self):
        with mock.patch.object(b, "HERE", self.tmp):
            idx = b.build(public=False)
        self.assertEqual(len(idx["staff"]["people"]), 12)
        sec = next(c for c in idx["core"] if c["title"] == "Who to talk to about what")
        self.assertIn("arjuna-heim", sec["text"])
        self.assertIn("devin@hiappleseed.org", sec["text"])
        self.assertTrue(sec["url"].endswith("/our-team"))

    def test_staff_json_and_the_staff_list_in_about_must_agree(self):
        d = self.staff()
        d["people"][2]["title"] = "Chief of Everything"
        self.save(d)
        with mock.patch.object(b, "HERE", self.tmp), self.assertRaises(SystemExit) as cm:
            b.build(public=False)
        self.assertIn("disagree", str(cm.exception))

    def test_a_route_naming_nobody_who_exists_and_a_foreign_email_break_the_build(self):
        d = self.staff()
        d["routes"][0]["people"].append("ghost")
        self.save(d)
        with mock.patch.object(b, "HERE", self.tmp), self.assertRaises(SystemExit):
            b.build(public=False)
        d = self.staff()
        d["people"][0]["email"] = "will@example.com"
        self.save(d)
        with mock.patch.object(b, "HERE", self.tmp), self.assertRaises(SystemExit):
            b.build(public=False)

    def test_a_public_build_leaves_it_out_until_approved_and_again_when_it_is_edited(self):
        idx, skipped = self.build()
        self.assertIsNone(idx["staff"])
        self.assertNotIn("Who to talk to about what", [c["title"] for c in idx["core"]])
        self.assertEqual(skipped["who-to-talk-to routing not approved (public build)"], 1)
        d = self.staff()
        d["status"], d["reviewed"] = "approved by Kai Tanaka 2026-10-28", approval.staff_hash(d)
        self.save(d)
        idx, _ = self.build()
        self.assertEqual(len(idx["staff"]["people"]), 12)
        self.assertIn("Who to talk to about what", [c["title"] for c in idx["core"]])
        d["routes"][1]["about"] += " and more"
        self.save(d)
        idx, skipped = self.build()
        self.assertIsNone(idx["staff"])
        self.assertEqual(skipped["who-to-talk-to routing changed since it was approved (public build)"], 1)


@unittest.skipUnless(shutil.which("node"), "the fixed replies live in the Worker's JavaScript")
class FixedReplies(unittest.TestCase):
    def test_a_public_build_needs_every_fixed_reply_approved_and_unchanged(self):
        self.assertEqual(len(fixed.problems()), 7, "all seven are draft")
        tmp = Path(tempfile.mkdtemp(prefix="ha-fixed-")) / "fixed.json"
        items = fixed.items()
        tmp.write_text(json.dumps({"items": {i: {"status": "approved by Kai Tanaka 2026-10-28", "reviewed": fixed.hash_of(it)} for i, it in items.items()}}), encoding="utf-8")
        with mock.patch.object(fixed, "STATUS_FILE", tmp):
            self.assertEqual(fixed.problems(), [])
            d = json.loads(tmp.read_text(encoding="utf-8"))
            d["items"]["welcome"]["reviewed"] = "0000000000"
            tmp.write_text(json.dumps(d), encoding="utf-8")
            self.assertEqual(len(fixed.problems()), 1)
            self.assertIn("changed since it was approved", fixed.problems()[0])

    def test_the_public_command_line_build_refuses_while_any_is_unapproved(self):
        out = Path(tempfile.mkdtemp(prefix="ha-out-")) / "index.json"
        with mock.patch.object(sys, "argv", ["build_index.py", "--public", "--out", str(out)]):
            self.assertEqual(b.main(), 3)
        self.assertFalse(out.exists(), "nothing is written when the gate refuses")
        with mock.patch.object(sys, "argv", ["build_index.py", "--public", "--out", str(out)]), mock.patch.object(fixed, "problems", return_value=[]):
            self.assertEqual(b.main(), 0)
        self.assertTrue(out.exists())

    def test_every_fixed_item_the_review_shows_has_a_status_entry(self):
        self.assertEqual(sorted(fixed.statuses()), sorted(fixed.items()))


if __name__ == "__main__":
    unittest.main()
