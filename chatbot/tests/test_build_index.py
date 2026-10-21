"""Guards for the public assistant's index. Run: python3 -m unittest discover -s chatbot/tests"""
import json
import re
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


class ChartSharing(unittest.TestCase):
    """Every chart carries Copy as image / Copy the table, drawn from the same data with its source baked in."""

    def test_the_widget_has_both_buttons_and_the_picture_carries_its_source(self):
        src = (HERE / "index.html").read_text(encoding="utf-8")
        share = json.loads(re.search(r"var SHARE = (\{.*?\});", src).group(1))
        self.assertEqual(sorted(share), sorted(["image", "table", "copied", "saved", "failed", "manual", "footer", "drawn", "illustration"]))
        self.assertTrue(share["footer"].endswith("hiappleseed.org"))
        for needle in ("function paintChart", "function tableText", "ClipboardItem", "fig.appendChild(shareRow(g))", "'Source: '"):
            self.assertIn(needle, src)
        # the picture is drawn on a canvas from the data: nothing is fetched and no library is loaded
        self.assertNotIn("html2canvas", src)
        self.assertNotIn("foreignObject", src)

    def test_the_squarespace_payload_is_still_ascii_with_the_picture_code_in_it(self):
        payload = (HERE / "squarespace-inject.html").read_text(encoding="utf-8")
        payload.encode("ascii")
        self.assertIn("paintChart", payload)


class EmbedDocument(unittest.TestCase):
    def test_worker_page_is_a_full_document_with_a_viewport_and_noindex(self):
        sys.path.insert(0, str(HERE))
        import build_embed as be
        doc = be.as_document(be.build())
        self.assertTrue(doc.startswith("<!doctype html>"))
        self.assertIn('name="viewport" content="width=device-width, initial-scale=1"', doc)
        self.assertIn("noindex", doc)
        self.assertIn('id="ha-ask"', doc)
        self.assertTrue(all(ord(c) < 128 for c in doc))


class ReadyMadeAnswers(unittest.TestCase):
    """content/faq.json goes out without a model checking it, so the build is the checker."""

    @classmethod
    def setUpClass(cls):
        cls.idx = b.build(public=False)
        cls.faq_path = HERE / "content" / "faq.json"

    def test_built_into_the_index_with_sources(self):
        self.assertGreaterEqual(len(self.idx["faq"]), 20)
        urls = {c["url"] for c in self.idx["core"]}
        for e in self.idx["faq"]:
            for s in e["sources"]:
                self.assertIn(s["url"], urls, e["id"])

    def _build_with(self, mutate):
        import tempfile
        from unittest import mock
        d = json.loads(self.faq_path.read_text(encoding="utf-8"))
        mutate(d["entries"])
        tmp = Path(tempfile.mkdtemp(prefix="ha-faq-"))
        (tmp / "content").mkdir()
        (tmp / "content" / "faq.json").write_text(json.dumps(d), encoding="utf-8")
        core = [c for c in self.idx["core"] if c["url"]]
        facts = (HERE / "content" / "about.md").read_text(encoding="utf-8") + (HERE / "content" / "practical.md").read_text(encoding="utf-8")
        with mock.patch.object(b, "HERE", tmp):
            return b.load_faq({c["url"] for c in core}, facts)

    def test_an_invented_phone_number_breaks_the_build(self):
        def tamper(es): next(e for e in es if e["id"] == "contact")["answer"] += " Or call (808) 555-0100."
        with self.assertRaises(SystemExit) as cm:
            self._build_with(tamper)
        self.assertIn("555-0100", str(cm.exception))

    def test_a_source_that_is_not_a_page_in_the_content_breaks_the_build(self):
        def tamper(es): next(e for e in es if e["id"] == "mission")["sources"][0]["url"] = "https://example.com/mission"
        with self.assertRaises(SystemExit):
            self._build_with(tamper)

    def test_citation_markers_must_match_sources_and_voice_rules_hold(self):
        def marker(es): next(e for e in es if e["id"] == "mission")["answer"] += " See also [2]."
        def exclaim(es): next(e for e in es if e["id"] == "greeting")["answer"] = "Aloha! Ask away."
        def bare(es): next(e for e in es if e["id"] == "greeting")["answer"] = "Welcome to Hawaii Appleseed."
        for t in (marker, exclaim, bare):
            with self.assertRaises(SystemExit, msg=t.__name__):
                self._build_with(t)

    def test_every_vetted_answer_passes_as_shipped(self):
        self.assertEqual(len(self._build_with(lambda es: None)), len(self.idx["faq"]))


