"""The sign-off review (signoff_doc.py): that it shows everything the assistant says on its own, and that decisions read back
correctly. Run: python3 -m unittest discover -s chatbot/tests"""
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import build_index as b  # noqa: E402
import signoff_doc as sd  # noqa: E402


@unittest.skipUnless(shutil.which("node"), "needs node to read the Worker's fixed replies")
class Rendered(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page = sd.build_html()
        cls.idx = b.build(public=False)

    def test_every_position_ready_made_answer_and_fixed_reply_gets_a_ref_and_a_decision_box(self):
        pos = [c for c in self.idx["core"] if c.get("pos")]
        faq = [f for f in self.idx["faq"] if f["variants"]]
        refs = re.findall(r"Ref: ([a-z]+/[a-z0-9-]+)", self.page)
        self.assertEqual(len(refs), len(set(refs)), "refs are unique")
        self.assertEqual(sum(r.startswith("position/") for r in refs), len(pos))
        self.assertEqual(sum(r.startswith("answer/") for r in refs), len(faq) + 1, "the ready-made answers, and the no-position reply in Part 3")
        self.assertIn("staff/routing", refs)
        self.assertEqual({r for r in refs if r.startswith("fixed/")}, {"fixed/legal-help", "fixed/cannot-answer", "fixed/unavailable", "fixed/ask-a-person", "fixed/share-chart", "fixed/welcome", "fixed/privacy-note"})
        self.assertEqual(self.page.count("☐ Approve"), len(refs) * 2, "two approve lines in every decision box")

    def test_a_position_is_shown_word_for_word_with_its_chart_and_figures(self):
        c = next(c for c in self.idx["core"] if c.get("title") == "Conveyance tax modernization")
        self.assertIn(sd.e(c["text"].strip()[:120]), self.page)
        self.assertIn("up to 30%", self.page)             # the chart's own label
        self.assertIn("Published wording", self.page)     # the figures table
        self.assertIn("Staff confirm", self.page)         # accepted figures are marked for a person

    def test_the_fixed_replies_are_the_ones_the_worker_uses(self):
        fx = sd.node_json("({legal: L.LEGAL_REPLY, declined: H.FRIENDLY.declined})")
        self.assertIn(sd.e(fx["legal"].replace(" [1]", "")), self.page)
        self.assertIn(sd.e(fx["declined"]), self.page)

    def test_the_ask_a_person_wording_is_shown_exactly_as_the_page_has_it(self):
        import json as _json
        person = _json.loads(re.search(r"var PERSON = (\{.*?\});", (HERE / "index.html").read_text(encoding="utf-8")).group(1))
        for k in ("label", "button", "help", "subject"):
            self.assertIn(sd.e(person[k]), self.page, k)
        self.assertIn(self.idx["contact"]["email"], self.page)

    def test_the_chart_sharing_wording_is_shown_exactly_as_the_page_has_it(self):
        import json as _json
        share = _json.loads(re.search(r"var SHARE = (\{.*?\});", (HERE / "index.html").read_text(encoding="utf-8")).group(1))
        for k in ("image", "table", "footer", "drawn", "illustration", "copied", "saved", "failed", "manual"):
            self.assertIn(sd.e(share[k]), self.page, k)

    def test_table_widths_are_declared_for_every_table_and_no_script_gets_in(self):
        tables = self.page.count("<table")
        self.assertEqual(len(re.findall(r'<table data-w="[\d,]+"', self.page)), tables)
        for w in re.findall(r'<table data-w="([\d,]+)"', self.page):
            self.assertEqual(sum(map(int, w.split(","))), 100)
        self.assertNotIn("<script", self.page.lower())
        self.assertTrue(all(h.startswith("https://") for h in re.findall(r'href="([^"]+)"', self.page)))


class Decisions(unittest.TestCase):
    """Reading decisions back, and applying only approvals of the exact words the reviewer saw."""

    def setUp(self):
        import json as _json
        import approval
        import fixed
        self.json, self.approval, self.fixed = _json, approval, fixed
        self.tmp = Path(tempfile.mkdtemp(prefix="ha-signoff-"))
        (self.tmp / "content").mkdir()
        self.md = ("## Labor\n\n### Minimum wage\n<!-- status: draft -->\n<!-- url: /x -->\n\nText one.\n\n"
                   "### Capital gains tax\n<!-- status: draft -->\n\nText two.\n\n### Empty homes tax (Honolulu)\n<!-- status: draft -->\n\nText three.\n\n"
                   "### Parking mandates\n<!-- status: draft -->\n\nText four.\n")
        (self.tmp / "content" / "positions.md").write_text(self.md, encoding="utf-8")
        self.faq = {"_comment": "x", "entries": [{"id": "mission", "status": "draft", "variants": ["mission"], "answer": "Our mission. [1]", "sources": [{"title": "T", "url": "https://hiappleseed.org/a"}]}]}
        (self.tmp / "content" / "faq.json").write_text(_json.dumps(self.faq), encoding="utf-8")
        self.fixed_file = self.tmp / "content" / "fixed.json"
        self.fixed_file.write_text(_json.dumps({"items": {"welcome": {"status": "draft"}}}), encoding="utf-8")
        self.staff = {"status": "draft", "people": [{"id": "kai-tanaka", "name": "Kai Tanaka", "title": "Director", "email": "kai@hiappleseed.org"}],
                      "routes": [{"about": "everything", "people": ["kai-tanaka"]}]}
        self.staff_file = self.tmp / "content" / "staff.json"
        self.staff_file.write_text(_json.dumps(self.staff), encoding="utf-8")
        self.items = {"welcome": {"title": "Welcome", "why": "", "parts": ["Hello."]}}
        self.h = {
            "minimum": approval.position_hash("Minimum wage", "Text one."),
            "capital": approval.position_hash("Capital gains tax", "Text two."),
            "empty": approval.position_hash("Empty homes tax (Honolulu)", "Text three."),
            "parking": approval.position_hash("Parking mandates", "Text four."),
            "mission": approval.faq_hash("Our mission. [1]", ["https://hiappleseed.org/a"]),
            "welcome": approval.fixed_hash(["Hello."]),
            "staff": approval.staff_hash(self.staff),
        }

    def lines(self, h=None):
        h = h or self.h
        return ["Ref: position/capital-gains-tax", f"Text: {h['capital']}", "☐ Approve this position as written", "☒ Approve with the edits in Notes", "Reviewed by (name and date): Maria Lopez 2026-10-28",
                "Notes (say what to change): drop the $55 million sentence",
                "Ref: position/minimum-wage", f"Text: {h['minimum']}", "☒ Approve this position as written", "Reviewed by (name and date): Kai Tanaka", "Notes: ",
                "Ref: position/empty-homes-tax", f"Text: {h['empty']}", "☒ Approve this position as written", "☒ Hold: not ready", "Reviewed by (name and date): Lee 2026-10-29",
                "Ref: position/parking-mandates", f"Text: {h['parking']}", "☒ Approve this position as written", "Reviewed by (name and date): ",
                "Ref: answer/mission", f"Text: {h['mission']}", "☒ Approve this answer as written", "Reviewed by (name and date): Kai Tanaka 2026-10-30",
                "Ref: fixed/welcome", f"Text: {h['welcome']}", "☒ Approve this text as written", "Reviewed by (name and date): Kai Tanaka",
                "Ref: staff/routing", f"Text: {h['staff']}", "☒ Approve these people and routes as written", "Reviewed by (name and date): Kai Tanaka 2026-10-31"]

    def apply(self, lines, write=True):
        from unittest import mock
        with mock.patch.object(sd, "HERE", self.tmp), mock.patch.object(self.fixed, "STATUS_FILE", self.fixed_file), mock.patch.object(self.fixed, "items", lambda root=None: self.items):
            return sd.apply_approvals(sd.decisions(lines), write=write)

    def test_decisions_are_read_by_ref_with_the_hash_of_the_words_seen(self):
        d = sd.decisions(self.lines())
        self.assertEqual(d["position/capital-gains-tax"]["ticked"], ["Approve with the edits in Notes"])
        self.assertEqual(d["position/capital-gains-tax"]["by"], "Maria Lopez 2026-10-28")
        self.assertEqual(d["position/capital-gains-tax"]["hash"], self.h["capital"])
        self.assertIn("drop the $55 million", d["position/capital-gains-tax"]["notes"])
        self.assertEqual(len(d["position/empty-homes-tax"]["ticked"]), 2)

    def test_only_a_clean_named_approval_of_the_words_seen_is_applied_and_it_records_their_hash(self):
        log = self.apply(self.lines())
        pos = (self.tmp / "content" / "positions.md").read_text(encoding="utf-8")
        self.assertIn(f"### Minimum wage\n<!-- status: approved by Kai Tanaka ", pos)
        self.assertIn(f"<!-- reviewed: {self.h['minimum']} -->", pos)
        self.assertIn("### Capital gains tax\n<!-- status: draft -->", pos, "edits are for a person, not applied")
        self.assertIn("### Empty homes tax (Honolulu)\n<!-- status: draft -->", pos, "two boxes ticked: not applied")
        self.assertIn("### Parking mandates\n<!-- status: draft -->", pos, "no reviewer name: not applied")
        faq = self.json.loads((self.tmp / "content" / "faq.json").read_text(encoding="utf-8"))["entries"][0]
        self.assertEqual((faq["status"], faq["reviewed"]), ("approved by Kai Tanaka 2026-10-30", self.h["mission"]))
        fx = self.json.loads(self.fixed_file.read_text(encoding="utf-8"))["items"]["welcome"]
        self.assertEqual(fx["reviewed"], self.h["welcome"])
        st = self.json.loads(self.staff_file.read_text(encoding="utf-8"))
        self.assertEqual((st["status"], st["reviewed"]), ("approved by Kai Tanaka 2026-10-31", self.h["staff"]))
        self.assertTrue(any("more than one box" in l for l in log) and any("no reviewer name" in l for l in log))

    def test_words_that_changed_after_the_review_are_not_approved(self):
        (self.tmp / "content" / "positions.md").write_text(self.md.replace("Text one.", "Text one, edited."), encoding="utf-8")
        log = self.apply(self.lines())
        self.assertTrue(any("minimum-wage" in l and "changed after this review" in l for l in log))
        self.assertIn("### Minimum wage\n<!-- status: draft -->", (self.tmp / "content" / "positions.md").read_text(encoding="utf-8"))

    def test_routing_edited_after_the_review_is_not_approved(self):
        self.staff["routes"][0]["about"] = "everything, and more"
        self.staff_file.write_text(self.json.dumps(self.staff), encoding="utf-8")
        log = self.apply(self.lines())
        self.assertTrue(any("staff/routing" in l and "changed after this review" in l for l in log), log)
        self.assertEqual(self.json.loads(self.staff_file.read_text(encoding="utf-8"))["status"], "draft")

    def test_a_doc_that_predates_the_hashes_cannot_approve_anything(self):
        lines = [l for l in self.lines() if not l.startswith("Text:")]
        log = self.apply(lines)
        self.assertTrue(all("no Text: line" in l or "for a person" in l or "more than one" in l or "no reviewer name" in l for l in log), log)
        self.assertIn("draft", (self.tmp / "content" / "positions.md").read_text(encoding="utf-8"))

    def test_dry_run_changes_nothing(self):
        self.apply(self.lines(), write=False)
        self.assertEqual((self.tmp / "content" / "positions.md").read_text(encoding="utf-8"), self.md)
        self.assertEqual(self.json.loads((self.tmp / "content" / "faq.json").read_text(encoding="utf-8")), self.faq)
        self.assertEqual(self.json.loads(self.staff_file.read_text(encoding="utf-8")), self.staff)


if __name__ == "__main__":
    unittest.main()
