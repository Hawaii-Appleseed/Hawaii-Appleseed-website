#!/usr/bin/env python3
"""Offline tests for scripts/media_watch.py. Run: python3 scripts/test_media_watch.py"""
import base64
import datetime as dt
import io
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import media_watch as mw  # noqa: E402

CFG = json.loads(mw.CONFIG_PATH.read_text(encoding="utf-8"))
STAFF = ["Will White", "Devin Thomas", "Will Caron"]

GOOGLE = """<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>Tax reform gains ground - Honolulu Civil Beat</title>
<link>https://news.google.com/rss/articles/CBMiXXXX?oc=5</link>
<pubDate>Sun, 27 Sep 2026 10:09:53 GMT</pubDate>
<description>&lt;a href="x"&gt;Tax reform gains ground&lt;/a&gt;&amp;nbsp;&lt;font&gt;Honolulu Civil Beat&lt;/font&gt; Hawaii Appleseed says...</description>
<source url="https://www.civilbeat.org">Honolulu Civil Beat</source></item></channel></rss>"""

BING = """<?xml version="1.0"?><rss version="2.0" xmlns:News="https://www.bing.com/news"><channel>
<item><title>Nonprofit seeks new leader</title>
<link>http://www.bing.com/news/apiclick.aspx?ref=FexRss&amp;url=https%3a%2f%2fwww.bizjournals.com%2fpacific%2fnews%2fa.html&amp;c=1</link>
<description>Hawaii Appleseed Center for Law and Economic Justice...</description>
<pubDate>Mon, 25 Nov 2024 16:10:00 GMT</pubDate><News:Source>The Business Journals</News:Source></item></channel></rss>"""

ATOM = """<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><entry>
<title>Food fund heads to ballot</title><link href="https://example.org/a"/>
<updated>2026-09-28T01:00:00Z</updated><content>Full text here</content></entry></feed>"""


def item(title, snippet="", url="https://example.org/x", outlet="Example", outlet_url="https://example.org"):
    return {"title": title, "snippet": snippet, "url": url, "outlet": outlet, "outlet_url": outlet_url,
            "published": "", "source": "google"}


class Text(unittest.TestCase):
    def test_norm_folds_okina_and_possessive(self):
        self.assertEqual(mw.norm("Hawaiʻi Appleseed"), "hawaii appleseed")
        self.assertEqual(mw.norm("Hawai'i Appleseed"), "hawaii appleseed")  # okina-lint:ignore — the wrong spelling is the test input
        self.assertEqual(mw.norm("Hawai’i Appleseed’s report"), "hawaii appleseed report")  # okina-lint:ignore — the wrong spelling is the test input
        self.assertEqual(mw.norm("Hawaiʻi’s Appleseed"), "hawaii appleseed")

    def test_has_phrase_is_whole_word(self):
        self.assertTrue(mw.has_phrase(mw.norm("said Will White of X"), "Will White"))
        self.assertFalse(mw.has_phrase(mw.norm("Will Whiteside spoke"), "Will White"))

    def test_canon_url_drops_tracking(self):
        self.assertEqual(mw.canon_url("https://www.a.com/p/?utm_source=x&id=2#f"), "a.com/p?id=2")

    def test_decode_google_old_style(self):
        tok = base64.urlsafe_b64encode(b"\x08\x13\x22\x20https://example.org/story\xd2\x01\x00").decode().rstrip("=")
        self.assertEqual(mw.decode_google_url(f"https://news.google.com/rss/articles/{tok}?oc=5"),
                         "https://example.org/story")
        self.assertIsNone(mw.decode_google_url("https://news.google.com/rss/articles/CBMiXXXX"))

    def test_trim_chrome_only_in_back_half(self):
        body = "word " * 200
        self.assertEqual(mw.trim_chrome(body + "Read this next: other story"), body)
        self.assertIn("Related", mw.trim_chrome("Related: an opening line " + body))


class Errors(unittest.TestCase):
    def test_http_error_carries_retry_after_and_body(self):
        import email.message
        import urllib.error
        h = email.message.Message()
        h["Retry-After"] = "120"
        h["Server"] = "nginx"
        e = urllib.error.HTTPError("https://x.test/", 429, "Too Many Requests", h,
                                   io.BytesIO(b"<html><body>Slow down, please.</body></html>"))
        msg = mw.describe_error(e)
        for want in ("HTTP 429", "Retry-After: 120", "Server: nginx", "Slow down, please."):
            self.assertIn(want, msg)
        self.assertEqual(mw.describe_error(OSError("timed out")), "timed out")


