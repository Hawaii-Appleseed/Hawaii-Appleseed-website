#!/usr/bin/env python3
"""
Media watch: find stories, podcast episodes and videos that mention Hawaiʻi
Appleseed, its work, or its staff, and say which ones the In the News page does
not carry yet.

Four stages, because each has a blind spot the others cover (--only picks some):
  engines   Google News and Bing News RSS, one query per phrase and per staff
            name. Headline and lede only, and a story two engines both return is
            judged once. Links from Google are opaque redirects; Bing's are real.
  feeds     each outlet's own RSS (config outlet_feeds), every new story read in
            full, once. Finds a body-only mention ("said Devin Thomas of Hawaiʻi
            Appleseed"). Also YouTube channel feeds, judged on the description,
            and Google Alerts feeds (alert_feeds / $MEDIA_WATCH_ALERT_FEEDS).
  search    each outlet's OWN search (config outlet_search): full text, years
            deep, indifferent to how shallow its feed is. WordPress REST, BLOX
            RSS, or a site-search page. Works around outlets that bot-wall their
            article pages (KHON2).
  podcasts  Apple's podcast directory, which matches episode descriptions.
GDELT was left out on purpose: its own rate limit answers with a plain-text
notice that reads as "zero results", so a quiet day and a blocked day look the
same. See Legislative-Research-Tool/testimony/media.py for that history.

Every source ends in the same Reader, which decides for each story WHY it
matched and how sure that is:
    high    the article says "Hawaiʻi Appleseed"
    medium  "Appleseed" within ~150 characters of a Hawaiʻi word; a staff name
            with Appleseed; a distinctive staff name with Hawaiʻi and policy
            context; a common staff name (config staff_ambiguous) with a job
            title beside it; or one of config work_terms
    low     a staff name and nothing else (a stranger who shares the name looks
            exactly like this) — read the page for the org name, else DROPPED
The confidence rules, and why each exists, are in classify(); the measured
recall (119 of 125 readable stories on In the News) is in the README.

What it does each run:
  1. Reads search terms from media-watch/config.json and the staff names from
     our-team.html (so a new hire is watched the day the team page lists them).
  2. Runs the stages, keeps stories inside the lookback window.
  3. De-duplicates across sources (by headline and by URL) and against
     media-watch/mentions.json.
  4. Checks each story against news.json's `press` items (the In the News
     page) so the digest lists only stories nobody has posted yet.

Outputs:
  media-watch/mentions.json   every kept story, with status. The script never
                              overwrites `status`; staff may set it by hand
                              ("added", "ignore") to stop a story resurfacing.
  media-watch/latest.md       the digest of stories first seen this run
                              (only written when there are some). Columns that
                              carry a staff member's name as a title prefix are
                              listed apart, under "Written by staff".

The repo is PUBLIC and Pages serves the whole tree, so mentions.json is public.
That is why low-confidence matches are never written to it, and why Google
Alerts feed URLs (which embed the owner's account id) come from a secret.

Usage:
    python3 scripts/media_watch.py                 # a normal run
    python3 scripts/media_watch.py --days 30       # look back a month
    python3 scripts/media_watch.py --dry-run       # search and report, write nothing
    python3 scripts/media_watch.py --only search,podcasts --days 365 --deep --report inventory.md
                                                   # a one-off inventory, state untouched
Exit codes: 0 ok (partial source failures print warnings), 2 every engine query failed.
"""
import argparse
import base64
import calendar
import concurrent.futures
import datetime as dt
import difflib
import email.utils
import hashlib
import html
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
WATCH_DIR = ROOT / "media-watch"
CONFIG_PATH = WATCH_DIR / "config.json"
STATE_PATH = WATCH_DIR / "mentions.json"
DIGEST_PATH = WATCH_DIR / "latest.md"
NEWS_PATH = ROOT / "news.json"
CHECKED_PATH = WATCH_DIR / ".cache" / "checked.json"   # gitignored; the workflow keeps it in the Actions cache

UA = "Mozilla/5.0 (compatible; HawaiiAppleseedMediaWatch/1.0; +https://hiappleseed.org)"
RANK = {"low": 0, "medium": 1, "high": 2}
REQUEST_DELAY = 1.0  # seconds between requests; both endpoints are unofficial

# ---------------------------------------------------------------- text helpers


