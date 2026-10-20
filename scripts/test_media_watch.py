#!/usr/bin/env python3
"""Offline tests for scripts/media_watch.py. Run: python3 scripts/test_media_watch.py"""
import base64
import datetime as dt
import io
import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import media_watch as mw  # noqa: E402

CFG = json.loads(mw.CONFIG_PATH.read_text(encoding="utf-8"))
STAFF = ["Will White", "Devin Thomas", "Will Caron", "Christy MacPherson", "Genevieve Mumma"]   # all but the last are staff_ambiguous in the config

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


ALERT = """<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><entry>
<title type="html">&lt;b&gt;Hawaii Appleseed&lt;/b&gt; urges lawmakers on SNAP</title>
<link href="https://www.google.com/url?rct=j&amp;sa=t&amp;url=https://www.example.org/snap-story&amp;ct=ga&amp;cd=x"/>
<published>2026-09-28T10:00:00Z</published><content type="html">&lt;b&gt;Hawaii Appleseed&lt;/b&gt; said</content></entry></feed>"""


class Feeds(unittest.TestCase):
    def test_feed_urls_pages(self):
        self.assertEqual(mw.feed_urls({"url": "https://a.test/feed/"}), ["https://a.test/feed/"])
        self.assertEqual(mw.feed_urls({"url": "https://a.test/feed/", "pages": 3}),
                         ["https://a.test/feed/", "https://a.test/feed/?paged=2", "https://a.test/feed/?paged=3"])
        self.assertEqual(mw.feed_urls({"url": "https://a.test/f?x=1", "pages": 2})[1], "https://a.test/f?x=1&paged=2")

    def test_unwrap_google_alert_link(self):
        self.assertEqual(mw.unwrap_redirect("https://www.google.com/url?rct=j&url=https://e.org/a&ct=ga"), "https://e.org/a")
        self.assertEqual(mw.unwrap_redirect("https://e.org/a"), "https://e.org/a")

    def test_alert_title_loses_its_markup(self):
        (a,) = mw.parse_feed(ALERT, "Alert")
        self.assertEqual(a["title"], "Hawaii Appleseed urges lawmakers on SNAP")

    def test_appleseed_must_be_near_hawaii(self):
        far = ("Texas Appleseed sued the state over school discipline. " + "Filler sentence. " * 40 +
               "Separately, lawmakers in Honolulu met on Tuesday.")
        self.assertIsNone(mw.verify_article(far, CFG))
        self.assertEqual(mw.verify_article("Appleseed, the Honolulu advocacy group, said", CFG)[0], "medium")


class Crawl(unittest.TestCase):
    """crawl_feeds end to end, with the network stubbed."""

    def setUp(self):
        self._g, self._f = mw.http_get, mw.fetch_article
        self.feeds, self.pages, self.page_dates = {}, {}, {}
        mw.http_get = lambda url, **k: self.feeds[url]
        mw.fetch_article = lambda u: (self.pages.get(u), self.page_dates.get(u))
        self.cutoff = dt.datetime(2026, 9, 1, tzinfo=dt.timezone.utc)

    def tearDown(self):
        mw.http_get, mw.fetch_article = self._g, self._f

    @staticmethod
    def rss(*stories):
        body = "".join(f"<item><title>{t}</title><link>{u}</link><pubDate>Mon, 28 Sep 2026 10:00:00 GMT</pubDate>"
                       f"<description>short</description></item>" for t, u in stories)
        return f'<?xml version="1.0"?><rss version="2.0"><channel>{body}</channel></rss>'

    def run_crawl(self, cfg, checked=None):
        checked = {} if checked is None else checked
        out = io.StringIO()
        found = mw.crawl_feeds({**CFG, **cfg}, STAFF, self.cutoff, checked, "2026-09-29", delay=0, out=out)
        return found, checked, out.getvalue()

    def test_hit_is_found_and_miss_is_remembered(self):
        self.feeds["https://a.test/f"] = self.rss(("Yes story", "https://a.test/1"), ("No story", "https://a.test/2"))
        self.pages["https://a.test/1"] = "Hawaiʻi Appleseed said so. " * 80
        self.pages["https://a.test/2"] = "Nothing relevant. " * 120
        found, checked, _ = self.run_crawl({"outlet_feeds": [{"name": "A", "url": "https://a.test/f"}], "alert_feeds": []})
        self.assertEqual([f["title"] for f in found], ["Yes story"])
        self.assertEqual(list(checked), [mw.story_id(mw.title_key("No story"))])   # only the miss

    def test_pages_are_fetched_and_deduped(self):
        self.feeds["https://a.test/f"] = self.rss(("One", "https://a.test/1"))
        self.feeds["https://a.test/f?paged=2"] = self.rss(("One", "https://a.test/1"), ("Two", "https://a.test/2"))
        self.pages["https://a.test/1"] = self.pages["https://a.test/2"] = "Hawaiʻi Appleseed said so. " * 80
        found, _, _ = self.run_crawl({"outlet_feeds": [{"name": "A", "url": "https://a.test/f", "pages": 2}], "alert_feeds": []})
        self.assertEqual(sorted(f["title"] for f in found), ["One", "Two"])

    def test_failed_first_page_warns_and_later_page_failure_is_quiet(self):
        mw.http_get = lambda url, **k: (_ for _ in ()).throw(RuntimeError("boom"))
        found, _, log = self.run_crawl({"outlet_feeds": [{"name": "Dead", "url": "https://dead.test/f"}], "alert_feeds": []})
        self.assertEqual(found, [])
        self.assertIn("feed Dead failed", log)

    def test_read_cap_defers_rather_than_forgets(self):
        old = mw.MAX_ARTICLE_READS
        mw.MAX_ARTICLE_READS = 1
        try:
            self.feeds["https://a.test/f"] = self.rss(("First", "https://a.test/1"), ("Second", "https://a.test/2"))
            self.pages["https://a.test/1"] = self.pages["https://a.test/2"] = "Nothing here. " * 150
            found, checked, log = self.run_crawl({"outlet_feeds": [{"name": "A", "url": "https://a.test/f"}], "alert_feeds": []})
        finally:
            mw.MAX_ARTICLE_READS = old
        self.assertEqual(list(checked), [mw.story_id(mw.title_key("First"))])   # Second was NOT marked read
        self.assertIn("1 left for the next run", log)

    def test_alert_unreadable_page_is_kept_unchecked_and_readable_miss_is_dropped(self):
        wrap = lambda u: "https://www.google.com/url?rct=j&amp;url=" + u
        self.feeds["https://g.test/alert"] = self.rss(("Paywalled story", wrap("https://p.test/1")),
                                                      ("Engine noise", wrap("https://p.test/2")))
        self.pages["https://p.test/2"] = "A story about farms. " * 120
        found, checked, _ = self.run_crawl({"outlet_feeds": [], "alert_feeds": [{"name": "Alert", "url": "https://g.test/alert"}]})
        self.assertEqual([f["title"] for f in found], ["Paywalled story"])
        self.assertEqual(found[0]["url"], "https://p.test/1")
        self.assertEqual(found[0]["reasons"], [mw.UNCHECKED])
        self.assertIn(mw.story_id(mw.title_key("Engine noise")), checked)