class Parse(unittest.TestCase):
    def test_google(self):
        (a,) = mw.parse_google(GOOGLE)
        self.assertEqual(a["title"], "Tax reform gains ground")   # outlet suffix stripped
        self.assertEqual(a["outlet"], "Honolulu Civil Beat")
        self.assertIn("Hawaii Appleseed says", a["snippet"])

    def test_bing_extracts_real_url(self):
        (a,) = mw.parse_bing(BING)
        self.assertEqual(a["url"], "https://www.bizjournals.com/pacific/news/a.html")
        self.assertEqual(a["outlet"], "The Business Journals")

    def test_feed_atom(self):
        (a,) = mw.parse_feed(ATOM, "Example")
        self.assertEqual((a["title"], a["url"]), ("Food fund heads to ballot", "https://example.org/a"))
        self.assertIsNotNone(mw.parse_any_date(a["published"]))


class Classify(unittest.TestCase):
    def c(self, title, snippet="", **kw):
        return mw.classify(item(title, snippet), CFG, STAFF, **kw)

    def test_org_name_is_high(self):
        self.assertEqual(self.c("Hawaiʻi Appleseed releases report")[0], "high")
        self.assertEqual(self.c("x", "study by Hawai'i Appleseed Center for Law and Economic Justice")[0], "high")  # okina-lint:ignore — the wrong spelling is the test input

    def test_appleseed_needs_hawaii_context(self):
        self.assertEqual(self.c("Appleseed's tax report hits Honolulu")[0], "medium")
        self.assertIsNone(self.c("Johnny Appleseed festival"))
        self.assertIsNone(self.c("Appleseed report on Texas courts"))

    def test_staff_tiers(self):
        self.assertEqual(self.c("Will White of Appleseed on housing")[0], "medium")
        self.assertEqual(self.c("Devin Thomas on Hawaii tax policy")[0], "medium")
        self.assertEqual(self.c("Devin Thomas scores twice")[0], "low")   # a stranger looks like this

    def test_full_text_staff_without_appleseed_says_so(self):
        conf, reasons, _ = self.c("x", "Devin Thomas on Hawaii tax policy", full_text=True)
        self.assertEqual(conf, "medium")
        self.assertIn("does not name Appleseed", reasons[0])
        # no Hawaii/policy context: a namesake, not us
        self.assertEqual(self.c("x", "Devin Thomas scored twice in Tuesday's game", full_text=True)[0], "low")

    def test_staff_names_are_case_sensitive(self):
        self.assertIsNone(self.c("the tide will white-cap soon", "will white water rafting in Hawaii on a budget"))
        self.assertEqual(self.c("Will White on the Hawaii budget")[0], "medium")

    def test_okina_used_as_possessive(self):
        # HPR: Hawaiʻi Appleseedʻs “Equity on the Menu”
        self.assertEqual(mw.norm("Hawaiʻi Appleseedʻs “Equity”"), "hawaii appleseed equity")
        self.assertEqual(self.c("x", "Hawaiʻi Appleseedʻs “Equity on the Menu” shows a cost")[0], "high")
        self.assertEqual(mw.norm("Hawaiʻi and Oʻahu"), "hawaii and oahu")   # a real okina is still dropped

    def test_engine_hit_with_no_visible_text_is_unchecked(self):
        conf, reasons, _ = self.c("Local ag groups rally for food fund", kind="org")
        self.assertEqual((conf, reasons), ("medium", [mw.UNCHECKED]))
        self.assertIsNone(self.c("Local ag groups rally for food fund", kind="staff"))

    def test_work_term(self):
        self.assertEqual(self.c("Hawaii Tax Fairness Coalition urges vote")[0], "medium")

    def test_verify_article(self):
        self.assertEqual(mw.verify_article("... Hawai'i Appleseed said ...", CFG)[0], "high")  # okina-lint:ignore — the wrong spelling is the test input
        self.assertEqual(mw.verify_article("Appleseed is active in Honolulu", CFG)[0], "medium")
        self.assertIsNone(mw.verify_article("nothing to see here", CFG))


class Dedupe(unittest.TestCase):
    def test_merge_prefers_direct_url_and_higher_confidence(self):
        a = {**item("Tax reform gains ground", url="https://news.google.com/rss/articles/CBM"),
             "confidence": "medium", "reasons": ["a"], "source": "google", "query": "q1"}
        b = {**item("Tax Reform Gains Ground!", url="https://www.civilbeat.org/2026/09/tax"),
             "confidence": "high", "reasons": ["b"], "source": "bing", "query": "q2"}
        (m,) = mw.merge_found([a, b]).values()
        self.assertEqual((m["url"], m["confidence"]), ("https://www.civilbeat.org/2026/09/tax", "high"))
        self.assertEqual(sorted(m["sources"]), ["bing", "google"])

    def test_on_site_by_url_and_by_title(self):
        press = [{"url": mw.canon_url("https://www.staradvertiser.com/2026/09/16/a/"),
                  "title": mw.norm("Hawaiʻi wealth flight fears are overblown"), "fullUrl": "/in-the-news/x"}]
        self.assertEqual(mw.on_site(item("Any", url="https://staradvertiser.com/2026/09/16/a"), press), "/in-the-news/x")
        self.assertEqual(mw.on_site(item("Column: Isle wealth flight fears are overblown"), press), "/in-the-news/x")
        self.assertEqual(mw.on_site(item("Something else entirely"), press), "")

    def test_own_site_is_dropped(self):
        self.assertTrue(mw.is_own(item("x", url="https://hiappleseed.org/blog/y"), CFG))
        self.assertTrue(mw.is_own(item("x", outlet_url="https://www.hitaxfairness.org"), CFG))
        self.assertFalse(mw.is_own(item("x", url="https://www.civilbeat.org/y"), CFG))