def norm(s):
    """Lowercase, strip accents, and fold every spelling of Hawaiʻi together
    (proper ʻokina, ASCII apostrophe, curly quote, or none).

    The possessive goes first: a possessive apostrophe-s must vanish
    ("appleseed", not "appleseeds"), while an apostrophe standing in for the
    ʻokina must vanish without eating the letter after it ("hawaii").
    """
    s = html.unescape(s or "")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = re.sub(r"[ʻʼ’'‘`]s\b", "", s)   # HPR writes "Appleseedʻs": the ʻokina used as an apostrophe
    s = re.sub(r"[ʻʼ’'‘`]", "", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return s.strip()


def has_phrase(text, phrase):
    """Whole-word phrase test on already-normalised text."""
    p = norm(phrase)
    return bool(p) and re.search(r"(?<![a-z0-9])" + re.escape(p) + r"(?![a-z0-9])", text) is not None


def near(text, anchor, terms, window=150):
    """True if any of `terms` sits within `window` characters of `anchor`, on
    already-normalised text. A national article that names Texas Appleseed in
    one paragraph and Hawaii in another is not about us; one that puts them in
    the same sentence is."""
    a = norm(anchor)
    for m in re.finditer(r"(?<![a-z0-9])" + re.escape(a) + r"(?![a-z0-9])", text):
        seg = text[max(0, m.start() - window): m.end() + window]
        if any(has_phrase(seg, w) for w in terms):
            return True
    return False


def _fold(raw):
    """Accent- and ʻokina-folded text with its case kept, for proper-name matching."""
    t = unicodedata.normalize("NFKD", html.unescape(raw or ""))
    return re.sub(r"[ʻʼ]", "", "".join(c for c in t if not unicodedata.combining(c)))


# "Will White House officials said": a sentence, not a person. The one
# collision that actually turned up (Civil Beat, twelve-month inventory).
NOT_A_NAME = re.compile(r"\s+House\b")


def name_windows(raw, name, before=0, after=0, folded=None):
    """The text around each occurrence of a person's full name as a capitalised
    proper name. Case matters: "will white" is ordinary English, "Will White"
    is a person. Accents and the ʻokina are folded so "Kamakani Albano"
    matches either way. Pass `folded=_fold(raw)` when asking about many names
    of the same text: folding a whole article is not free."""
    t = _fold(raw) if folded is None else folded
    pat = re.compile(r"(?<![A-Za-z])" + r"\s+".join(re.escape(w) for w in name.split()) + r"(?![A-Za-z])")
    return [t[max(0, m.start() - before): m.end() + after]
            for m in pat.finditer(t) if not NOT_A_NAME.match(t, m.end())]


def has_name(raw, name, folded=None):
    return bool(name_windows(raw, name, folded=folded))


def role_cue(raw, name, cfg, folded=None):
    """Is the name written with a job title beside it ("Name, director of…",
    "policy analyst Name")? That is what separates a quoted advocate from a
    stranger who shares the name, when the org is not named."""
    cues = cfg.get("role_cues", [])
    for w in name_windows(raw, name, before=40, after=80, folded=folded):
        nw = norm(w)
        if any(has_phrase(nw, c) for c in cues):
            return True
    return False


# Words that can precede "Appleseed" without naming another organisation
# ("The Appleseed report", "at Appleseed"); anything else capitalised, that is
# not Hawaii, is another state's Appleseed (Texas Appleseed, Georgia Appleseed).
NOT_A_STATE = {"the", "our", "at", "with", "of", "and", "by", "for", "from", "in", "on", "to", "a", "an", "its",
               "their", "said", "says", "hawaii", "hawai"}


def appleseed_beside(name, raw, cfg, folded=None):
    """Is one of OUR Appleseeds within ~150 characters of the name? "Will White
    of Appleseed" yes; "Will White, policy director at Texas Appleseed" no, and
    neither is a page that names Appleseed in one paragraph and a namesake in
    another. Matters most for a common name, where it is the only thing
    separating our staff member from a stranger."""
    for w in name_windows(raw, name, before=150, after=150, folded=folded):
        for m in re.finditer(r"appleseed", w, re.I):
            prev = re.search(r"([A-Za-z]+)\s+$", w[:m.start()])
            if prev is None or prev.group(1).lower() in NOT_A_STATE or not prev.group(1)[:1].isupper():
                return True
    return False


def strip_tags(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def title_key(title):
    return re.sub(r"\s", "", norm(title))[:90]


def story_key(item):
    """What identifies a story: its headline, or its URL when the headline has no
    Latin letters (an emoji-only video title, a Japanese headline). Without the
    fallback every such story shares the id of the empty string."""
    return title_key(item["title"]) or canon_url(item["url"])


def canon_url(url):
    """Comparable form of an article URL: no scheme, www, tracking, fragment."""
    try:
        u = urllib.parse.urlsplit(url)
    except ValueError:
        return url
    host = u.netloc.lower()
    host = host[4:] if host.startswith("www.") else host
    q = [(k, v) for k, v in urllib.parse.parse_qsl(u.query)
         if not k.lower().startswith("utm_") and k.lower() not in ("fbclid", "gclid", "ref", "oc")]
    return host + u.path.rstrip("/") + ("?" + urllib.parse.urlencode(q) if q else "")


def host_of(url):
    try:
        h = urllib.parse.urlsplit(url).netloc.lower()
    except ValueError:
        return ""
    return h[4:] if h.startswith("www.") else h


def parse_date(s):
    if not s:
        return None
    try:
        d = email.utils.parsedate_to_datetime(s)
    except (TypeError, ValueError):
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    return d.astimezone(dt.timezone.utc)


def decode_google_url(url):
    """Older Google News article ids embed the real URL in base64. Newer ones
    do not, and resolving those takes a second request per story — not worth
    it, since the opaque link still redirects for a human. Best effort only."""
    m = re.search(r"/articles/([A-Za-z0-9_-]+)", url)
    if not m:
        return None
    tok = m.group(1)
    try:
        raw = base64.urlsafe_b64decode(tok + "=" * (-len(tok) % 4))
    except (ValueError, TypeError):
        return None
    found = re.search(rb"https?://[\x21-\x7e]+", raw)
    return found.group(0).decode("ascii") if found else None


def resolve_google(url):
    """Real article URL behind a Google News link, or None. Two requests: the
    article shell carries a signature and timestamp, and batchexecute swaps
    them for the destination. Unofficial and it has changed before, so every
    failure quietly leaves the opaque link in place."""
    m = re.search(r"/articles/([A-Za-z0-9_-]+)", url)
    if not m:
        return None
    gid = m.group(1)
    try:
        page = http_get(f"https://news.google.com/rss/articles/{gid}", retries=0)
        sg = re.search(r'data-n-a-sg="([^"]+)"', page)
        ts = re.search(r'data-n-a-ts="([^"]+)"', page)
        if not (sg and ts):
            return None
        inner = json.dumps(["garturlreq", [["X", "X", ["X", "X"], None, None, 1, 1, "US:en", None, 1, None,
                                            None, None, None, None, 0, 1], "X", "X", 1, [1, 1, 1], 1, 1, None,
                                           0, 0, None, 0], gid, int(ts.group(1)), sg.group(1)])
        body = urllib.parse.urlencode({"f.req": json.dumps([[["Fbv4je", inner, None, "generic"]]])}).encode()
        req = urllib.request.Request(
            "https://news.google.com/_/DotsSplashUi/data/batchexecute", data=body,
            headers={"User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"})
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read().decode("utf-8", "replace")
        real = json.loads(json.loads(raw.split("\n\n")[1])[0][2])[1]
        return real if isinstance(real, str) and real.startswith("http") else None
    except (RuntimeError, urllib.error.URLError, TimeoutError, OSError, ValueError, IndexError, TypeError, KeyError):
        return None


# Where an article page says when it was published, most reliable first.
PAGE_DATES = [
    re.compile(r'<meta[^>]+(?:property|name|itemprop)=["\'](?:article:published_time|og:published_time|'
               r'datePublished|pubdate|publishdate|parsely-pub-date|date)["\'][^>]*?content=["\']([^"\']+)', re.I),
    re.compile(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]*?(?:property|name|itemprop)='
               r'["\'](?:article:published_time|datePublished)["\']', re.I),
    re.compile(r'"datePublished"\s*:\s*"([^"]+)"'),
]   # no <time> fallback: the first one on a page is as likely a "related story" as the article


def page_date(raw):
    for rx in PAGE_DATES:
        for m in rx.finditer(raw):
            d = parse_any_date(m.group(1))
            if d is not None:
                return d.strftime("%Y-%m-%dT%H:%M:%SZ")
    return None


# /2026/09/16/ or /2026-09-15/ or /2026/09/slug. A month with no day must be
# followed by a slash: /2025/12-things (a slug) is not a date.
URL_DATE = re.compile(r"/(20\d\d)[/-](0[1-9]|1[0-2])(?:[/-](0[1-9]|[12]\d|3[01])(?=[/-]|$|\D)|(?=/|$))")


def url_date(url):
    """The date an article's URL carries (/2026/09/16/, /2026-09-15/, /2026/09/),
    or None. With no day it is the month's last day, so a September story is
    never judged older than a cutoff that falls late in September."""
    m = URL_DATE.search(urllib.parse.urlsplit(url).path)
    if not m:
        return None
    y, mo = int(m.group(1)), int(m.group(2))
    day = int(m.group(3)) if m.group(3) else calendar.monthrange(y, mo)[1]
    return dt.datetime(y, mo, day, tzinfo=dt.timezone.utc)


LAST_FAILURE = {}   # url -> why the last fetch_article(url) returned no text; read by Reader to say what it could not read


def ascii_url(url):
    """`url` with any non-ASCII in its path/query percent-encoded. urllib cannot
    send a raw ʻokina (hawaiʻi-…); it raises before any request and the page
    looked unreadable. Existing %-escapes are left alone."""
    s = urllib.parse.urlsplit(url)
    keep = "/%:@!$&'()*+,;=-._~"
    return urllib.parse.urlunsplit(s._replace(path=urllib.parse.quote(s.path, safe=keep),
                                              query=urllib.parse.quote(s.query, safe=keep + "?")))


def fetch_article(url, limit=1_500_000):
    """(visible text, published ISO date) of an article page. Either is None if
    it could not be had. A paywall or bot wall returns None or a shell; callers
    must treat "no mention found" as evidence only when the page really loaded."""
    raw = None
    for attempt in range(2):                         # one retry, for a timeout or a server hiccup only
        try:
            req = urllib.request.Request(ascii_url(url), headers={"User-Agent": UA, "Accept": "text/html,*/*"})
            with urllib.request.urlopen(req, timeout=20) as r:
                raw = r.read(limit).decode("utf-8", "replace")
            break
        except urllib.error.HTTPError as e:
            LAST_FAILURE[url] = f"HTTP {e.code}"
            if not (e.code in (429, 500, 502, 503, 504) and attempt == 0):
                return None, None
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            LAST_FAILURE[url] = "timeout" if isinstance(e, TimeoutError) or "timed out" in str(e) else f"{type(e).__name__}: {e}"[:80]
            if isinstance(e, ValueError) or attempt == 1:
                return None, None
        time.sleep(2)
    published = page_date(raw)                       # before scripts go: JSON-LD lives in one
    raw = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", raw)
    text = trim_chrome(strip_tags(raw))
    if len(text) <= 400:
        LAST_FAILURE[url] = f"too short ({len(text)} chars of text)"
        return None, published
    LAST_FAILURE.pop(url, None)
    return text, published


def fetch_article_text(url, limit=None):
    return (fetch_article(url) if limit is None else fetch_article(url, limit))[0]


# "Read this next: <another story>", "Most read", "Related coverage": headlines
# of other stories, which would otherwise make one story mention another's
# staff. Only cut in the back half, so a story that opens with "Related:" survives.
# Only phrases that are not ordinary prose: "hear more from residents" and "one of
# the most popular programs" both occur in op-eds, and cutting there would drop
# the author bio at the foot, which is where "Hawaiʻi Appleseed" is.
CHROME = re.compile(r"(read this next|related (stories|articles|coverage|posts|reading)|most read|"
                    r"you (may|might) also like|trending now|recommended for you)", re.I)


def trim_chrome(text):
    for m in CHROME.finditer(text):
        if m.start() > len(text) * 0.4:
            return text[: m.start()]
    return text


# -------------------------------------------------------------------- sources


THROTTLE_WAIT_CAP = 30   # seconds; the longest a 429/503 Retry-After is honoured


def throttle_wait(e, attempt):
    """Seconds to sit out a 429/503: what Retry-After asks (seconds form), else
    5s, 10s...; never more than THROTTLE_WAIT_CAP."""
    try:
        asked = float(e.headers.get("Retry-After", ""))
    except (TypeError, ValueError):
        asked = 5 * (attempt + 1)
    return min(max(asked, 0), THROTTLE_WAIT_CAP)


def http_get(url, timeout=25, retries=2, throttle_retries=0):
    """`throttle_retries` are extra attempts spent only on 429/503, after waiting
    out Retry-After; the ordinary `retries` back-off does not honour it."""
    last, throttled = None, 0
    for attempt in range(retries + throttle_retries + 1):
        try:
            req = urllib.request.Request(ascii_url(url), headers={"User-Agent": UA, "Accept": "application/rss+xml, text/xml, */*"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", "replace")
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = describe_error(e)
            if isinstance(e, urllib.error.HTTPError) and e.code in (429, 503) and throttled < throttle_retries:
                time.sleep(throttle_wait(e, throttled))
                throttled += 1
                continue
            if isinstance(e, urllib.error.HTTPError) and e.code in (400, 401, 403, 404, 410):
                break                                # retrying a refusal only wastes time
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"{url[:90]}… : {last}")


def describe_error(e):
    """An HTTP failure with what the server said about it. A bare "429" cannot
    tell a throttle from a block; Retry-After and the first words of the body
    usually can (a bot wall names itself, a rate limit says when to return)."""
    if not isinstance(e, urllib.error.HTTPError):
        return str(e)
    try:
        raw = e.read(4000).decode("utf-8", "replace")
        raw = re.sub(r"(?is)<(head|script|style)[^>]*>.*?(</\1>|$)", " ", raw)   # error pages are mostly <head>
        body = re.sub(r"\s+", " ", strip_tags(raw))[:120]
    except (OSError, ValueError):
        body = ""
    extra = [f"Retry-After: {e.headers['Retry-After']}"] if e.headers.get("Retry-After") else []
    if e.headers.get("Server"):
        extra.append(f"Server: {e.headers['Server']}")
    return f"HTTP {e.code} {e.reason}" + (f" [{', '.join(extra)}]" if extra else "") + (f" body: {body!r}" if body else "")


def google_url(query, days):
    q = f"{query} when:{max(1, days)}d"
    return "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {"q": q, "hl": "en-US", "gl": "US", "ceid": "US:en"})


def bing_url(query):
    return "https://www.bing.com/news/search?" + urllib.parse.urlencode(
        {"q": query, "format": "rss", "sortbydate": "1"})


def _child_text(item, local):
    for c in item:
        if c.tag.split("}")[-1].lower() == local.lower():
            return (c.text or "").strip(), c
    return "", None


def parse_google(xml_text):
    out = []
    for item in ET.fromstring(xml_text).iter("item"):
        title, _ = _child_text(item, "title")
        link, _ = _child_text(item, "link")
        pub, _ = _child_text(item, "pubDate")
        desc, _ = _child_text(item, "description")
        outlet, src = _child_text(item, "source")
        outlet_url = src.get("url", "") if src is not None else ""
        if outlet and title.endswith(" - " + outlet):
            title = title[: -len(outlet) - 3]
        snippet = strip_tags(desc)
        # Google's description is the headline and outlet again; keep only
        # what is beyond them.
        for dup in (title, outlet):
            if dup:
                snippet = snippet.replace(dup, " ")
        out.append({"title": html.unescape(title), "url": decode_google_url(link) or link,
                    "published": pub, "snippet": re.sub(r"\s+", " ", snippet).strip(),
                    "outlet": outlet, "outlet_url": outlet_url, "source": "google"})
    return out


def parse_bing(xml_text):
    out = []
    for item in ET.fromstring(xml_text).iter("item"):
        title, _ = _child_text(item, "title")
        link, _ = _child_text(item, "link")
        pub, _ = _child_text(item, "pubDate")
        desc, _ = _child_text(item, "description")
        outlet, _ = _child_text(item, "Source")
        real = urllib.parse.parse_qs(urllib.parse.urlsplit(link).query).get("url", [link])[0]
        out.append({"title": html.unescape(title), "url": real, "published": pub,
                    "snippet": strip_tags(desc), "outlet": outlet,
                    "outlet_url": "https://" + host_of(real), "source": "bing"})
    return out


def parse_feed(xml_text, outlet):
    """RSS 2.0 or Atom -> the same dicts the search parsers give. Keeps the
    feed's own body text (content:encoded / content) when it has any, since a
    full-text feed saves fetching the page."""
    out = []
    root = ET.fromstring(xml_text)
    for e in root.iter():
        if e.tag.split("}")[-1] not in ("item", "entry"):
            continue
        title, link, pub, body = "", "", "", ""
        # YouTube nests the description one level down, inside media:group
        children = list(e) + [g for c in e if c.tag.split("}")[-1].lower() == "group" for g in c]
        for c in children:
            tag = c.tag.split("}")[-1].lower()
            if tag == "title":
                title = strip_tags(c.text or "")
            elif tag == "link":
                cand = (c.get("href") or (c.text or "")).strip()
                if cand and not link and c.get("rel") in (None, "alternate"):   # not rel="replies" / "self"
                    link = cand
            elif tag in ("pubdate", "published", "updated", "date"):
                pub = pub or (c.text or "").strip()
            elif tag in ("encoded", "content", "description", "summary"):
                txt = strip_tags(c.text or "")
                if len(txt) > len(body):
                    body = txt
        if title and link:
            out.append({"title": html.unescape(title), "url": link, "published": pub, "snippet": body,
                        "outlet": outlet, "outlet_url": "https://" + host_of(link), "source": "feed"})
    return out


def parse_any_date(s):
    """RFC 2822 (RSS) or ISO 8601 (Atom / dc:date)."""
    d = parse_date(s)
    if d is not None:
        return d
    try:
        d = dt.datetime.fromisoformat((s or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    return (d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)).astimezone(dt.timezone.utc)


MIN_FEED_HOURS = 8       # runs are ~6h apart; a busy feed must reach back further than that
MAX_ARTICLE_READS = 600  # a first run after adding feeds reads several hundred; later runs read only what is new


def feed_urls(feed):
    """The pages to fetch for one feed. A WordPress feed holds only its newest
    10 or so stories, which for a busy outlet is a few hours; `pages: 3`
    reaches back three times as far via ?paged=N."""
    url = feed["url"]
    sep = "&" if "?" in url else "?"
    return [url] + [f"{url}{sep}paged={n}" for n in range(2, int(feed.get("pages", 1)) + 1)]


def unwrap_redirect(url):
    """Google Alerts links go through google.com/url?...&url=<article>."""
    u = urllib.parse.urlsplit(url)
    if host_of(url) == "google.com" and u.path == "/url":
        q = urllib.parse.parse_qs(u.query)
        for key in ("url", "q"):
            if q.get(key):
                return q[key][0]
    return url


def fetch_feed(feed, alert, delay, out):
    """All items from one feed, or None if its first page failed."""
    items = []
    for n, url in enumerate(feed_urls(feed), 1):
        try:
            got = parse_feed(http_get(url, timeout=20, retries=1), feed["name"])
        except (RuntimeError, ET.ParseError) as e:
            if n == 1:
                # an alert feed's URL carries the owner's Google account id: name it, never print it
                msg = re.sub(r"https?://\S+", "<alert feed url>", str(e)) if alert else e
                print(f"::warning::feed {feed['name']} failed: {msg}", file=out)
                return None
            break   # a later page that will not load just ends the paging
        finally:
            time.sleep(delay)
        items += got
        if not got:
            break
    dates = [d for d in (parse_any_date(it["published"]) for it in items) if d]
    if len(items) >= 10 and len(dates) >= 10:
        hours = (max(dates) - min(dates)).total_seconds() / 3600
        active = max(dates) > dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=2)
        if hours < MIN_FEED_HOURS and active:
            # The gap that hid Maui Now's stories: a busy feed that reaches back less
            # far than the time between runs loses the stories in between. Only an
            # ACTIVE feed: a monthly paper posts its ten stories in one afternoon.
            print(f"::warning::feed {feed['name']} reaches back only {hours:.0f}h "
                  f"({len(items)} items); stories can slip between runs. Give it `pages` or a larger size.", file=out)
    if alert:
        for it in items:
            it["url"] = unwrap_redirect(it["url"])
            it["outlet"] = host_of(it["url"])          # an alert names no outlet
            it["outlet_url"] = "https://" + it["outlet"]
    return items


DEFER = object()   # "past the read budget: leave it for the next run"
BLIND = "~blind"   # suffix on a `checked` date: the page would not load, so the story was skipped, not judged


def blind_mark(today):
    return today + BLIND


def is_blind(mark):
    return bool(mark) and mark.endswith(BLIND)


class Reader:
    """The part of a run that reads stories and judges them. One instance is
    shared by every source (feeds, outlet search, podcasts), so the read budget
    and the per-outlet tally of pages that would not load are global, and a
    story two sources both find is judged once.

    Each story is read at most once a fortnight: `checked` remembers a miss
    (id -> date). A story already in mentions.json is skipped (`known`, ids and
    canonical URLs). A page that will not load is counted per outlet and shown
    in the run report, so a paywalled outlet reads as blind, not as quiet."""

    def __init__(self, cfg, staff, cutoff, checked, today, delay=0.3, out=sys.stdout, known=()):
        self.cfg, self.staff, self.cutoff = cfg, staff, cutoff
        self.checked, self.today, self.delay, self.out = checked, today, delay, out
        self.known = set(known)
        self.reads = self.deferred = self.seen = 0
        self.blind, self.seen_ids = {}, set()
        self.health = {}          # stage -> (answered, asked): a stage that answered nothing is dead, not quiet

    def snapshot(self):
        return (self.seen, self.reads, self.deferred, dict(self.blind))

    def since(self, snap):
        """One line about what happened since `snapshot()`."""
        seen, reads, deferred, blind = snap
        notes = [f"{self.seen - seen} new stories judged, {self.reads - reads} pages read"]
        lost = {k: v - blind.get(k, 0) for k, v in self.blind.items() if v - blind.get(k, 0)}
        if lost:
            notes.append("could not read: " + ", ".join(f"{k} ×{v}" for k, v in lost.items()))
        if self.deferred - deferred:
            notes.append(f"{self.deferred - deferred} left for the next run (read cap)")
        return " · ".join(notes)

    def _read_via_rest(self, url):
        """The page would not load (a bot wall: KHON2 answers every article with a
        403), but a WordPress outlet in `outlet_search` still serves the post's text
        through its REST API. Look it up by slug; (None, None) if it is not one."""
        host = host_of(url)
        base = next((o["base"].rstrip("/") for o in self.cfg.get("outlet_search", [])
                     if o.get("type") == "wp-rest" and host_of(o.get("base", "")) == host), None)
        slug = urllib.parse.urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1]
        if not (base and slug):
            return None, None
        try:
            rows = json.loads(http_get(f"{base}/wp-json/wp/v2/posts?slug={urllib.parse.quote(slug)}"
                                       "&_fields=date_gmt,content", timeout=30, retries=0, throttle_retries=1))
            time.sleep(self.delay)
        except (RuntimeError, ValueError):
            return None, None
        if not (isinstance(rows, list) and rows):
            return None, None
        text = strip_tags((rows[0].get("content") or {}).get("rendered", ""))
        gmt = rows[0].get("date_gmt") or ""
        return (text if len(text) > 400 else None), (gmt + "Z" if gmt else None)

    def _read(self, it):
        if self.reads >= MAX_ARTICLE_READS:
            self.deferred += 1
            return DEFER, None
        self.reads += 1
        text, published = fetch_article(it["url"])
        time.sleep(self.delay)
        if text is None:
            text, published = self._read_via_rest(it["url"])
        if text is None:
            who = it.get("outlet") or host_of(it["url"])
            self.blind[who] = self.blind.get(who, 0) + 1
            self.logged = getattr(self, "logged", 0) + 1
            if self.logged <= 10:                    # name the page; the per-outlet count alone cannot be chased
                print(f"::notice::could not read {it['url']} ({LAST_FAILURE.get(it['url'], 'no text')})"
                      + (" — more not listed" if self.logged == 10 else ""), file=self.out)
        return text, published

    def evaluate(self, items, label, alert=False):
        """Judge each item; return those that qualify (medium or better).

        Item flags: `complete` — the text is all there is (a podcast or video
        description, a REST post body), so do not fetch the page to find more;
        `no_read` — never fetch the page at all; `needs_date` — the source gave
        no date (HTML search results), so the page or URL must supply one.

        A weak verdict earns a page read: a bare staff name on a full REST body
        says nothing, but the page's byline bio usually says "Hawaiʻi
        Appleseed" (the weekly Civil Beat column does)."""
        cfg, staff = self.cfg, self.staff
        found = []
        for it in items:
            d = parse_any_date(it.get("published", "")) or url_date(it["url"])
            if (d is not None and d < self.cutoff) or is_own(it, cfg) or is_ignored(it, cfg):
                continue
            iid = story_id(story_key(it))
            mark = self.checked.get(iid)
            # A "~blind" mark means a page would not load, so nothing was actually
            # judged. It stops the feed stage re-fetching a bot-walled page every
            # run, but must not stop a source that HAS the text (REST search, a
            # podcast description) from judging the story.
            if (mark and not (is_blind(mark) and it.get("complete"))) or iid in self.known \
                    or canon_url(it["url"]) in self.known or iid in self.seen_ids:
                continue
            self.seen_ids.add(iid)
            self.seen += 1
            text, no_read = it.get("snippet", ""), it.get("no_read", False)
            page_read = unread = False
            if not it.get("complete") and len(text) < 1500 and not no_read:
                page, published = self._read(it)
                if page is DEFER:
                    self.seen_ids.discard(iid)
                    self.seen -= 1
                    continue                          # not remembered: the next run reads it
                page_read, unread = True, page is None
                text = text if page is None else page
                d = d or parse_any_date(published or "")
            if d is not None and d < self.cutoff:
                self.checked[iid] = self.today        # old, however it got here
                continue
            if d is None and it.get("needs_date"):
                self.checked[iid] = self.today        # cannot show it is recent
                continue

            def judge(t):
                return classify({"title": it["title"], "snippet": t}, cfg, staff,
                                kind="org" if alert and unread else "", full_text=len(t) >= 1500)

            verdict = judge(text)
            if verdict and verdict[0] == "low" and not page_read and not no_read:
                page, published = self._read(it)
                if page is DEFER:
                    self.seen_ids.discard(iid)
                    self.seen -= 1
                    continue
                if page is not None:
                    verdict = judge(page)
                    d = d or parse_any_date(published or "")
            if verdict is None or verdict[0] == "low":
                # a miss is remembered; a hit is remembered by mentions.json. A
                # story whose page would not load was not judged, only skipped.
                self.checked[iid] = blind_mark(self.today) if unread and not alert else self.today
                continue
            it["confidence"], it["reasons"], it["matched"] = verdict
            it["query"] = label
            it["published_iso"] = d.strftime("%Y-%m-%dT%H:%M:%SZ") if d else ""
            found.append(it)
        return found


def crawl_feeds(cfg, staff, cutoff, checked, today, delay=0.3, out=sys.stdout, reader=None, known=()):
    """Read every new story in the outlets' own feeds, in full, and keep those
    that name Appleseed or its staff.

    This is the half that finds body-only mentions ("said Devin Thomas of
    Hawaiʻi Appleseed"), which the news search engines never index.

    Two kinds of feed, same reading. `outlet_feeds` are an outlet's newest
    stories (a feed with `read_pages: false` — a YouTube channel — is judged on
    its own description and its page is never fetched). `alert_feeds` are
    Google Alerts RSS feeds: Google has already matched the phrase somewhere in
    the page (any site on the web), so a hit whose page will not load is kept as
    an unchecked match rather than dropped, exactly as for a search-engine hit."""
    reader = reader or Reader(cfg, staff, cutoff, checked, today, delay, out, known)
    snap, found = reader.snapshot(), []
    feeds = [(f, False) for f in cfg.get("outlet_feeds", [])] + [(f, True) for f in cfg.get("alert_feeds", [])]
    answered = 0
    for feed, alert in feeds:
        items = fetch_feed(feed, alert, delay, out)
        if items is None:
            continue
        answered += 1
        if feed.get("read_pages") is False:
            for it in items:
                it["complete"] = it["no_read"] = True
        found += reader.evaluate(items, f"{'alert' if alert else 'feed'}: {feed['name']}", alert=alert)
    reader.health["feeds"] = (answered, len(feeds))
    print("feeds: " + reader.since(snap), file=out)
    return found


# --------------------------------------------------- outlet search and podcasts
#
# The news search engines index headline and lede, and a feed holds only the
# newest few hours. An outlet's OWN search reaches the full text of every story
# it ever ran, and does not care how deep its feed is. Three drivers, one per
# way an outlet lets itself be searched:
#   wp-rest   WordPress REST: /wp-json/wp/v2/posts?search=  (full article body
#             in the reply, so nothing to fetch; also works around outlets that
#             bot-wall their article pages, which KHON2 does)
#   blox-rss  BLOX CMS: /search/?q=&f=rss  (headlines only; the page is read)
#   html      any site search page: its result links are collected and each
#             article read. Result pages carry no dates, so the URL or the page
#             has to supply one.


def parse_wp_rows(rows, outlet):
    out = []
    for p in rows:
        title = strip_tags((p.get("title") or {}).get("rendered", ""))
        link = p.get("link", "")
        if not (title and link):
            continue
        gmt = p.get("date_gmt") or ""
        out.append({"title": title, "url": link, "published": gmt + "Z" if gmt else "",
                    "snippet": strip_tags((p.get("content") or {}).get("rendered", "")),
                    "outlet": outlet["name"], "outlet_url": "https://" + host_of(link),
                    "source": "search", "complete": True})
    return out


def search_wp_rest(outlet, term, cutoff, delay, max_pages=5):
    base = outlet["base"].rstrip("/")
    after = (cutoff - dt.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S")   # WordPress compares in site-local time
    items = []
    for page in range(1, max_pages + 1):
        url = (f"{base}/wp-json/wp/v2/posts?search={urllib.parse.quote(term)}&per_page=100&page={page}"
               f"&orderby=date&order=desc&after={after}&_fields=date_gmt,link,title,content")
        try:
            rows = json.loads(http_get(url, timeout=outlet.get("timeout", 30), retries=0, throttle_retries=2))
        except RuntimeError:
            if page == 1:
                raise
            break                                     # WordPress answers 400 past the last page
        if not isinstance(rows, list):
            raise ValueError("not a post list")
        items += parse_wp_rows(rows, outlet)
        if len(rows) < 100:
            break
        time.sleep(delay)
    return items


def search_blox_rss(outlet, term, cutoff, delay):
    url = (f"{outlet['base'].rstrip('/')}/search/?q={urllib.parse.quote(term)}"
           "&f=rss&t=article&l=50&s=start_time&sd=desc")
    items = parse_feed(http_get(url, timeout=outlet.get("timeout", 30), retries=0), outlet["name"])
    for it in items:
        it["source"] = "search"
    return items


NOT_ARTICLE = re.compile(r"/(category|categories|tag|tags|author|authors|topic|topics|section|page|search|feed|"
                         r"wp-content|wp-json|about|contact|subscribe|events?)(/|$)", re.I)
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+){3,}", re.I)


def html_search_links(html_text, base_url):
    """Headline links on a site-search page: same host, link text long enough
    to be a headline (a menu label is not), and a path that looks like an
    article (dated, or a slug of four words or more)."""
    host, seen, out = host_of(base_url), set(), []
    for m in re.finditer(r'<a\s[^>]*?href=["\']([^"\'#]+)["\'][^>]*>(.*?)</a>', html_text, re.S | re.I):
        href = urllib.parse.urljoin(base_url, html.unescape(m.group(1)))
        title = strip_tags(m.group(2))
        if host_of(href) != host or len(title) < 25 or len(title.split()) < 4:
            continue
        path = urllib.parse.urlsplit(href).path
        if NOT_ARTICLE.search(path) or not (URL_DATE.search(path) or SLUG.search(path)):
            continue
        cu = canon_url(href)
        if cu in seen:
            continue
        seen.add(cu)
        out.append({"title": title, "url": href, "published": "", "snippet": "", "outlet": "",
                    "outlet_url": "https://" + host, "source": "search", "needs_date": True})
    return out


def search_html(outlet, term, cutoff, delay):
    """A site-search page, and its further pages. Every outlet paginates
    differently (Star-Advertiser /search/<q>/page/2/, HPR &p=2), so `page_url`
    is a template with {q} (query-escaped), {qp} (path-escaped) and {n}; without
    one only the first page is read. Results are relevance-ordered, not dated,
    and some outlets stem the term (Star-Advertiser's "Appleseed" also returns
    Apple iPhone stories), so a deep page is mostly noise the reader discards."""
    pages = int(outlet.get("pages", 1))
    seen, items = set(), []
    for n in range(1, pages + 1):
        tpl = outlet["url"] if n == 1 else outlet.get("page_url", "")
        if not tpl:
            break
        url = tpl.format(q=urllib.parse.quote_plus(term), qp=urllib.parse.quote(term), n=n)
        try:
            page = http_get(url, timeout=outlet.get("timeout", 30), retries=0)
        except RuntimeError:
            if n == 1:
                raise
            break                                     # a later page that will not load ends the paging
        got = [it for it in html_search_links(page, url) if canon_url(it["url"]) not in seen]
        mentions = len(re.findall(re.escape(term), page, re.I))
        if n == 1 and not got and mentions > 5:
            # A page that says the term many times but gives us no headline is a
            # page whose markup changed, which would otherwise read as "no coverage".
            # (A page that merely echoes the query says it once or twice.)
            raise ValueError(f"the results page mentions {term!r} {mentions} times "
                             "but no article links were recognised; its markup may have changed")
        if not got:
            break
        seen |= {canon_url(it["url"]) for it in got}
        items += got
        time.sleep(delay)
    for it in items:
        it["outlet"] = outlet["name"]
    return items


DRIVERS = {"wp-rest": search_wp_rest, "blox-rss": search_blox_rss, "html": search_html}


def _gather_outlet(outlet, terms, cutoff, delay):
    """All of one outlet's results for `terms`. One request at a time per outlet,
    so it stays polite. A term that fails is skipped, not fatal: the rest are
    still asked, and the error names what was lost (a single 429 used to cost
    every later term, including every staff name)."""
    driver, got, lost = DRIVERS[outlet["type"]], [], []
    for term in terms:
        try:
            got += driver(outlet, term, cutoff, delay)
        except Exception as e:                        # one outlet's odd reply must not cost the others
            lost.append((term, str(e) if isinstance(e, RuntimeError) else f"{type(e).__name__}: {e}"))
        time.sleep(delay)
    if not lost:
        return outlet, got, None
    names = ", ".join(repr(t) for t, _ in lost[:5]) + (f" +{len(lost) - 5} more" if len(lost) > 5 else "")
    return outlet, got, RuntimeError(f"{len(lost)} of {len(terms)} queries failed ({names}); first: {lost[0][1]}")


def search_sites(cfg, staff, cutoff, reader, delay=0.3, out=sys.stdout, deep=False):
    """Ask each outlet's own search for the org, its work, and (WordPress only,
    where the reply is cheap) each staff name; judge what comes back.

    Outlets are independent hosts, so they are asked in parallel; the judging,
    which fetches pages and spends the read budget, is sequential.

    `deep` reads an html outlet's `pages_deep` result pages instead of `pages`.
    Their results are relevance-ordered, so a story that names Appleseed once, in
    paragraph nine, is on page 10 or 14 (measured on Star-Advertiser and HPR).
    A daily run does not need that depth, because a feed sees every new story;
    an inventory does. html outlets are asked only for the org term: work terms
    to a stemming, relevance-ranked search only add noise."""
    org_terms = list(cfg.get("search_terms", ["Appleseed"]))
    terms = org_terms + list(cfg.get("work_terms", []))
    snap, found, failed, answered = reader.snapshot(), [], [], 0
    outlets, jobs = cfg.get("outlet_search", []), []
    for outlet in outlets:
        if outlet.get("type") not in DRIVERS:
            print(f"::warning::outlet_search {outlet.get('name')}: unknown type {outlet.get('type')!r}", file=out)
            continue
        if deep and "pages_deep" in outlet:
            outlet = {**outlet, "pages": outlet["pages_deep"]}
        names = staff if outlet["type"] == "wp-rest" and cfg.get("search_staff", True) and outlet.get("staff", True) else []
        jobs.append((outlet, (org_terms if outlet["type"] == "html" else terms) + names))
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, min(8, len(jobs)))) as pool:
        results = list(pool.map(lambda j: _gather_outlet(j[0], j[1], cutoff, delay), jobs))
    for outlet, got, err in results:
        if err is None:
            answered += 1
        else:
            failed.append(outlet["name"])
            what = str(err) if isinstance(err, RuntimeError) else f"{type(err).__name__}: {err}"
            print(f"::warning::search {outlet['name']} failed: {what}", file=out)
        found += reader.evaluate(got, f"search: {outlet['name']}")
    fail = f" · failed: {', '.join(failed)}" if failed else ""
    reader.health["search"] = (answered, len(jobs))
    print(f"search: {answered}/{len(outlets)} outlets answered{fail} · " + reader.since(snap), file=out)
    return found


