"""Guards for the public assistant's index. Run: python3 -m unittest discover -s chatbot/tests"""
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import build_index as b  # noqa: E402


class Tokenizer(unittest.TestCase):
    def test_vectors(self):
        for v in json.loads((HERE / "tokenizer_vectors.json").read_text(encoding="utf-8")):
            self.assertEqual(b.tokenize(v["in"]), v["out"], v["in"])

    def test_okina_and_bill_numbers_collapse(self):
        self.assertEqual(b.tokenize("Hawaiʻi HB 1779"), ["hawaii", "hb1779"])


class Content(unittest.TestCase):
    def test_every_position_has_a_status_and_url(self):
        for it in b.parse_sections(HERE / "content" / "positions.md"):
            if it["group"] == "Topics with no stated public position":
                continue
            self.assertTrue(it["status"], f"{it['title']}: missing <!-- status: -->")
            self.assertTrue(it["url"], f"{it['title']}: missing <!-- url: -->")

    def test_public_build_leaves_out_unapproved_positions(self):
        idx = b.build(public=True)
        titles = [c["title"] for c in idx["core"]]
        self.assertNotIn("Conveyance tax modernization", titles)
        self.assertIn("Who we are", titles)           # org facts are not gated
        self.assertIn("2026 bill outcomes", titles)   # generated from Legislature data

    def test_pilot_build_includes_drafts(self):
        titles = [c["title"] for c in b.build(public=False)["core"]]
        self.assertIn("Conveyance tax modernization", titles)


class Corpus(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.idx = b.build(public=False)

    def test_internal_meeting_notes_never_indexed(self):
        for c in self.idx["chunks"]:
            self.assertNotIn("Coalition Meeting Notes", c["x"])
            self.assertNotIn("Group lead:", c["x"])

    def test_no_reference_dir_or_samples(self):
        for c in self.idx["chunks"]:
            self.assertFalse(c["t"].lower().startswith("sample"), c["t"])

    def test_blog_chunks_all_have_urls(self):
        for c in self.idx["chunks"]:
            if c["k"] == "blog":
                self.assertTrue(c["u"], c["t"])

    def test_chunks_are_readable_sizes(self):
        for c in self.idx["chunks"]:
            self.assertLess(len(c["x"].split()), 400, c["t"])

    def test_postings_reference_real_chunks(self):
        n = len(self.idx["chunks"])
        self.assertEqual(self.idx["bm25"]["n"], n)
        for term, p in list(self.idx["bm25"]["post"].items())[:500]:
            self.assertEqual(len(p) % 2, 0)
            self.assertTrue(all(0 <= ci < n for ci in p[::2]), term)


if __name__ == "__main__":
    unittest.main()
