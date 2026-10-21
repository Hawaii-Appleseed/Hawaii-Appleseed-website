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
        self.assertEqual(sum(r.startswith("answer/") for r in refs), len(faq))
        self.assertEqual({r for r in refs if r.startswith("fixed/")}, {"fixed/legal-help", "fixed/no-position", "fixed/cannot-answer", "fixed/unavailable", "fixed/ask-a-person", "fixed/share-chart", "fixed/welcome", "fixed/privacy-note"})
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
    LINES = ["Ref: position/capital-gains-tax", "☐ Approve this position as written", "☒ Approve with the edits in Notes", "Reviewed by (name and date): Maria Lopez 2026-10-28",
             "Notes (say what to change): drop the $55 million sentence", "Ref: position/minimum-wage", "☒ Approve this position as written", "Reviewed by (name and date): Kai Tanaka",
             "Notes: ", "Ref: position/empty-homes-tax", "☒ Approve this position as written", "☒ Hold: not ready", "Reviewed by (name and date): Lee 2026-10-29",
             "Ref: position/parking-mandates", "☒ Approve this position as written", "Reviewed by (name and date): ", "Ref: answer/mission", "☒ Approve this answer as written"]

    def test_decisions_are_read_by_ref(self):
        d = sd.decisions(self.LINES)
        self.assertEqual(d["position/capital-gains-tax"]["ticked"], ["Approve with the edits in Notes"])
        self.assertEqual(d["position/capital-gains-tax"]["by"], "Maria Lopez 2026-10-28")
        self.assertIn("drop the $55 million", d["position/capital-gains-tax"]["notes"])
        self.assertEqual(d["position/minimum-wage"]["by"], "Kai Tanaka")
        self.assertEqual(len(d["position/empty-homes-tax"]["ticked"]), 2)

    def test_only_a_clean_named_approve_as_written_is_applied(self):
        tmp = Path(tempfile.mkdtemp(prefix="ha-signoff-"))
        (tmp / "content").mkdir()
        md = ("## Labor\n\n### Minimum wage\n<!-- status: draft -->\n<!-- url: /x -->\n\nText.\n\n"
              "### Capital gains tax\n<!-- status: draft -->\n\nText.\n\n### Empty homes tax (Honolulu)\n<!-- status: draft -->\n\nText.\n\n"
              "### Parking mandates\n<!-- status: draft -->\n\nText.\n")
        (tmp / "content" / "positions.md").write_text(md, encoding="utf-8")
        with mock.patch.object(sd, "HERE", tmp):
            log = sd.apply_approvals(sd.decisions(self.LINES), write=True)
            out = (tmp / "content" / "positions.md").read_text(encoding="utf-8")
        self.assertIn("### Minimum wage\n<!-- status: approved by Kai Tanaka ", out)
        self.assertIn("### Capital gains tax\n<!-- status: draft -->", out, "edits are for a person, not applied")
        self.assertIn("### Empty homes tax (Honolulu)\n<!-- status: draft -->", out, "two boxes ticked: not applied")
        self.assertIn("### Parking mandates\n<!-- status: draft -->", out, "no reviewer name: not applied")
        self.assertTrue(any("more than one box" in l for l in log) and any("no reviewer name" in l for l in log))

    def test_dry_run_changes_nothing(self):
        tmp = Path(tempfile.mkdtemp(prefix="ha-signoff-"))
        (tmp / "content").mkdir()
        (tmp / "content" / "positions.md").write_text("### Minimum wage\n<!-- status: draft -->\n", encoding="utf-8")
        with mock.patch.object(sd, "HERE", tmp):
            sd.apply_approvals(sd.decisions(self.LINES), write=False)
            self.assertIn("draft", (tmp / "content" / "positions.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
