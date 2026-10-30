"""The figure cross-check (figures.py): what it extracts, how it matches, and that the real positions pass it.
Run: python3 -m unittest discover -s chatbot/tests"""
import sys
import unittest
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import build_index as b  # noqa: E402
import figures as fg  # noqa: E402


def keys(text):
    return [f["key"] for f in fg.extract(text)]


class Extract(unittest.TestCase):
    def test_money_percent_counts_bills_and_acts(self):
        self.assertEqual(keys("$183.4 million, $800M, $1,000, $2 billion"), ["usd:183400000", "usd:800000000", "usd:1000", "usd:2000000000"])
        self.assertEqual(keys("7.25 percent and 11%"), ["pct:7.25", "pct:11"])
        self.assertEqual(keys("more than 50,000 units, 200,000+ workers"), ["num:50000", "num:200000"])
        self.assertEqual(keys("HB 1850 and SB3125 became Act 24"), ["bill:HB1850", "bill:SB3125", "act:24"])

    def test_spelled_out_numbers_and_ranges(self):
        self.assertEqual(keys("Sixty-six percent of the budget"), ["pct:66"])
        self.assertEqual(keys("a flat tax of three percent"), ["pct:3"])
        self.assertEqual(sorted(keys("between 82.4 and 87 percent")), ["pct:82.4", "pct:87"])
        self.assertEqual(keys("no one knows"), [])  # "one" alone is not a figure

    def test_years_and_plain_small_numbers_are_not_figures(self):
        self.assertEqual(keys("In 2026 it passed 3 amendments in 17 states."), [])

    def test_qualifiers(self):
        q = lambda text: fg.extract(text)[0]["qual"]
        self.assertEqual(q("Up to 30 percent would go to DHHL"), "max")
        self.assertEqual(q("capped at $60 million a year"), "max")
        self.assertEqual(q("debt of $500 or more"), "min")
        self.assertEqual(q("at least 90 percent of cases"), "min")
        self.assertEqual(q("raised the wage from $10.10 up to $18 an hour"), "")  # "up to" says where it went, not a ceiling
        self.assertEqual(q("about 70 percent"), "")


def doc(title, text, url=None):
    return {"title": title, "url": url or f"https://hiappleseed.org/publications/{title.lower().replace(' ', '-')}", "lines": [text]}