def parse_itunes(data):
    out = []
    for r in data.get("results", []):
        title, url = r.get("trackName", ""), r.get("trackViewUrl") or r.get("episodeUrl", "")
        if not (title and url):
            continue
        out.append({"title": title, "url": url, "published": r.get("releaseDate", ""),
                    "snippet": r.get("description") or r.get("shortDescription") or "",
                    "outlet": r.get("collectionName", ""), "outlet_url": "https://podcasts.apple.com",
                    "source": "podcast", "complete": True, "no_read": True})
    return out


def search_podcasts(cfg, cutoff, reader, delay=1.0, out=sys.stdout):
    """Apple's podcast directory search (open, no key). It matches episode
    titles and descriptions, so it finds a guest introduced as "…of Hawaiʻi
    Appleseed". Audio is not transcribed: a mention only spoken is not found."""
    terms = cfg.get("podcast_terms") or [q.strip('"') for q in cfg.get("org_queries", [])]
    snap, items, failed = reader.snapshot(), [], 0
    for t in terms:
        url = "https://itunes.apple.com/search?" + urllib.parse.urlencode(
            {"term": t, "media": "podcast", "entity": "podcastEpisode", "limit": 200, "country": "us"})
        try:
            items += parse_itunes(json.loads(http_get(url, timeout=30, retries=1)))
        except (RuntimeError, ValueError) as e:
            failed += 1
            print(f"::warning::podcast search failed ({t}): {e}", file=out)
        time.sleep(delay)
    found = reader.evaluate(items, "podcast")
    reader.health["podcasts"] = (len(terms) - failed, len(terms))
    print(f"podcasts: {len(terms) - failed}/{len(terms)} searches answered · " + reader.since(snap), file=out)
    return found