YOUTUBE = """<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom" xmlns:media="http://search.yahoo.com/mrss/">
<entry><title>Insights: housing costs</title><link rel="alternate" href="https://www.youtube.com/watch?v=abc"/>
<published>2026-09-28T01:00:00+00:00</published>
<media:group><media:title>x</media:title><media:description>Guests: Will White, executive director of Hawaiʻi Appleseed.</media:description></media:group>
</entry></feed>"""

WP_ROWS = [
    {"date_gmt": "2026-09-27T20:00:00", "link": "https://www.civilbeat.org/2026/09/will-caron-artful-dodgers/",
     "title": {"rendered": "Will Caron: Artful &amp; Dodgers"}, "content": {"rendered": "<p>Column body.</p>"}},
    {"date_gmt": "", "link": "", "title": {"rendered": "no link"}, "content": {"rendered": ""}},
]

SEARCH_HTML = """<html><body><nav><a href="/news/">News</a><a href="/about-us/">About us and our story here</a></nav>
<a href="/2026/09/16/editorial/island-voices/column-isle-wealth-flight-fears-are-overblown/">Column: Isle wealth flight fears are overblown</a>
<a href="/2026/09/16/editorial/island-voices/column-isle-wealth-flight-fears-are-overblown/"><img src="x"></a>
<a href="/category/hawaii-news/topic-page-with-a-long-title-for-a-category/">A category page with a long enough title</a>
<a href="https://elsewhere.com/2026/09/16/some-other-site-story-with-long-slug/">A story on another site entirely, long title</a>
<a href="/local-news/2026-09-15/local-ag-food-groups-rally-vote-for-oahu-food-security-fund">Local ag, food groups rally public to vote for food fund</a>
</body></html>"""

ITUNES = {"results": [
    {"trackName": "Covering the Cost", "trackViewUrl": "https://podcasts.apple.com/us/podcast/x/id1?i=2",
     "releaseDate": "2026-09-28T07:00:00Z", "collectionName": "Covering the Cost",
     "description": "New tool shows disparities. Guest: Will White, executive director, Hawaiʻi Appleseed."},
    {"trackName": "Untitled", "trackViewUrl": "", "releaseDate": "2026-09-28T07:00:00Z"}]}


class Dates(unittest.TestCase):
    def test_url_date(self):
        self.assertEqual(mw.url_date("https://a.com/2026/09/16/x/").date(), dt.date(2026, 9, 16))
        self.assertEqual(mw.url_date("https://a.com/local-news/2026-09-15/x").date(), dt.date(2026, 9, 15))
        self.assertEqual(mw.url_date("https://a.com/2026/09/slug").date(), dt.date(2026, 9, 30))   # no day: month's end
        self.assertIsNone(mw.url_date("https://a.com/about-us"))

    def test_page_date_and_timezone(self):
        # a -10:00 (Hawaii) time must land on the right UTC hour, not be labelled Z as-is
        self.assertEqual(mw.page_date('<meta property="article:published_time" content="2026-09-20T10:11:07-10:00">'),
                         "2026-09-20T20:11:07Z")
        self.assertEqual(mw.page_date('<script type="application/ld+json">{"datePublished":"2026-08-01T00:00:00Z"}</script>'),
                         "2026-08-01T00:00:00Z")
        self.assertIsNone(mw.page_date("<p>no date here</p>"))


class Names(unittest.TestCase):
    def test_has_name(self):
        self.assertTrue(mw.has_name("said Will White, director", "Will White"))
        self.assertFalse(mw.has_name("Will White House officials said", "Will White"))
        self.assertFalse(mw.has_name("will white water", "Will White"))
        self.assertTrue(mw.has_name("Kamakani Albano spoke", "Kamakani Albano"))

    def test_role_cue_looks_beside_the_name_not_at_the_topic(self):
        self.assertTrue(mw.role_cue("said Devin Thomas, director of tax", "Devin Thomas", CFG))
        self.assertTrue(mw.role_cue("policy analyst Devin Thomas said", "Devin Thomas", CFG))
        self.assertFalse(mw.role_cue("Devin Thomas on Hawaii tax policy", "Devin Thomas", CFG))