class Matching(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus = fg.Corpus([
            doc("Empty Homes Tax", "A 3 percent tax on empty homes in Honolulu could generate $183.4 million in new revenue for county services each year."),
            doc("School Meals", "Up to 30 percent of revenue would go to the Department of Hawaiian Home Lands, capped at $60 million per year. Family budgets are tight."),
            doc("Food Brief", "Nearly 6,000 SNAP households in the county lost benefits last winter."),
            doc("Wages", "In 2023, women in Hawaiʻi earned 82.4 percent of what men earned. Poverty would fall with equal pay."),
        ], "SB3125 Act 24")

    def status(self, text, aliases=(), title="x", allow=()):
        r = fg.check([{"title": title, "text": text, "aliases": list(aliases)}], self.corpus, list(allow))
        return [row["status"] for sec in r["sections"] for row in sec["figures"]] or ["sentence"], r

    def test_a_figure_stated_about_the_same_thing_is_backed(self):
        self.assertEqual(self.status("An empty homes tax of 3 percent could raise about $183.4 million a year for Honolulu.")[0], ["sentence", "sentence"])

    def test_a_figure_that_turns_up_somewhere_unrelated_is_not(self):
        st, r = self.status("The Hawaiian Home Lands waitlist is 6,000 families.")
        self.assertEqual(st, ["none"], "6,000 is in the corpus, but about SNAP households")
        self.assertTrue(r["sections"][0]["figures"][0]["closest"], "a published sentence is offered beside it")

    def test_an_invented_figure_is_not_backed(self):
        self.assertEqual(self.status("The tax would raise $999 million a year.")[0], ["none"])

    def test_a_dropped_qualifier_is_caught(self):
        st, _ = self.status("Revenue goes to the Department of Hawaiian Home Lands (30 percent), capped at nothing.")
        self.assertEqual(st, ["qualifier"])
        self.assertEqual(self.status("Up to 30 percent would go to the Department of Hawaiian Home Lands.")[0], ["sentence"])

    def test_the_same_subject_report_is_a_weaker_back(self):
        # the published sentence is about something else entirely in its words; only the report's subject ties them
        st, _ = self.status("Overall the ratio looks to be near 82.4 percent.", aliases=["equal pay"], title="Equal pay")
        self.assertEqual(st, ["topic"])
        self.assertEqual(self.status("Overall the ratio looks to be near 82.4 percent.", aliases=["rent control"], title="Rent control")[0], ["none"])

    def test_bills_and_acts_need_only_to_exist(self):
        self.assertEqual(self.status("SB3125 became Act 24.")[0], ["sentence", "sentence"])
        self.assertEqual(self.status("HB9999 became Act 777.")[0], ["none", "none"])

    def test_accepting_a_figure_needs_a_reason(self):
        text = "The tax would raise $999 million a year."
        ok = {"section": "x", "figure": "usd:999000000", "reason": "checked against the fiscal note"}
        self.assertEqual(self.status(text, allow=[ok])[0], ["accepted"])
        self.assertEqual(self.status(text, allow=[{**ok, "reason": " "}])[0], ["none"])
        self.assertEqual(self.status(text, allow=[{**ok, "section": "another section"}])[0], ["none"])


class RealPositions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.docs = list(b.corpus_docs(Counter()))
        cls.core = [it for it in b.parse_sections(HERE / "content" / "positions.md") if it["group"] != "Topics with no stated public position"]
        for c in cls.core:
            c["pos"] = True

    def test_every_figure_in_the_positions_is_backed_or_accepted(self):
        report = b.check_figures(self.core, self.docs, public=False)
        self.assertEqual(report["unexplained"], 0, "run python3 chatbot/check_figures.py")
        self.assertGreater(report["figures"], 100)

    def test_the_conveyance_allocation_without_its_caps_would_have_been_caught(self):
        # the first draft said "(20 percent) ... (30 percent) ... (5 percent)"; the published post says "up to", with dollar caps
        sec = {"title": "Conveyance tax modernization", "aliases": ["conveyance tax"],
               "text": "Revenue would be dedicated to affordable housing (20 percent), the Department of Hawaiian Home Lands (30 percent), DURF (20 percent), and conservation (5 percent)."}
        r = fg.check([sec], fg.Corpus(self.docs, ""), [])
        self.assertEqual([row["status"] for row in r["sections"][0]["figures"]], ["qualifier", "qualifier", "sentence", "qualifier"])

    def test_an_unpublished_figure_in_an_approved_position_stops_a_public_build_but_not_a_pilot_build(self):
        core = [dict(c) for c in self.core if c["title"] == "Minimum wage"]
        core[0]["text"] += " It would raise pay for 987,654 workers."
        self.assertEqual(b.check_figures(core, self.docs, public=False)["unexplained"], 1)
        with self.assertRaises(SystemExit) as cm:
            b.check_figures(core, self.docs, public=True)
        self.assertIn("987,654", str(cm.exception))

    def test_every_accepted_figure_still_appears_in_its_section(self):
        import json
        allow = json.loads((HERE / "content" / "figures.json").read_text(encoding="utf-8"))["allow"]
        by_title = {c["title"]: {f["key"] for f in fg.extract(c["text"])} for c in self.core}
        for a in allow:
            self.assertIn(a["section"], by_title, a)
            self.assertIn(a["figure"], by_title[a["section"]], f"stale allowlist entry: {a['section']} {a['figure']}")
            self.assertTrue(a["reason"].strip() and a["source"].strip(), a)


if __name__ == "__main__":
    unittest.main()
