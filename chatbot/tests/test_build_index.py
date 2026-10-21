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


class Research(unittest.TestCase):
    def test_catalog_covers_every_publication_with_a_pdf(self):
        cat = b.pub_catalog()
        self.assertGreaterEqual(len(cat), 43)
        self.assertTrue(all(u.startswith("https://hiappleseed.org/publications/") for u in cat))
        self.assertTrue(all(v["p"] for v in cat.values()), "every published report has a PDF link")

    def test_curated_research_links_resolve(self):
        idx = b.build(public=False)  # build() exits if a curated slug is not a real report
        tagged = [c for c in idx["core"] if c["research"]]
        self.assertGreaterEqual(len(tagged), 13)
        for c in tagged:
            for u in c["research"]:
                self.assertIn(u, idx["pubs"], c["title"])


class Practical(unittest.TestCase):
    def test_practical_sections_exist_with_links_and_survive_public_build(self):
        titles = {c["title"]: c for c in b.build(public=True)["core"]}
        for t in ("Sign up for the newsletter and action alerts", "Contact the office",
                  "Jobs, requests for proposals, volunteering", "Legal help and referrals"):
            self.assertIn(t, titles)
            self.assertTrue(titles[t]["url"].startswith("https://"), t)

    def test_every_core_link_is_absolute_https(self):
        for c in b.build(public=False)["core"]:
            if c["url"]:
                self.assertTrue(c["url"].startswith("https://"), c["title"])


@unittest.skipUnless((HERE.parent / "writing-bot" / "sources.py").exists(), "needs the website repo checkout around chatbot/")
class Vendoring(unittest.TestCase):
    """vendor.py copies exactly what the builder reads, and building from the copy changes nothing."""

    @classmethod
    def setUpClass(cls):
        import subprocess
        import tempfile
        cls.tmp = Path(tempfile.mkdtemp(prefix="ha-vendor-"))
        cls.vdir = cls.tmp / "vendor"
        env = {**__import__("os").environ, "CHATBOT_VENDOR_DIR": str(cls.vdir)}
        cls.py = staticmethod(lambda *a, **k: subprocess.run([sys.executable, *a], capture_output=True, text=True, env={**env, **k.get("env", {})}))
        r = cls.py(str(HERE / "vendor.py"))
        assert r.returncode == 0, r.stderr
        cls.manifest = json.loads((cls.vdir / "MANIFEST.json").read_text(encoding="utf-8"))

    def test_manifest_records_the_snapshot(self):
        m = self.manifest
        self.assertTrue(m["source_commit"])
        self.assertEqual(m["counts"], {"publications": 43, "blog-posts": m["counts"]["blog-posts"], "testimony": m["counts"]["testimony"]})
        self.assertGreater(len(m["files"]), 200)

    def test_internal_notes_are_never_vendored(self):
        self.assertFalse((self.vdir / "writing-bot" / "reference").exists())
        self.assertFalse((self.vdir / "writing-bot" / "relationship-memory").exists())
        self.assertFalse(any("reference" in f or "relationship" in f for f in self.manifest["files"]))

    def test_vendored_build_equals_live_build(self):
        outs = {}
        for mode in ("live", "vendor"):
            out = self.tmp / f"{mode}.json"
            r = self.py(str(HERE / "build_index.py"), "--out", str(out), env={"CHATBOT_SOURCE": mode})
            self.assertEqual(r.returncode, 0, r.stderr)
            d = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(d["source"]["mode"], mode)
            outs[mode] = d
        for k in ("core", "pubs", "chunks", "bm25"):
            self.assertEqual(outs["live"][k], outs["vendor"][k], f"{k} differs between live and vendored builds")

    def test_check_detects_drift(self):
        self.assertEqual(self.py(str(HERE / "vendor.py"), "--check").returncode, 0)
        victim = next(self.vdir.glob("writing-bot/publications/*.txt"))
        original = victim.read_text(encoding="utf-8")
        victim.write_text(original + "\ntampered\n", encoding="utf-8")
        try:
            r = self.py(str(HERE / "vendor.py"), "--check")
            self.assertEqual(r.returncode, 1)
            self.assertIn(victim.name, r.stdout)
        finally:
            victim.write_text(original, encoding="utf-8")


class Embed(unittest.TestCase):
    """build_embed.py: one self-contained, ASCII-only widget payload."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(HERE))
        import build_embed as be
        cls.be = be
        cls.html = be.build(endpoint="https://ha-ask.example.workers.dev/chat", sitekey="0x4AAAtest")

    def test_self_contained(self):
        import re
        self.assertEqual(re.findall(r'<link[^>]*stylesheet[^>]*(?:\.\./assets|github\.io)', self.html), [])
        for needle in ("--ha-charcoal", "OkinaManrope", 'id="ha-ask"', "<script>"):
            self.assertIn(needle, self.html)

    def test_ascii_only_because_squarespace_mangles_utf8(self):
        self.assertTrue(all(ord(c) < 128 for c in self.html))
        self.assertIn("Hawai\\u02BBi", self.html)   # the okina survives inside script strings as an escape

    def test_endpoint_and_sitekey_are_written_into_the_wrapper(self):
        self.assertIn('data-endpoint="https://ha-ask.example.workers.dev/chat"', self.html)
        self.assertIn('data-turnstile-sitekey="0x4AAAtest"', self.html)
        self.assertIn('data-endpoint=""', self.be.build())

    def test_squarespace_mobile_breakout_is_present(self):
        self.assertIn("margin-left: calc(50% - 50vw) !important", self.html)

    def test_no_internal_content_leaks_into_the_widget(self):
        for needle in ("positions.md", "Coalition Meeting Notes", "ANTHROPIC_API_KEY", "sk-ant"):
            self.assertNotIn(needle, self.html)