class Sources(unittest.TestCase):
    def test_youtube_description_is_parsed_from_media_group(self):
        (v,) = mw.parse_feed(YOUTUBE, "PBS")
        self.assertEqual(v["url"], "https://www.youtube.com/watch?v=abc")
        self.assertIn("executive director of Hawaiʻi Appleseed", v["snippet"])

    def test_wp_rows(self):
        (r,) = mw.parse_wp_rows(WP_ROWS, {"name": "Civil Beat"})       # the row without a link is dropped
        self.assertEqual((r["title"], r["published"], r["complete"]), ("Will Caron: Artful & Dodgers", "2026-09-27T20:00:00Z", True))
        self.assertEqual(r["snippet"], "Column body.")

    def test_html_search_links_keeps_headlines_only(self):
        links = mw.html_search_links(SEARCH_HTML, "https://www.staradvertiser.com/?s=Appleseed")
        self.assertEqual([l["title"] for l in links],
                         ["Column: Isle wealth flight fears are overblown",
                          "Local ag, food groups rally public to vote for food fund"])   # no menu, category, other host, image dup
        self.assertTrue(all(l["needs_date"] for l in links))

    def test_html_search_that_mentions_the_term_but_yields_no_links_is_reported_as_broken(self):
        _g = mw.http_get
        try:
            mw.http_get = lambda url, **k: "<html>" + "Appleseed result card. " * 12 + "</html>"
            with self.assertRaises(ValueError):
                mw.search_html({"name": "X", "url": "https://x.test/?s={q}"}, "Appleseed", None, 0)
            mw.http_get = lambda url, **k: "<html><input value='Appleseed'>No results found.</html>"
            self.assertEqual(mw.search_html({"name": "X", "url": "https://x.test/?s={q}"}, "Appleseed", None, 0), [])
        finally:
            mw.http_get = _g

    def test_html_search_follows_page_url_dedupes_and_stops_when_a_page_adds_nothing(self):
        _g = mw.http_get
        fetched = []
        p1 = '<a href="/2026/09/20/one-story-with-a-long-enough-slug/">One story with a long enough headline</a>'
        p2 = p1 + '<a href="/2026/09/21/two-story-with-a-long-enough-slug/">Two story with a long enough headline</a>'
        try:
            def fake(url, **k):
                fetched.append(url)
                return {"https://x.test/?s=a+b": p1, "https://x.test/search/a%20b/page/2/?s=a+b": p2,
                        "https://x.test/search/a%20b/page/3/?s=a+b": p2}[url]
            mw.http_get = fake
            outlet = {"name": "X", "url": "https://x.test/?s={q}", "page_url": "https://x.test/search/{qp}/page/{n}/?s={q}", "pages": 5}
            items = mw.search_html(outlet, "a b", None, 0)
            self.assertEqual([i["title"] for i in items],
                             ["One story with a long enough headline", "Two story with a long enough headline"])
            self.assertEqual(len(fetched), 3)                     # page 3 added nothing new, so it stopped
            fetched.clear()
            mw.search_html({"name": "X", "url": "https://x.test/?s={q}"}, "a b", None, 0)   # no page_url: one page only
            self.assertEqual(len(fetched), 1)
        finally:
            mw.http_get = _g

    def test_itunes(self):
        (e,) = mw.parse_itunes(ITUNES)
        self.assertEqual((e["outlet"], e["complete"], e["no_read"]), ("Covering the Cost", True, True))