class Graphics(unittest.TestCase):
    """content/graphics.json is drawn by the page with no model checking it, so the build is the checker: every figure
    has to be in the organization's approved text, or the graphic has to say it is a made-up illustration."""

    @classmethod
    def setUpClass(cls):
        cls.idx = b.build(public=False)
        cls.path = HERE / "content" / "graphics.json"
        cls.catalog = b.pub_catalog()
        cls.vetted = "\n".join((HERE / "content" / f).read_text(encoding="utf-8") for f in ("about.md", "practical.md", "positions.md"))
        cls.urls = {c["url"] for c in cls.idx["core"] if c["url"]}
        cls.titles = {c["title"] for c in cls.idx["core"] if c.get("pos")}
        cls.about = "\n".join((HERE / "content" / f).read_text(encoding="utf-8") for f in ("about.md", "practical.md"))

    def _load(self, mutate, wanted=(), **kw):
        import tempfile
        from unittest import mock
        d = json.loads(self.path.read_text(encoding="utf-8"))
        mutate(d["graphics"])
        tmp = Path(tempfile.mkdtemp(prefix="ha-gfx-"))
        (tmp / "content").mkdir()
        (tmp / "content" / "graphics.json").write_text(json.dumps(d), encoding="utf-8")
        with mock.patch.object(b, "HERE", tmp):
            return b.load_graphics(self.urls, self.catalog, self.vetted, set(wanted), self.titles, **kw)

    def _g(self, gs, gid):
        return next(g for g in gs if g["id"] == gid)

    def test_built_into_the_index_clean_of_proofs_and_attached_to_positions(self):
        ids = {g["id"] for g in self.idx["graphics"]}
        self.assertGreaterEqual(len(ids), 11)
        for g in self.idx["graphics"]:
            self.assertNotIn("proof", json.dumps(g), g["id"])
            self.assertTrue(g["source"]["url"].startswith("https://hiappleseed.org/"), g["id"])
        for c in self.idx["core"]:
            for gid in c.get("graphics", []):
                self.assertIn(gid, ids, c["title"])
        self.assertTrue(any(c.get("graphics") for c in self.idx["core"] if c["title"] == "Conveyance tax modernization"))

    def test_the_marginal_illustration_is_computed_and_labeled_made_up(self):
        g = self._g(self.idx["graphics"], "marginal-illustration")
        self.assertTrue(g["illustration"])
        self.assertIn("made-up", g["note"])
        vals = [r["value"] for r in g["rows"]]
        self.assertEqual(vals[:3], [5000, 10000, 10000])
        self.assertEqual(vals[3], sum(vals[:3]))          # the total is the parts
        self.assertEqual(vals[4], 50000)                  # the top rate on the whole price

    def test_every_graphic_as_shipped_passes(self):
        self.assertEqual(len(self._load(lambda gs: None)), len(self.idx["graphics"]))

    def test_a_number_that_is_not_in_the_approved_text_breaks_the_build(self):
        def row(gs): self._g(gs, "pay-gap")["items"][0]["label"] += " in 2031"
        def note(gs): self._g(gs, "eht-revenue")["note"] = "About 41,000 units sit empty."
        for t in (row, note):
            with self.assertRaises(SystemExit, msg=t.__name__):
                self._load(t)

    def test_a_label_that_disagrees_with_its_bar_or_its_proof_breaks_the_build(self):
        def value(gs): self._g(gs, "conveyance-allocation")["rows"][0]["value"] = 35
        def display(gs): self._g(gs, "capital-gains-rates")["rows"][2]["display"] = "8%"
        def proof(gs): self._g(gs, "reit-stats")["items"][0]["proof"] = "more than $20 billion in Hawaiʻi assets"
        for t in (value, display, proof):
            with self.assertRaises(SystemExit, msg=t.__name__):
                self._load(t)

    def test_a_spelled_out_number_in_our_text_counts(self):
        # "Sixty-six percent of HDOT's $5.68 billion" proves a bar labeled 66%
        self._load(lambda gs: None)
        self.assertEqual(b._nums("Sixty-six percent, twenty, $1,000, 7.25"), {"66", "20", "1000", "7.25"})

    def test_an_illustration_must_say_so_and_only_illustrations_may_be_computed(self):
        def unlabeled(gs): self._g(gs, "marginal-illustration")["note"] = "An example for a $2.5 million sale."
        def not_illustration(gs): self._g(gs, "marginal-illustration").pop("illustration")
        def wrong_end(gs): self._g(gs, "marginal-illustration")["price"] = 3000000
        for t in (unlabeled, not_illustration, wrong_end):
            with self.assertRaises(SystemExit, msg=t.__name__):
                self._load(t)

    def test_sources_aliases_types_and_attachments_are_checked(self):
        def source(gs): self._g(gs, "pay-gap")["source"]["url"] = "https://example.com/pay"
        def general(gs): self._g(gs, "pay-gap")["aliases"].append("history")
        def shared(gs): self._g(gs, "reit-stats")["aliases"].append("pay gap")
        def kind(gs): self._g(gs, "pay-gap")["type"] = "pie"
        def dup(gs): gs.append(dict(self._g(gs, "pay-gap")))
        for t in (source, general, shared, kind, dup):
            with self.assertRaises(SystemExit, msg=t.__name__):
                self._load(t)
        with self.assertRaises(SystemExit):
            self._load(lambda gs: None, wanted={"no-such-graphic"})

    def test_the_public_build_ships_only_graphics_the_approved_text_backs(self):
        pub = b.build(public=True)  # no position is approved yet: only the history timeline rests on about.md alone
        self.assertEqual({g["id"] for g in pub["graphics"]}, {"appleseed-history"})
        self.assertEqual(pub["faq"], [], "no ready-made answer is approved yet, so none ships (see test_approval.py)")
        # approve every position: now each graphic's figures are in approved text, so all of them ship
        every = self._load(lambda gs: None, public_text=self.vetted, public_titles=self.titles)
        self.assertEqual(len(every), len(self.idx["graphics"]))
        # approve one position's worth of text: only what that text backs (and the history) ships
        some = self._load(lambda gs: None, public_text=self.about + "\n" + next(c["text"] for c in self.idx["core"] if c["title"] == "Empty homes tax (Honolulu)"),
                          public_titles={"Empty homes tax (Honolulu)"})
        self.assertEqual({g["id"] for g in some}, {"appleseed-history", "eht-revenue"})