class Settle(unittest.TestCase):
    def setUp(self):
        self._r, self._f = mw.resolve_google, mw.fetch_article_text
        self.pages = {}
        mw.resolve_google = lambda u: None
        mw.fetch_article_text = lambda u: self.pages.get(u)

    def tearDown(self):
        mw.resolve_google, mw.fetch_article_text = self._r, self._f

    def make(self, title, conf, reasons, url="https://example.org/a"):
        m = {**item(title, url=url), "confidence": conf, "reasons": reasons, "sources": ["bing"], "query": "q"}
        return {mw.title_key(title): m}

    def test_confirmed_low_is_upgraded_and_only_reason_removed(self):
        merged = self.make("Will Caron: Column", "low", ["staff: Will Caron only"])
        self.pages["https://example.org/a"] = "Will Caron is with Hawaiʻi Appleseed. " * 40
        mw.settle(merged, {"items": []}, CFG, {}, "2026-09-29", delay=0, out=io.StringIO())
        (m,) = merged.values()
        self.assertEqual(m["confidence"], "high")
        self.assertEqual(m["reasons"], ["article text names Hawaiʻi Appleseed"])

    def test_read_page_without_appleseed_is_rejected_and_remembered(self):
        merged = self.make("Local ag rally", "medium", [mw.UNCHECKED])
        self.pages["https://example.org/a"] = "A story about farms. " * 60
        checked = {}
        mw.settle(merged, {"items": []}, CFG, checked, "2026-09-29", delay=0, out=io.StringIO())
        self.assertEqual(merged, {})
        self.assertEqual(len(checked), 1)

    def test_unreadable_page_keeps_unchecked_medium_but_not_low(self):
        merged = self.make("Local ag rally", "medium", [mw.UNCHECKED])
        mw.settle(merged, {"items": []}, CFG, {}, "2026-09-29", delay=0, out=io.StringIO())
        self.assertEqual(list(merged.values())[0]["confidence"], "medium")

    def test_known_story_is_not_refetched(self):
        merged = self.make("Local ag rally", "medium", [mw.UNCHECKED])
        iid = mw.story_id(next(iter(merged)))
        mw.fetch_article_text = lambda u: self.fail("fetched a known story")
        mw.settle(merged, {"items": [{"id": iid}]}, CFG, {}, "2026-09-29", delay=0, out=io.StringIO())


class State(unittest.TestCase):
    def rec(self, title, conf="high", on_site=""):
        return {"title": title, "outlet": "O", "url": "https://o.org/a", "published_iso": "2026-09-27T00:00:00Z",
                "confidence": conf, "reasons": ["r"], "sources": ["bing"], "on_site": on_site}

    def test_status_is_never_overwritten(self):
        state = {"items": []}
        key = mw.title_key("Story one")
        fresh = mw.update_state(state, {key: self.rec("Story one")}, "2026-09-27T00:00:00Z")
        self.assertEqual(len(fresh), 1)
        state["items"][0]["status"] = "ignore"
        fresh = mw.update_state(state, {key: self.rec("Story one", on_site="/in-the-news/x")}, "2026-09-28T00:00:00Z")
        self.assertEqual(fresh, [])
        self.assertEqual(state["items"][0]["status"], "ignore")

    def test_digest_leaves_out_what_is_on_site_and_below_threshold(self):
        s = {"items": []}
        recs = {mw.title_key(t): self.rec(t, c, o) for t, c, o in
                (("Fresh story", "high", ""), ("Posted story", "high", "/in-the-news/x"), ("Weak story", "low", ""))}
        fresh = mw.update_state(s, recs, "2026-09-27T00:00:00Z")
        text, n = mw.render_digest(fresh, "2026-09-27", "medium")
        self.assertEqual(n, 1)
        self.assertIn("Fresh story", text)
        self.assertNotIn("Posted story", text)
        self.assertNotIn("Weak story", text)

    def test_checked_cache_expires(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "c.json"
            today = dt.date.today()
            mw.save_checked({"a": today.isoformat(), "b": (today - dt.timedelta(days=30)).isoformat()}, p)
            self.assertEqual(list(mw.load_checked(p)), ["a"])


if __name__ == "__main__":
    unittest.main(verbosity=1)