class Reading(unittest.TestCase):
    """Reader.evaluate and the search stage, with the network stubbed."""

    def setUp(self):
        self._g, self._f = mw.http_get, mw.fetch_article
        self.pages, self.page_dates, self.fetched = {}, {}, []
        mw.fetch_article = lambda u: (self.fetched.append(u), (self.pages.get(u), self.page_dates.get(u)))[1]
        self.cutoff = dt.datetime(2026, 9, 20, tzinfo=dt.timezone.utc)

    def tearDown(self):
        mw.http_get, mw.fetch_article = self._g, self._f

    def reader(self, **k):
        return mw.Reader(CFG, STAFF, self.cutoff, k.pop("checked", {}), "2026-09-29", delay=0, out=io.StringIO(), **k)

    @staticmethod
    def it(title, url, text="", **k):
        return {"title": title, "url": url, "published": "2026-09-28T00:00:00Z", "snippet": text, "outlet": "O",
                "outlet_url": "https://o.test", "source": "search", **k}

    def test_complete_text_is_not_fetched(self):
        r = self.reader()
        found = r.evaluate([self.it("A story", "https://o.test/a", "Hawaiʻi Appleseed said so. " * 5, complete=True)], "t")
        self.assertEqual((len(found), self.fetched), (1, []))

    def test_weak_verdict_earns_a_page_read_that_can_upgrade_it(self):
        # the weekly Civil Beat column: the REST body has no byline bio, the page does
        r = self.reader()
        body = "Column body about panda excess and other things. " * 20
        self.pages["https://o.test/c"] = body + "Will Caron is communications director at Hawaiʻi Appleseed."
        found = r.evaluate([self.it("Will Caron: Panda Excess", "https://o.test/c", body, complete=True)], "t")
        self.assertEqual(self.fetched, ["https://o.test/c"])
        self.assertEqual([f["confidence"] for f in found], ["high"])

    def test_weak_verdict_that_the_page_does_not_back_is_remembered_as_a_miss(self):
        r = self.reader()
        self.pages["https://o.test/w"] = "Nothing about us here. " * 60
        found = r.evaluate([self.it("Will Caron: Panda Excess", "https://o.test/w", "Will Caron column body", complete=True)], "t")
        self.assertEqual(found, [])
        self.assertIn(mw.story_id(mw.title_key("Will Caron: Panda Excess")), r.checked)

    def test_no_read_never_fetches(self):
        r = self.reader()
        r.evaluate([self.it("Video", "https://y.test/v", "Guests: Will Caron", complete=True, no_read=True)], "t")
        self.assertEqual(self.fetched, [])

    def test_old_by_url_is_dropped_without_a_fetch_and_dateless_html_result_needs_a_page_date(self):
        r = self.reader()
        old = self.it("Old story", "https://o.test/2025/01/02/old-story-with-a-long-slug/", published="", needs_date=True)
        undated = self.it("Undated story here", "https://o.test/undated-story-with-a-long-slug/", published="", needs_date=True)
        dated = self.it("Dated story here", "https://o.test/dated-story-with-a-long-slug/", published="", needs_date=True)
        self.pages[dated["url"]] = "Hawaiʻi Appleseed said so. " * 60
        self.page_dates[dated["url"]] = "2026-09-27T00:00:00Z"
        self.pages[undated["url"]] = "Hawaiʻi Appleseed said so. " * 60      # no date anywhere: cannot show it is recent
        found = r.evaluate([old, undated, dated], "t")
        self.assertEqual([f["title"] for f in found], ["Dated story here"])
        self.assertNotIn(old["url"], self.fetched)
        self.assertEqual(found[0]["published_iso"], "2026-09-27T00:00:00Z")

    def test_known_story_is_skipped_by_id_or_url(self):
        first = self.it("Known story", "https://o.test/k", "Hawaiʻi Appleseed. " * 5, complete=True)
        r = self.reader(known={mw.story_id(mw.title_key("Known story"))})
        self.assertEqual(r.evaluate([dict(first)], "t"), [])
        r = self.reader(known={mw.canon_url("https://www.o.test/k")})
        self.assertEqual(r.evaluate([dict(first, title="Different headline")], "t"), [])

    def test_search_stage_runs_each_driver_and_survives_a_failing_outlet(self):
        calls = []

        def fake_get(url, **k):
            calls.append(url)
            if "dead.test" in url:
                raise RuntimeError("HTTP 403 Forbidden")
            if "wp.test" in url:
                return json.dumps([{"date_gmt": "2026-09-28T00:00:00", "link": "https://wp.test/2026/09/a-story",
                                    "title": {"rendered": "A Hawaii story"},
                                    "content": {"rendered": "<p>Said Hawaiʻi Appleseed. </p>" * 3}}])
            if "html.test" in url:
                return SEARCH_HTML.replace("/2026", "https://html.test/2026").replace('"/local-news', '"https://html.test/local-news')
            raise AssertionError(url)

        mw.http_get = fake_get
        cfg = {**CFG, "search_terms": ["Appleseed"], "work_terms": [], "search_staff": False, "outlet_search": [
            {"name": "WP", "type": "wp-rest", "base": "https://wp.test"},
            {"name": "Dead", "type": "wp-rest", "base": "https://dead.test"},
            {"name": "HTML", "type": "html", "url": "https://html.test/?s={q}"}]}
        self.pages["https://html.test/local-news/2026-09-15/local-ag-food-groups-rally-vote-for-oahu-food-security-fund"] = ""
        out = io.StringIO()
        r = mw.Reader(cfg, STAFF, self.cutoff, {}, "2026-09-29", delay=0, out=out)
        found = mw.search_sites(cfg, STAFF, self.cutoff, r, delay=0, out=out)
        self.assertEqual([f["title"] for f in found], ["A Hawaii story"])
        self.assertIn("2/3 outlets answered", out.getvalue())
        self.assertIn("failed: Dead", out.getvalue())

    def test_deep_reads_pages_deep_and_html_outlets_get_only_the_org_term(self):
        urls = []
        mw.http_get = lambda url, **k: (urls.append(url), "<html></html>")[1]
        cfg = {**CFG, "search_terms": ["Appleseed"], "work_terms": ["Hawaii Tax Fairness Coalition"], "search_staff": False,
               "outlet_search": [{"name": "H", "type": "html", "url": "https://h.test/?s={q}",
                                  "page_url": "https://h.test/p/{n}?s={q}", "pages": 1, "pages_deep": 3}]}
        r = mw.Reader(cfg, STAFF, self.cutoff, {}, "2026-09-29", delay=0, out=io.StringIO())
        mw.search_sites(cfg, STAFF, self.cutoff, r, delay=0, out=io.StringIO())
        self.assertEqual(urls, ["https://h.test/?s=Appleseed"])                 # daily: page 1, org term only
        urls.clear()
        # a page with no links ends the paging, so make each page yield a new link
        pages = iter(f'<a href="/2026/09/2{n}/story-number-{n}-with-a-long-slug/">Story number {n} with a long headline here</a>'
                     for n in range(9))
        mw.http_get = lambda url, **k: (urls.append(url), next(pages))[1]
        mw.search_sites(cfg, STAFF, self.cutoff, r, delay=0, out=io.StringIO(), deep=True)
        self.assertEqual(len(urls), 3)                                           # deep: pages_deep result pages

    def test_podcast_search_judges_the_description_and_fetches_nothing(self):
        mw.http_get = lambda url, **k: json.dumps(ITUNES)
        r = self.reader()
        found = mw.search_podcasts({**CFG, "podcast_terms": ["Hawaii Appleseed"]}, self.cutoff, r, delay=0, out=io.StringIO())
        self.assertEqual([(f["title"], f["confidence"]) for f in found], [("Covering the Cost", "high")])
        self.assertEqual(self.fetched, [])

    def test_youtube_feed_is_judged_on_its_description_only(self):
        mw.http_get = lambda url, **k: YOUTUBE
        cfg = {**CFG, "outlet_feeds": [{"name": "PBS", "url": "https://yt.test/f", "read_pages": False}], "alert_feeds": []}
        found = mw.crawl_feeds(cfg, STAFF, self.cutoff, {}, "2026-09-29", delay=0, out=io.StringIO())
        self.assertEqual([f["confidence"] for f in found], ["high"])
        self.assertEqual(self.fetched, [])


class Alerts(unittest.TestCase):
    def test_alert_feeds_come_from_the_environment(self):
        old = os.environ.get("MEDIA_WATCH_ALERT_FEEDS")
        try:
            os.environ["MEDIA_WATCH_ALERT_FEEDS"] = "https://www.google.com/alerts/feeds/1/2\nhttps://www.google.com/alerts/feeds/1/3, junk"
            self.assertEqual([f["name"] for f in mw.env_alert_feeds()], ["Google Alert 1", "Google Alert 2"])
            os.environ.pop("MEDIA_WATCH_ALERT_FEEDS")
            self.assertEqual(mw.env_alert_feeds(), [])
        finally:
            if old is not None:
                os.environ["MEDIA_WATCH_ALERT_FEEDS"] = old

    def test_a_failing_alert_feed_never_prints_its_url(self):
        _g = mw.http_get
        try:
            def boom(url, **k):
                raise RuntimeError(f"{url[:90]}… : HTTP 404 Not Found")
            mw.http_get = boom
            out = io.StringIO()
            r = mw.fetch_feed({"name": "Google Alert 1", "url": "https://www.google.com/alerts/feeds/123456/789"}, True, 0, out)
            self.assertIsNone(r)
            self.assertNotIn("123456", out.getvalue())
            self.assertIn("Google Alert 1", out.getvalue())
        finally:
            mw.http_get = _g