class Contact(unittest.TestCase):
    """The "ask a person" button's email, phone and page come from practical.md's "Contact the office", one source."""

    def test_contact_block_is_built_from_the_office_section(self):
        idx = b.build(public=False)
        c = idx["contact"]
        self.assertEqual(sorted(c), ["email", "page", "phone", "tel"])
        sec = next(x for x in idx["core"] if x["title"] == "Contact the office")
        self.assertIn(c["email"], sec["text"])
        self.assertIn(c["phone"], sec["text"])
        self.assertEqual(c["tel"], "+1" + re.sub(r"\D", "", c["phone"]))
        self.assertTrue(c["email"].endswith("@hiappleseed.org") and c["page"].startswith("https://hiappleseed.org/"))

    def test_a_contact_section_without_an_email_breaks_the_build(self):
        core = [{"title": "Contact the office", "text": "Phone: (808) 587-7605.", "url": "https://hiappleseed.org/contact"}]
        with self.assertRaises(SystemExit):
            b.contact_block(core)


class BillFeed(unittest.TestCase):
    """The bill-status feed is refreshed by a scheduled job from capitol.hawaii.gov, which sometimes answers 403. A refresh made of
    errors must not crash the build or erase what the assistant knows (this broke CI on the PR on 2026-10-21)."""

    def _feed(self, bills):
        import tempfile
        path = Path(tempfile.mkdtemp(prefix="ha-bills-")) / "bill-status.json"
        path.write_text(json.dumps({"generatedAt": "2026-10-21T18:11:11Z", "trackers": [], "bills": bills}), encoding="utf-8")
        return path

    def test_a_feed_of_only_errors_falls_back_to_the_committed_snapshot(self):
        from unittest import mock
        bad = self._feed({"HB2306": {"type": "HB", "number": "2306", "year": "2026", "error": "HTTP 403"},
                          "SB3125": {"type": "SB", "number": "3125", "year": "2026", "error": "HTTP 403"}})
        with mock.patch.object(b, "BILL_STATUS", bad):
            out = b.bill_outcomes()
        self.assertIsNotNone(out)
        self.assertIn("SB3125", out["text"])
        self.assertIn("Act 024", out["text"])
        self.assertIn("data pulled 2026-10-18", out["text"], "says the older date when it used the snapshot")

    def test_live_data_wins_for_the_bills_it_has_and_the_snapshot_fills_the_rest(self):
        from unittest import mock
        feed = self._feed({"SB3125": {"type": "SB", "number": "3125", "year": "2026", "updates": [{"date": "2026-12-01T00:00:00Z", "description": "Newer action in the live feed"}]},
                           "HB2306": {"type": "HB", "number": "2306", "year": "2026", "error": "HTTP 403"}})
        with mock.patch.object(b, "BILL_STATUS", feed):
            text = b.bill_outcomes()["text"]
        self.assertIn("Newer action in the live feed", text)
        self.assertIn("HB2306", text)

    def test_no_feed_and_no_snapshot_means_no_section_not_a_crash(self):
        from unittest import mock
        with mock.patch.object(b, "BILL_STATUS", Path("/nonexistent/bill-status.json")), mock.patch.object(b, "BILL_SNAPSHOT", Path("/nonexistent/snap.json")):
            self.assertIsNone(b.bill_outcomes())

    def test_the_snapshot_is_complete_and_current(self):
        snap = json.loads(b.BILL_SNAPSHOT.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(snap["bills"]), 14)
        for key, v in snap["bills"].items():
            self.assertTrue(v["date"] and v["description"], key)


class PositionAliases(unittest.TestCase):
    """Aliases are how a visitor's "where do you stand on X" finds a position, so they must be clean."""

    @classmethod
    def setUpClass(cls):
        cls.pos = [c for c in b.build(public=False)["core"] if c.get("pos")]

    def test_every_position_lists_aliases(self):
        self.assertGreaterEqual(len(self.pos), 25)
        for c in self.pos:
            self.assertTrue(c["aliases"], f"{c['title']}: add an <!-- aliases: ... --> line")

    def test_no_alias_names_two_positions(self):
        seen = {}
        for c in self.pos:
            for a in c["aliases"]:
                key = " ".join(b.tokenize(a))
                if key in seen and seen[key] != c["title"]:
                    self.fail(f"alias {a!r} is on both {seen[key]!r} and {c['title']!r}")
                seen[key] = c["title"]