def load_checked(path=None, keep_days=14):
    try:
        data = json.loads(Path(path or CHECKED_PATH).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    floor = (dt.date.today() - dt.timedelta(days=keep_days)).isoformat()
    return {k: v for k, v in data.items() if isinstance(v, str) and v >= floor}


def save_checked(checked, path=None):
    path = Path(path or CHECKED_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(checked, sort_keys=True), encoding="utf-8")


# ------------------------------------------------------------ matching / queue


def read_staff(cfg):
    """Names from the team page: every .ha-member-name plus the ED's <h2>."""
    names = []
    path = ROOT / cfg.get("staff_from", "our-team.html")
    if path.exists():
        text = path.read_text(encoding="utf-8")
        ed = re.search(r'class="ha-ed-content".*?<h2>([^<]+)</h2>', text, re.S)
        if ed:
            names.append(html.unescape(ed.group(1)).strip())
        names += [html.unescape(n).strip() for n in re.findall(r'class="ha-member-name">([^<]+)<', text)]
    names += cfg.get("staff_extra", [])
    seen, out = set(), []
    for n in names:
        if n and n.lower() not in seen:
            seen.add(n.lower())
            out.append(n)
    return out


def build_queries(cfg, staff):
    qs = [("org", q) for q in cfg["org_queries"]]
    qs += [("work", f'"{t}"') for t in cfg.get("work_terms", [])]
    suffix = cfg.get("staff_query_suffix", "")
    qs += [("staff", f'"{n}" {suffix}'.strip()) for n in staff]
    return qs


def classify(item, cfg, staff, kind="", full_text=False):
    """(confidence, reasons, matched) or None when it does not qualify.

    The feed carries a headline and, at best, a short snippet, so a story the
    engine matched on its body text (a byline bio, a quote) can show nothing
    here. For an org or work query that is still a signal — the engine did
    match the exact phrase — but an unchecked one, recorded as such and
    settled by verify_article().

    full_text=True means `snippet` is the whole article rather than a headline
    and lede. A full article names people in passing, so the bar for a staff
    name is the same as for a headline (Hawaiʻi and policy context around it)
    but the reason says the org was not named, so a person can check it is
    them. That rule needs trim_chrome(): a "Read this next" widget promoting
    one of our columnists once made an unrelated story look like a mention."""
    text = norm(item["title"] + " " + item.get("snippet", ""))
    org = has_phrase(text, "hawaii appleseed") or has_phrase(text, "appleseed center for law and economic justice")
    if not org and any(has_phrase(text, p) for p in cfg.get("ignore_phrases", [])):
        return None
    reasons, matched, best = [], [], None

    def bump(level, why, name=None):
        nonlocal best
        reasons.append(why)
        if name:
            matched.append(name)
        if best is None or RANK[level] > RANK[best]:
            best = level

    appleseed = org or has_phrase(text, "appleseed")
    hawaii = any(has_phrase(text, w) for w in cfg.get("hawaii_context", []))
    policy = any(has_phrase(text, w) for w in cfg.get("policy_context", []))

    if org:
        bump("high", "names Hawaiʻi Appleseed")
    elif appleseed and near(text, "appleseed", cfg.get("hawaii_context", [])):
        bump("medium", "“Appleseed” with Hawaiʻi context")
    raw = (item["title"] + " " + item.get("snippet", ""))
    folded = _fold(raw)
    ambiguous = {n.lower() for n in cfg.get("staff_ambiguous", [])}
    for name in staff:
        if not has_name(raw, name, folded):
            continue
        if appleseed and appleseed_beside(name, raw, cfg, folded):
            bump("medium", f"staff: {name}, with Appleseed", name)
        elif name.lower() in ambiguous:
            # Common enough that the bare name proves nothing (a candidate who
            # shares it, a football player, "Will White House"). Believed only
            # with a job title beside it; otherwise "low", which earns the
            # article being read for the org's name (a byline bio has it).
            if hawaii and role_cue(raw, name, cfg, folded):
                bump("medium", f"staff: {name}, named with a job title; the text does not name Appleseed", name)
            else:
                bump("low", f"staff: {name} only", name)
        elif hawaii and policy:
            bump("medium", f"staff: {name}, with Hawaiʻi policy context; the text does not name Appleseed"
                 if full_text else f"staff: {name}, with Hawaiʻi policy context", name)
        else:
            bump("low", f"staff: {name} only", name)
    for term in cfg.get("work_terms", []):
        if has_phrase(text, term):
            bump("medium", f"work: {term}")
    if best is None and kind in ("org", "work"):
        return "medium", [UNCHECKED], []
    if best is None:
        return None
    return best, reasons, matched


UNCHECKED = "search engine matched the phrase; article text not checked"


HEADLINE_STAFF = re.compile(r"^staff: .+, with Hawaiʻi policy context$")   # no "; the text does not name Appleseed" tail


def is_guess(reason):
    """A reason nobody has read the article behind: the engine's phrase match
    (UNCHECKED), or a staff name that sat near Hawaiʻi and policy words in a
    headline or snippet. A namesake looks exactly like that."""
    return reason == UNCHECKED or bool(HEADLINE_STAFF.match(reason))


def is_weak(rec):
    """Needs the article read before it is believed: a bare staff name, or a
    match nobody has seen the words of."""
    return rec["confidence"] == "low" or (bool(rec["reasons"]) and all(is_guess(r) for r in rec["reasons"]))


def verify_article(text, cfg):
    """Judge an article's full text. Returns (confidence, reason), or None if
    it never mentions Appleseed."""
    t = norm(text)
    if has_phrase(t, "hawaii appleseed") or has_phrase(t, "appleseed center for law and economic justice"):
        return "high", "article text names Hawaiʻi Appleseed"
    if near(t, "appleseed", cfg.get("hawaii_context", [])):
        return "medium", "article text mentions Appleseed, with Hawaiʻi context"
    return None


def merge_found(found):
    """One entry per story. The same story from two sources, or from two
    queries, is merged; the direct URL beats a Google redirect."""
    by_key, by_url = {}, {}
    for f in found:
        k = story_key(f)
        # the same article under a slightly different headline (a feed's, a
        # search result's) is still one story: match on its URL too
        cu = "" if "news.google.com" in f["url"] else canon_url(f["url"])
        if k not in by_key and cu in by_url:
            k = by_url[cu]
        cur = by_key.get(k)
        if cur is None:
            by_key[k] = {**f, "sources": [f["source"]], "queries": [f.get("query", "")]}
            if cu:
                by_url[cu] = k
            continue
        if cu:
            by_url.setdefault(cu, k)
        if f["source"] not in cur["sources"]:
            cur["sources"].append(f["source"])
        if f.get("query") and f["query"] not in cur["queries"]:
            cur["queries"].append(f["query"])
        if "news.google.com" in cur["url"] and "news.google.com" not in f["url"]:
            cur["url"] = f["url"]
        if RANK[f["confidence"]] > RANK[cur["confidence"]]:
            cur["confidence"] = f["confidence"]
        for r in f["reasons"]:
            if r not in cur["reasons"]:
                cur["reasons"].append(r)
        for m in f.get("matched", []):
            if m not in cur.get("matched", []):
                cur.setdefault("matched", []).append(m)
    return by_key


def load_site_press(path=None):
    try:
        data = json.loads(Path(path or NEWS_PATH).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    out = []
    for p in data.get("press", []):
        out.append({"url": canon_url(p.get("sourceUrl", "")) if p.get("sourceUrl") else "",
                    "title": norm(p.get("title", "")), "fullUrl": p.get("fullUrl", "")})
    return out


def on_site(item, press):
    """Return the In the News path if this story is already posted there."""
    cu = canon_url(item["url"]) if "news.google.com" not in item["url"] else ""
    nt = norm(item["title"])
    for p in press:
        if cu and p["url"] and cu == p["url"]:
            return p["fullUrl"] or "/in-the-news"
    for p in press:
        if not p["title"]:
            continue
        sm = difflib.SequenceMatcher(None, nt, p["title"])
        if sm.real_quick_ratio() >= 0.75 and sm.quick_ratio() >= 0.75 and sm.ratio() >= 0.8:
            return p["fullUrl"] or "/in-the-news"
    return ""


def is_ignored(item, cfg):
    """A headline a person has said is never a mention (config ignore_titles, regexes).
    The default is "Candidate Q&A": an election guide lists every candidate, so a
    staff member who ran shows up on six rivals' pages as well as their own, in a
    public digest, for a reason that is not press coverage of the org."""
    return any(re.search(pat, item["title"], re.I) for pat in cfg.get("ignore_titles", [])) or is_blocked(item, cfg)


def is_blocked(item, cfg):
    """A source a person has said is junk (config block_sources). Each entry is a host
    ("example.com", which also covers its subdomains) or a host plus path prefix
    ("facebook.com/somepage", which blocks that page and leaves the rest of the host
    alone). Matched against the story's own URL and its outlet URL, never the title."""
    for u in (item.get("url", ""), item.get("outlet_url", "")):
        if not u:
            continue
        host = host_of(u)
        path = urllib.parse.urlsplit(u if "//" in u else "//" + u).path.strip("/").lower()
        for entry in cfg.get("block_sources", []):
            bhost, _, bpath = entry.lower().strip("/").partition("/")
            if host and (host == bhost or host.endswith("." + bhost)) and (
                    not bpath or path == bpath or path.startswith(bpath + "/")):
                return True
    return False


def is_own(item, cfg):
    hosts = {host_of(item.get("outlet_url", "")), host_of(item["url"])}
    return any(h == d or h.endswith("." + d) for h in hosts if h for d in cfg.get("own_domains", []))


# ---------------------------------------------------------------------- state


def load_state(path=None):
    try:
        return json.loads(Path(path or STATE_PATH).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"_generated": "Written by scripts/media_watch.py. `status` is the one field a person may edit "
                              "(new | added | ignore); the script never overwrites it.", "items": []}


def story_id(key):
    return hashlib.sha1(key.encode()).hexdigest()[:12]


def update_state(state, merged, now_iso):
    """Fold this run's stories into state. Returns the items first seen now."""
    by_id = {i["id"]: i for i in state["items"]}
    by_url = {canon_url(i["url"]): i for i in state["items"] if i.get("url") and "news.google.com" not in i["url"]}
    fresh = []
    for key, m in merged.items():
        iid = story_id(key)
        rec = by_id.get(iid) or (by_url.get(canon_url(m["url"])) if "news.google.com" not in m["url"] else None)
        if rec is None:
            rec = {"id": iid, "title": m["title"], "outlet": m["outlet"], "url": m["url"],
                   "published": m["published_iso"], "firstSeen": now_iso,
                   "confidence": m["confidence"], "reasons": m["reasons"],
                   "sources": m["sources"], "onSite": m["on_site"],
                   "status": "on-site" if m["on_site"] else "new"}
            by_id[iid] = rec
            fresh.append(rec)
            continue
        if "news.google.com" in rec["url"] and "news.google.com" not in m["url"]:
            rec["url"] = m["url"]
        if RANK[m["confidence"]] > RANK.get(rec["confidence"], 0):
            rec["confidence"] = m["confidence"]
        rec["sources"] = sorted(set(rec["sources"]) | set(m["sources"]))
        rec["reasons"] = list(dict.fromkeys(rec["reasons"] + m["reasons"]))
        if m["on_site"] and not rec.get("onSite"):
            rec["onSite"] = m["on_site"]
            if rec.get("status") == "new":
                rec["status"] = "on-site"
    state["items"] = sorted(by_id.values(), key=lambda i: i.get("published", ""), reverse=True)
    return fresh


def is_staff_column(title, staff):
    """"Will Caron: Artful Dodgers": a column that carries its author's name as
    a title prefix. Written by us, not about us, and weekly, so it is listed
    apart rather than swamping the coverage."""
    return any(title.startswith(n + ":") for n in staff)


def _lines(group):
    out = []
    for i in group:
        when = (i.get("published") or i.get("published_iso") or "")[:10]
        out.append(f"- [{i['title']}]({i['url']}) — {i['outlet'] or host_of(i['url'])}, {when}  ")
        out.append(f"  _{'; '.join(i['reasons'])}_")
    return out


def render_digest(items, today, min_conf, staff=()):
    show = [i for i in items if RANK[i["confidence"]] >= RANK[min_conf] and not i.get("onSite")]
    lines = [f"# Media watch — {today}", "",
             f"{len(show)} new {'story' if len(show) == 1 else 'stories'} mentioning Hawaiʻi Appleseed, "
             "its work, or its staff, not yet on [In the News](https://hiappleseed.org/in-the-news).", ""]
    columns = [i for i in show if is_staff_column(i["title"], staff)]
    coverage = [i for i in show if i not in columns]
    for level, head in (("high", "Names Hawaiʻi Appleseed"), ("medium", "Its work or its staff")):
        group = [i for i in coverage if i["confidence"] == level]
        if not group:
            continue
        lines += [f"## {head}", ""] + _lines(group) + [""]
    if columns:
        lines += ["## Written by staff", ""] + _lines(columns) + [""]
    lines += ["To post one: add it to the Squarespace `/in-the-news` collection. To stop one resurfacing, "
              "set its `status` to `ignore` in `media-watch/mentions.json`.", ""]
    return "\n".join(lines), len(show)


def render_report(items, today, days, staff=()):
    """A one-off inventory (--report): every story found in the window, split
    into what In the News lacks and what it already has."""
    key = lambda i: i.get("published_iso", "")
    columns = sorted((i for i in items if not i["on_site"] and is_staff_column(i["title"], staff)), key=key, reverse=True)
    todo = sorted((i for i in items if not i["on_site"] and i not in columns), key=key, reverse=True)
    done = sorted((i for i in items if i["on_site"]), key=key, reverse=True)
    lines = [f"# Media watch inventory — {today}", "",
             f"Stories from the last {days} days that name Hawaiʻi Appleseed, its work, or its staff. "
             f"**{len(todo)} are not on In the News**; {len(done)} already are; "
             f"{len(columns)} more are columns written by staff.", ""]
    for head, group in ((f"Not on In the News ({len(todo)})", todo),
                        (f"Already on In the News ({len(done)})", done),
                        (f"Columns written by staff, not on In the News ({len(columns)})", columns)):
        lines += [f"## {head}", ""]
        for i in group:
            lines.append(f"- {(i.get('published_iso') or '')[:10]} · **{i['outlet'] or host_of(i['url'])}** · "
                         f"[{i['title']}]({i['url']}) · _{i['confidence']}: {'; '.join(i['reasons'])}_")
        lines.append("")
    return "\n".join(lines)


# ------------------------------------------------------------------------ run


MAX_RESOLVE = 40   # Google links resolved per run (two requests each)
MAX_VERIFY = 30    # articles read per run


def settle(merged, state, cfg, checked, today, delay=0.5, out=sys.stdout):
    """Turn feed guesses into facts, for stories not already known.

    Resolves opaque Google links to the real URL (which also lets on_site()
    match by URL), then reads the article behind every weak match. A page that
    loads and never says Appleseed is a rejection, remembered in
    `checked` so it is not fetched again tomorrow. A page that will not
    load (a Facebook post, a bot wall, a Google link that did not resolve, the
    per-run read budget) settles nothing, and a story nobody has read is NOT
    reported: it is dropped for this run and not remembered, so the next run
    tries it again while it is inside the lookback window. Mutates `merged`."""
    known = {i["id"] for i in state["items"]}
    resolved = read = 0
    for key in list(merged):
        m, iid = merged[key], story_id(key)
        if iid in known:
            continue
        if iid in checked and not is_blind(checked[iid]):   # judged a miss (a blind page was never judged)
            del merged[key]
            continue
        if "news.google.com" in m["url"] and resolved < MAX_RESOLVE:
            resolved += 1
            real = resolve_google(m["url"])
            time.sleep(delay)
            if real:
                m["url"] = real
        if not is_weak(m) or "news.google.com" in m["url"] or read >= MAX_VERIFY:
            continue
        read += 1
        text = fetch_article_text(m["url"])
        time.sleep(delay)
        if text is None:
            continue
        verdict = verify_article(text, cfg)
        if verdict is None:
            checked[iid] = today
            del merged[key]
            continue
        m["confidence"] = verdict[0]
        # the weak reasons ("Will Caron only", "not checked") are settled now
        m["reasons"] = [r for r in m["reasons"] if not is_guess(r) and not r.endswith(" only")] + [verdict[1]]
    unread = [k for k, m in merged.items() if story_id(k) not in known and is_weak(m)]
    for k in unread:
        del merged[k]
    print(f"resolved {resolved} links, read {read} articles, held back {len(unread)} nobody could read", file=out)


STAGES = ("engines", "feeds", "search", "podcasts")


def env_alert_feeds():
    """Google Alerts feed URLs from $MEDIA_WATCH_ALERT_FEEDS (whitespace or comma
    separated). They live in a GitHub secret, not in config.json, because each
    URL embeds the owner's Google account id and this repo is public."""
    urls = [u for u in re.split(r"[\s,]+", os.environ.get("MEDIA_WATCH_ALERT_FEEDS", "")) if u.startswith("http")]
    return [{"name": f"Google Alert {i}", "url": u} for i, u in enumerate(urls, 1)]


def run(days=None, dry_run=False, delay=REQUEST_DELAY, out=sys.stdout, only=None, report=None, deep=False):
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    days = days or cfg.get("lookback_days", 3)
    min_conf = cfg.get("min_confidence", "medium")
    cfg["alert_feeds"] = list(cfg.get("alert_feeds", [])) + env_alert_feeds()
    stages = set(only) if only else set(STAGES)
    if report:
        dry_run = True                       # an inventory never touches state
    staff = read_staff(cfg)
    if len(staff) < 3:
        print(f"::warning::only {len(staff)} staff names read from {cfg.get('staff_from')}; "
              "the team page markup may have changed", file=out)
    now = dt.datetime.now(dt.timezone.utc)
    cutoff = now - dt.timedelta(days=days + 1)
    today = now.strftime("%Y-%m-%d")

    found, ok, failed = [], 0, 0
    if "engines" in stages:
        for kind, q in build_queries(cfg, staff):
            for name, url_for, parse in (("google", lambda q: google_url(q, days), parse_google),
                                         ("bing", bing_url, parse_bing)):
                try:
                    items = parse(http_get(url_for(q)))
                    ok += 1
                except (RuntimeError, ET.ParseError) as e:
                    failed += 1
                    print(f"::warning::{name} query failed ({q[:40]}): {e}", file=out)
                    continue
                finally:
                    time.sleep(delay)
                for it in items:
                    d = parse_date(it["published"])
                    if (d is not None and d < cutoff) or is_own(it, cfg) or is_ignored(it, cfg):
                        continue
                    verdict = classify(it, cfg, staff, kind)
                    if verdict is None:
                        continue
                    it["confidence"], it["reasons"], it["matched"] = verdict
                    it["query"] = q
                    it["published_iso"] = d.strftime("%Y-%m-%dT%H:%M:%SZ") if d else ""
                    found.append(it)
        if ok == 0:
            print("every search query failed — nothing to report", file=out)
            return 2, 0

    checked, state = ({} if report else load_checked()), load_state()
    before = json.dumps(state, sort_keys=True)
    known = set() if report else (
        {i["id"] for i in state["items"]} | {canon_url(i["url"]) for i in state["items"] if i.get("url")})
    reader = Reader(cfg, staff, cutoff, checked, today, delay=delay * 0.3, out=out, known=known)
    if "feeds" in stages:
        found += crawl_feeds(cfg, staff, cutoff, checked, today, delay=delay * 0.3, out=out, reader=reader)
    if "search" in stages:
        found += search_sites(cfg, staff, cutoff, reader, delay=delay * 0.3, out=out, deep=deep)
    if "podcasts" in stages:
        found += search_podcasts(cfg, cutoff, reader, delay=delay, out=out)

    merged = merge_found(found)
    settle(merged, state, cfg, checked, today, delay=delay * 0.5, out=out)
    merged = {k: m for k, m in merged.items() if RANK[m["confidence"]] >= RANK[min_conf]}
    press = load_site_press()
    for m in merged.values():
        m["on_site"] = on_site(m, press)

    if report:
        Path(report).write_text(render_report(list(merged.values()), today, days, staff), encoding="utf-8")
        print(f"inventory of {len(merged)} stories written to {report}", file=out)
        return 0, len(merged)

    fresh = update_state(state, merged, now.strftime("%Y-%m-%dT%H:%M:%SZ"))
    changed = json.dumps(state, sort_keys=True) != before

    digest, shown = render_digest(fresh, today, min_conf, staff)
    print(f"engine queries ok={ok} failed={failed} · staff watched={len(staff)} · stories matched={len(merged)} · "
          f"new={len(fresh)} · to review={shown}", file=out)
    print(digest if shown else "(nothing new to review)", file=out)

    if not dry_run:
        if changed:
            WATCH_DIR.mkdir(exist_ok=True)
            STATE_PATH.write_text(json.dumps(state, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        if shown:
            DIGEST_PATH.write_text(digest, encoding="utf-8")
        save_checked(checked)
    # A stage that answered nothing at all is broken, not quiet (every outlet
    # blocking the runner's IP looks, in the digest, exactly like no news). The
    # results of the stages that worked are still saved above; the workflow's
    # last step fails the job on `dead` so the triage workflow fires.
    dead = sorted(k for k, (answered, asked) in reader.health.items() if asked and not answered)
    if dead:
        print(f"::error::no answer from any source in: {', '.join(dead)}", file=out)
    gh = os.environ.get("GITHUB_OUTPUT")
    if gh:
        with open(gh, "a") as f:
            f.write(f"new={shown}\nchanged={'true' if changed and not dry_run else 'false'}\ndead={','.join(dead)}\n")
    return 0, shown


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--days", type=int, help="lookback window (default: config lookback_days)")
    ap.add_argument("--dry-run", action="store_true", help="search and report, write nothing")
    ap.add_argument("--only", help=f"comma-separated stages to run, from: {', '.join(STAGES)}")
    ap.add_argument("--deep", action="store_true", help="read each html outlet's pages_deep result pages, not just "
                                                       "pages (for an inventory; a daily run does not need it)")
    ap.add_argument("--report", metavar="FILE", help="write an inventory of everything found to FILE "
                                                    "(markdown) instead of updating state; implies --dry-run")
    a = ap.parse_args(argv)
    only = [x.strip() for x in a.only.split(",")] if a.only else None
    if only and not set(only) <= set(STAGES):
        ap.error(f"--only takes {', '.join(STAGES)}")
    code, _ = run(days=a.days, dry_run=a.dry_run, only=only, report=a.report, deep=a.deep)
    return code


if __name__ == "__main__":
    sys.exit(main())