class Interplay(unittest.TestCase):
    def setUp(self):
        self._f = mw.fetch_article
        mw.fetch_article = lambda u: (None, None)                       # a bot-walled outlet: nothing loads
        self.cutoff = dt.datetime(2026, 9, 20, tzinfo=dt.timezone.utc)

    def tearDown(self):
        mw.fetch_article = self._f

    def test_a_story_the_feed_could_not_read_is_still_judged_by_a_source_that_has_the_text(self):
        checked = {}
        r = mw.Reader(CFG, STAFF, self.cutoff, checked, "2026-09-29", delay=0, out=io.StringIO())
        feed_item = {"title": "KHON story", "url": "https://k.test/1", "published": "2026-09-28T00:00:00Z", "snippet": "",
                     "outlet": "KHON2", "outlet_url": "https://k.test", "source": "feed"}
        self.assertEqual(r.evaluate([dict(feed_item)], "feed"), [])
        self.assertTrue(checked[mw.story_id(mw.title_key("KHON story"))].endswith(mw.BLIND))
        r2 = mw.Reader(CFG, STAFF, self.cutoff, checked, "2026-09-29", delay=0, out=io.StringIO())
        rest = dict(feed_item, source="search", complete=True, snippet="Said Hawaiʻi Appleseed. " * 5)
        self.assertEqual([f["title"] for f in r2.evaluate([rest], "search")], ["KHON story"])
        # ...but the feed stage does not keep re-fetching a page that will not load
        r3 = mw.Reader(CFG, STAFF, self.cutoff, checked, "2026-09-29", delay=0, out=io.StringIO())
        self.assertEqual(r3.evaluate([dict(feed_item)], "feed"), [])
        self.assertEqual(r3.reads, 0)

    def test_settle_keeps_an_engine_hit_whose_page_was_blind_but_drops_a_judged_miss(self):
        merged = {}
        for t in ("Blind story", "Judged story"):
            merged[mw.title_key(t)] = {**item(t, url="https://k.test/" + t[:3]), "confidence": "medium", "reasons": [mw.UNCHECKED],
                                       "sources": ["google"], "query": "q"}
        checked = {mw.story_id(mw.title_key("Blind story")): "2026-09-28" + mw.BLIND,
                   mw.story_id(mw.title_key("Judged story")): "2026-09-28"}
        mw.settle(merged, {"items": []}, CFG, checked, "2026-09-29", delay=0, out=io.StringIO())
        self.assertEqual([m["title"] for m in merged.values()], ["Blind story"])

    def test_atom_prefers_the_alternate_link(self):
        atom = ('<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><entry><title>T</title>'
                '<link rel="replies" href="https://x.test/comments"/><link rel="alternate" href="https://x.test/story"/>'
                '<updated>2026-09-28T00:00:00Z</updated></entry></feed>')
        self.assertEqual(mw.parse_feed(atom, "X")[0]["url"], "https://x.test/story")

    def test_a_shallow_busy_feed_warns(self):
        _g = mw.http_get
        try:
            def feed_at(newest):
                items = "".join(f"<item><title>Story {i}</title><link>https://s.test/{i}</link>"
                                f"<pubDate>{email_date(newest - dt.timedelta(minutes=20 * i))}</pubDate></item>" for i in range(12))
                return f'<?xml version="1.0"?><rss version="2.0"><channel>{items}</channel></rss>'
            now = dt.datetime.now(dt.timezone.utc)
            mw.http_get = lambda url, **k: feed_at(now - dt.timedelta(hours=1))
            out = io.StringIO()
            self.assertEqual(len(mw.fetch_feed({"name": "Busy", "url": "https://s.test/f"}, False, 0, out)), 12)
            self.assertIn("reaches back only 4h", out.getvalue())
            # a monthly paper posts its stories in one batch and then goes quiet: no warning
            mw.http_get = lambda url, **k: feed_at(now - dt.timedelta(days=27))
            out = io.StringIO()
            mw.fetch_feed({"name": "Monthly", "url": "https://s.test/f"}, False, 0, out)
            self.assertNotIn("reaches back", out.getvalue())
        finally:
            mw.http_get = _g


def email_date(d):
    import email.utils
    return email.utils.format_datetime(d)


class Merging(unittest.TestCase):
    def test_same_url_under_different_headlines_is_one_story(self):
        a = {**item("Isle wealth flight fears are overblown", url="https://www.staradvertiser.com/2026/09/16/x/"),
             "confidence": "high", "reasons": ["a"], "source": "feed", "query": "q1"}
        b = {**item("Column: Isle wealth flight fears are overblown", url="https://staradvertiser.com/2026/09/16/x"),
             "confidence": "high", "reasons": ["b"], "source": "search", "query": "q2"}
        self.assertEqual(len(mw.merge_found([a, b])), 1)

    def test_state_matches_an_existing_record_by_url(self):
        state = {"items": [{"id": "old", "title": "Old headline", "outlet": "O", "url": "https://o.test/a", "published": "",
                            "confidence": "high", "reasons": ["r"], "sources": ["feed"], "onSite": "", "status": "ignore"}]}
        key = mw.title_key("A different headline")
        m = {"title": "A different headline", "outlet": "O", "url": "https://www.o.test/a/", "published_iso": "",
             "confidence": "high", "reasons": ["r2"], "sources": ["search"], "on_site": ""}
        self.assertEqual(mw.update_state(state, {key: m}, "2026-09-29T00:00:00Z"), [])
        self.assertEqual((len(state["items"]), state["items"][0]["status"]), (1, "ignore"))


class Ignored(unittest.TestCase):
    def test_candidate_qa_pages_are_never_mentions_but_ordinary_stories_still_are(self):
        self.assertTrue(mw.is_ignored({"title": "Candidate Q&A: State House District 26 – Nathan Kenichi Char"}, CFG))
        self.assertTrue(mw.is_ignored({"title": "2026 Election: Arjuna Heim"}, CFG))
        self.assertFalse(mw.is_ignored({"title": "Five housing questions on Oʻahu's 2026 election ballot"}, CFG))   # our own work
        self.assertFalse(mw.is_ignored({"title": "Hawaiʻi Appleseed releases housing report"}, CFG))
        r = mw.Reader(CFG, STAFF, dt.datetime(2026, 9, 20, tzinfo=dt.timezone.utc), {}, "2026-09-29", delay=0, out=io.StringIO())
        base = {"url": "https://c.test/a", "published": "2026-09-28T00:00:00Z", "outlet": "C", "outlet_url": "https://c.test",
                "source": "search", "complete": True,
                "snippet": "His opponents are Janel Fujinaka, Genevieve Mumma and Tony Silva, in Hawaii tax policy. " * 3}
        self.assertEqual(r.evaluate([dict(base, title="Candidate Q&A: State House District 26 – Janel Fujinaka")], "t"), [])
        self.assertEqual(len(r.evaluate([dict(base, title="Election night in Honolulu", url="https://c.test/b")], "t")), 1)
        self.assertEqual(r.seen, 1)                      # the ignored one was never even judged
        self.assertEqual(mw.is_ignored({"title": "Candidate Q&A: x"}, {**CFG, "ignore_titles": []}), False)


class Columns(unittest.TestCase):
    def test_staff_column_is_recognised_by_its_title_prefix(self):
        self.assertTrue(mw.is_staff_column("Will Caron: Artful Dodgers", STAFF))
        self.assertFalse(mw.is_staff_column("Why Will Caron left Honolulu", STAFF))

    def test_digest_and_report_list_columns_apart_from_coverage(self):
        rec = lambda t, c: {"title": t, "url": "https://o.test/" + t[:3], "outlet": "O", "published": "2026-09-27T00:00:00Z",
                            "published_iso": "2026-09-27T00:00:00Z", "confidence": c, "reasons": ["r"], "onSite": "", "on_site": ""}
        items = [rec("Will Caron: Artful Dodgers", "high"), rec("Appleseed report on tax", "high")]
        text, n = mw.render_digest(items, "2026-09-29", "medium", STAFF)
        self.assertEqual(n, 2)
        self.assertLess(text.index("Names Hawaiʻi Appleseed"), text.index("Appleseed report on tax"))
        self.assertLess(text.index("Appleseed report on tax"), text.index("## Written by staff"))
        self.assertLess(text.index("## Written by staff"), text.index("Will Caron: Artful Dodgers"))
        rep = mw.render_report(items, "2026-09-29", 30, STAFF)
        self.assertIn("**1 are not on In the News**", rep)
        self.assertIn("1 more are columns written by staff", rep)


class Report(unittest.TestCase):
    def test_report_splits_by_whether_in_the_news_has_it(self):
        items = [{"title": "New one", "url": "https://o.test/1", "outlet": "O", "published_iso": "2026-09-27T00:00:00Z",
                  "confidence": "high", "reasons": ["names Hawaiʻi Appleseed"], "on_site": ""},
                 {"title": "Posted one", "url": "https://o.test/2", "outlet": "O", "published_iso": "2026-09-26T00:00:00Z",
                  "confidence": "high", "reasons": ["names Hawaiʻi Appleseed"], "on_site": "/in-the-news/x"}]
        text = mw.render_report(items, "2026-09-29", 365)
        self.assertIn("**1 are not on In the News**", text)
        self.assertLess(text.index("New one"), text.index("Posted one"))


class ReviewFixes(unittest.TestCase):
    """One test per defect the code review found."""

    def c(self, title, snippet="", **kw):
        return mw.classify(item(title, snippet), CFG, STAFF, **kw)

    def test_a_namesake_at_another_states_appleseed_is_not_our_staff(self):
        conf = self.c("x", "Will White, policy director at Texas Appleseed, said the court fees are unfair.", full_text=True)
        self.assertEqual(conf[0], "low")                       # "Appleseed" is on the page, but it is not ours
        far = "Texas Appleseed sued the state. " + "Filler sentence about nothing. " * 30 + "Devin Thomas scored twice."
        self.assertEqual(self.c("x", far, full_text=True)[0], "low")   # Appleseed and the name far apart
        self.assertEqual(self.c("Will White of Appleseed on housing")[0], "medium")          # ours: no other org named
        self.assertEqual(self.c("x", "Will White of the Appleseed Center said", full_text=True)[0], "medium")

    def test_a_term_with_regex_metacharacters_is_searched_literally(self):
        # "Keiki (Ride" is not a valid regex: unescaped it raises re.error, which nothing catches
        _g = mw.http_get
        try:
            mw.http_get = lambda url, **k: "<html>" + "a plain page " * 5 + "</html>"
            self.assertEqual(mw.search_html({"name": "X", "url": "https://x.test/?s={q}"}, "Keiki (Ride", None, 0), [])
            mw.http_get = lambda url, **k: "<html>" + "Keiki (Ride result card. " * 12 + "</html>"
            with self.assertRaises(ValueError):                # counted literally, so still flagged as a broken page
                mw.search_html({"name": "X", "url": "https://x.test/?s={q}"}, "Keiki (Ride", None, 0)
        finally:
            mw.http_get = _g

    def test_one_outlets_odd_reply_costs_only_that_outlet(self):
        _g, _f = mw.http_get, mw.fetch_article
        try:
            def fake(url, **k):
                if "odd.test" in url:
                    return json.dumps(["not", "a", "post"])          # a list of strings: AttributeError in the parser
                return json.dumps([{"date_gmt": "2026-09-28T00:00:00", "link": "https://ok.test/2026/09/a-story",
                                    "title": {"rendered": "A story"}, "content": {"rendered": "Hawaiʻi Appleseed said. " * 5}}])
            mw.http_get = fake
            mw.fetch_article = lambda u: (None, None)
            cfg = {**CFG, "search_terms": ["Appleseed"], "work_terms": [], "search_staff": False, "outlet_search": [
                {"name": "Odd", "type": "wp-rest", "base": "https://odd.test"},
                {"name": "OK", "type": "wp-rest", "base": "https://ok.test"}]}
            out = io.StringIO()
            r = mw.Reader(cfg, STAFF, dt.datetime(2026, 9, 20, tzinfo=dt.timezone.utc), {}, "2026-09-29", delay=0, out=out)
            found = mw.search_sites(cfg, STAFF, r.cutoff, r, delay=0, out=out)
            self.assertEqual([f["title"] for f in found], ["A story"])
            self.assertIn("failed: Odd", out.getvalue())
            self.assertIn("AttributeError", out.getvalue())          # named, so a config or markup fault is diagnosable
        finally:
            mw.http_get, mw.fetch_article = _g, _f

    def test_headlines_with_no_latin_letters_are_still_distinct_stories(self):
        r = mw.Reader(CFG, STAFF, dt.datetime(2026, 9, 20, tzinfo=dt.timezone.utc), {}, "2026-09-29", delay=0, out=io.StringIO())
        body = "Said Hawaiʻi Appleseed. " * 5
        a = {"title": "🌱🌱🌱", "url": "https://y.test/a", "published": "2026-09-28T00:00:00Z", "snippet": body, "outlet": "Y",
             "outlet_url": "https://y.test", "source": "feed", "complete": True}
        b = dict(a, title="ハワイの話", url="https://y.test/b")
        self.assertEqual(len(r.evaluate([dict(a), dict(b)], "t")), 2)
        self.assertEqual(len(mw.merge_found([dict(a, confidence="high", reasons=["r"], query="q"),
                                             dict(b, confidence="high", reasons=["r"], query="q")])), 2)

    def test_chrome_markers_do_not_cut_ordinary_prose(self):
        body = "We need to hear more from renters. " * 30 + "One of the most popular programs. " * 10
        tail = "Devin Thomas is director of tax policy at Hawaiʻi Appleseed."
        self.assertIn("Hawaiʻi Appleseed", mw.trim_chrome(body + tail))
        self.assertNotIn("Other story", mw.trim_chrome(body + "Read this next: Other story"))

    def test_a_time_tag_is_not_a_publish_date_and_a_slug_is_not_a_url_date(self):
        self.assertIsNone(mw.page_date('<time datetime="2019-01-01T00:00:00Z">Related story</time>'))
        self.assertIsNone(mw.url_date("https://x.test/2025/12-things-to-know-about-taxes"))
        self.assertEqual(mw.url_date("https://x.test/2025/12/things").date(), dt.date(2025, 12, 31))
        self.assertEqual(mw.url_date("https://x.test/2025/12/05/things").date(), dt.date(2025, 12, 5))

    def test_folding_once_gives_the_same_answers(self):
        raw = "said Kamakani Albano, policy analyst, Will White House staff"
        f = mw._fold(raw)
        for name in ("Kamakani Albano", "Will White", "Devin Thomas"):
            self.assertEqual(mw.has_name(raw, name), mw.has_name(raw, name, f))
        self.assertEqual(mw.role_cue(raw, "Kamakani Albano", CFG), mw.role_cue(raw, "Kamakani Albano", CFG, f))

    def test_the_blind_mark_is_one_rule(self):
        self.assertTrue(mw.is_blind(mw.blind_mark("2026-09-29")))
        self.assertFalse(mw.is_blind("2026-09-29"))
        self.assertTrue(mw.blind_mark("2026-09-29") >= "2026-09-15")     # still pruned by date in load_checked


class RunWiring(unittest.TestCase):
    """run() and main() end to end, in a temp directory, network stubbed."""

    NOW = dt.datetime.now(dt.timezone.utc)

    def setUp(self):
        import tempfile
        from pathlib import Path
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "media-watch").mkdir()
        (self.tmp / "our-team.html").write_text(
            '<div class="ha-ed-content"><h2>Will White</h2></div>'
            '<h3 class="ha-member-name">Genevieve Mumma</h3><h3 class="ha-member-name">Abbey Seitz</h3>')
        self.cfg = {"lookback_days": 3, "org_queries": [], "work_terms": [], "search_terms": ["Appleseed"], "search_staff": False,
                    "podcast_terms": [], "staff_from": "our-team.html", "staff_ambiguous": [], "role_cues": [],
                    "hawaii_context": ["hawaii", "honolulu"], "policy_context": ["tax"], "own_domains": [],
                    "ignore_phrases": [], "min_confidence": "medium", "alert_feeds": [],
                    "outlet_feeds": [{"name": "A", "url": "https://a.test/feed"}],
                    "outlet_search": [{"name": "W", "type": "wp-rest", "base": "https://w.test"}]}
        self.saved = {k: getattr(mw, k) for k in ("ROOT", "WATCH_DIR", "CONFIG_PATH", "STATE_PATH", "DIGEST_PATH",
                                                   "NEWS_PATH", "CHECKED_PATH", "http_get", "fetch_article")}
        mw.ROOT, mw.WATCH_DIR = self.tmp, self.tmp / "media-watch"
        mw.CONFIG_PATH, mw.STATE_PATH = mw.WATCH_DIR / "config.json", mw.WATCH_DIR / "mentions.json"
        mw.DIGEST_PATH, mw.NEWS_PATH = mw.WATCH_DIR / "latest.md", self.tmp / "news.json"
        mw.CHECKED_PATH = mw.WATCH_DIR / ".cache" / "checked.json"
        (self.tmp / "news.json").write_text(json.dumps({"press": []}))
        self.calls = []
        self.web = {"https://a.test/feed": self.rss("Food fund heads to ballot", "https://a.test/1"),
                    "https://w.test/wp-json/": "[]"}
        self.pages = {"https://a.test/1": "Said Hawaiʻi Appleseed on the food fund. " * 30}
        mw.http_get = self.fake_get
        mw.fetch_article = lambda u: (self.pages.get(u), None)
        self.env = dict(os.environ)
        self.addCleanup(self.restore)
        self.write_cfg()

    def restore(self):
        for k, v in self.saved.items():
            setattr(mw, k, v)
        os.environ.clear()
        os.environ.update(self.env)

    def write_cfg(self):
        mw.CONFIG_PATH.write_text(json.dumps(self.cfg))

    def rss(self, title, url):
        import email.utils
        return (f'<?xml version="1.0"?><rss version="2.0"><channel><item><title>{title}</title><link>{url}</link>'
                f'<pubDate>{email.utils.format_datetime(self.NOW)}</pubDate><description>short</description></item>'
                '</channel></rss>')

    def fake_get(self, url, **k):
        self.calls.append(url)
        for prefix, body in self.web.items():
            if url.startswith(prefix):
                if isinstance(body, Exception):
                    raise body
                return body
        raise RuntimeError(f"{url} : HTTP 404 Not Found")

    def run_it(self, **k):
        out = io.StringIO()
        code, n = mw.run(delay=0, out=out, **k)
        return code, n, out.getvalue()

    def test_a_normal_run_writes_state_digest_and_the_checked_cache(self):
        code, n, log = self.run_it(only=["feeds"])
        self.assertEqual((code, n), (0, 1))
        state = json.loads(mw.STATE_PATH.read_text())
        self.assertEqual([i["title"] for i in state["items"]], ["Food fund heads to ballot"])
        self.assertIn("Food fund heads to ballot", mw.DIGEST_PATH.read_text())
        self.assertTrue(mw.CHECKED_PATH.exists())

    def test_a_second_run_finds_nothing_new(self):
        self.run_it(only=["feeds"])
        code, n, log = self.run_it(only=["feeds"])
        self.assertEqual(n, 0)

    def test_report_mode_lists_known_stories_and_writes_no_state(self):
        self.run_it(only=["feeds"])                                   # now "known"
        before, digest = mw.STATE_PATH.read_bytes(), mw.DIGEST_PATH.read_bytes()
        mw.CHECKED_PATH.unlink()
        report = self.tmp / "inventory.md"
        code, n, log = self.run_it(only=["feeds"], report=str(report))
        self.assertIn("Food fund heads to ballot", report.read_text())    # a known story is still in an inventory
        self.assertEqual((mw.STATE_PATH.read_bytes(), mw.DIGEST_PATH.read_bytes()), (before, digest))
        self.assertFalse(mw.CHECKED_PATH.exists())

    def test_only_runs_just_the_named_stages(self):
        self.run_it(only=["search"])
        self.assertTrue(all("a.test" not in c for c in self.calls))
        self.assertTrue(any("w.test" in c for c in self.calls))

    def test_a_dead_stage_is_named_in_github_output_yet_the_other_stages_results_are_saved(self):
        self.web["https://w.test/wp-json/"] = RuntimeError("https://w.test/… : HTTP 403 Forbidden")
        out_file = self.tmp / "gh_output"
        os.environ["GITHUB_OUTPUT"] = str(out_file)
        code, n, log = self.run_it(only=["feeds", "search"])
        self.assertEqual((code, n), (0, 1))                          # the feed story is still found and saved
        self.assertEqual(len(json.loads(mw.STATE_PATH.read_text())["items"]), 1)
        self.assertIn("dead=search", out_file.read_text())
        self.assertIn("::error::no answer from any source in: search", log)

    def test_a_healthy_run_reports_no_dead_stage(self):
        out_file = self.tmp / "gh_output"
        os.environ["GITHUB_OUTPUT"] = str(out_file)
        self.run_it(only=["feeds", "search"])
        self.assertIn("dead=\n", out_file.read_text())

    def test_alert_feeds_in_the_environment_are_read_and_unwrapped(self):
        self.cfg["outlet_feeds"] = []
        self.write_cfg()
        os.environ["MEDIA_WATCH_ALERT_FEEDS"] = "https://alerts.test/feed/1"
        self.web["https://alerts.test/feed/1"] = ALERT.replace("2026-09-28T10:00:00Z", self.NOW.strftime("%Y-%m-%dT%H:%M:%SZ"))
        self.pages["https://www.example.org/snap-story"] = "Hawaiʻi Appleseed urged lawmakers on SNAP. " * 30
        code, n, log = self.run_it(only=["feeds"])
        self.assertEqual(n, 1)
        self.assertEqual(json.loads(mw.STATE_PATH.read_text())["items"][0]["url"], "https://www.example.org/snap-story")

    def test_main_rejects_an_unknown_stage(self):
        import contextlib
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as cm:
                mw.main(["--only", "bogus"])
        self.assertEqual(cm.exception.code, 2)


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

    def test_staff_with_appleseed(self):
        self.assertEqual(self.c("Will White of Appleseed on housing")[0], "medium")

    def test_distinctive_name_needs_only_hawaii_policy_context(self):
        conf, reasons, _ = self.c("x", "said Genevieve Mumma of the hunger network on Hawaii food policy", full_text=True)
        self.assertEqual(conf, "medium")
        self.assertIn("does not name Appleseed", reasons[0])
        self.assertEqual(self.c("Genevieve Mumma on Hawaii tax policy")[0], "medium")
        self.assertEqual(self.c("Genevieve Mumma wins the marathon")[0], "low")   # no Hawaii/policy context

    def test_ambiguous_name_needs_a_job_title(self):
        # common name: context alone proves nothing (the candidate, the footballer, the White House)
        self.assertEqual(self.c("Devin Thomas on Hawaii tax policy")[0], "low")
        self.assertEqual(self.c("Devin Thomas scores twice")[0], "low")
        self.assertEqual(self.c("Will White on the Hawaii budget")[0], "low")
        # the Civil Beat candidate Q&A that turned up in the inventory: Hawaii and tax, but no job title
        self.assertEqual(self.c("x", "Christy MacPherson, who lost to Sen. Donna Kim in Honolulu, wants a tax cut",
                                full_text=True)[0], "low")
        conf, reasons, _ = self.c("Devin Thomas, director of tax policy, on the Hawaii budget")
        self.assertEqual(conf, "medium")
        self.assertIn("job title", reasons[0])

    def test_name_followed_by_house_is_not_a_person(self):
        self.assertIsNone(self.c("x", "Will White House officials comment on the Hawaii tax bill?"))

    def test_staff_names_are_case_sensitive(self):
        self.assertIsNone(self.c("the tide will white-cap soon", "will white water rafting in Hawaii on a budget"))

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
