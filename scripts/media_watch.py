#!/usr/bin/env python3
"""
Daily media watch: find news stories that mention Hawaiʻi Appleseed, its work,
or its staff, and say which ones the In the News page does not carry yet.

Sources (both free, no key, both RSS):
  * Google News search  — broad, but article links are opaque redirects.
  * Bing News search    — narrower, but links carry the real article URL,
                          which is what lets a story be matched to In the News.
GDELT was left out on purpose: its own rate limit answers with a plain-text
notice that reads as "zero results", so a quiet day and a blocked day look the
same. See Legislative-Research-Tool/testimony/media.py for that history.

What it does each run:
  1. Reads search terms from media-watch/config.json and the staff names from
     our-team.html (so a new hire is watched the day the team page lists them).
  2. Queries both sources, keeps stories inside the lookback window.
  3. Decides for each story WHY it matched and how sure that is:
        high    the org name, "Hawaii Appleseed", is in the headline/snippet
        medium  "Appleseed" with Hawaii context; a named staff member with
                Hawaii + policy context; or one of config work_terms
        low     a staff name and nothing else (a stranger with the same name
                looks exactly like this) — DROPPED, never stored
  4. De-duplicates across sources and against media-watch/mentions.json.
  5. Checks each story against news.json's `press` items (the In the News
     page) so the digest lists only stories nobody has posted yet.

Outputs:
  media-watch/mentions.json   every kept story, with status. The script never
                              overwrites `status`; staff may set it by hand
                              ("added", "ignore") to stop a story resurfacing.
  media-watch/latest.md       the digest of stories first seen this run
                              (only written when there are some).

The repo is PUBLIC and Pages serves the whole tree, so mentions.json is public.
That is why low-confidence matches are never written to it.

Usage:
    python3 scripts/media_watch.py                 # a normal daily run
    python3 scripts/media_watch.py --days 30       # backfill a month
    python3 scripts/media_watch.py --dry-run       # search and report, write nothing
Exit codes: 0 ok (partial source failures print warnings), 2 every query failed.
"""
import argparse
import base64
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
    s = re.sub(r"[’'‘`]s\b", "", s)
    s = re.sub(r"[ʻʼ’'‘`]", "", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return s.strip()


def has_phrase(text, phrase):
    """Whole-word phrase test on already-normalised text."""
    p = norm(phrase)
    return bool(p) and re.search(r"(?<![a-z0-9])" + re.escape(p) + r"(?![a-z0-9])", text) is not None


def strip_tags(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def title_key(title):
    return re.sub(r"\s", "", norm(title))[:90]


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


def fetch_article_text(url, limit=1_500_000):
    """Visible text of an article page, or None if it could not be read.
    A paywall or bot wall returns None or a shell; callers must treat
    "no mention found" as evidence only when the page really loaded."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,*/*"})
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read(limit).decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return None
    raw = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", raw)
    text = trim_chrome(strip_tags(raw))
    return text if len(text) > 400 else None


# "Read this next: <another story>", "Most read", "Related coverage": headlines
# of other stories, which would otherwise make one story mention another's
# staff. Only cut in the back half, so a story that opens with "Related:" survives.
CHROME = re.compile(r"(read this next|related (stories|articles|coverage|posts|reading)|most (read|popular)|"
                    r"you (may|might) also like|more from|trending now|recommended for you)", re.I)


def trim_chrome(text):
    for m in CHROME.finditer(text):
        if m.start() > len(text) * 0.4:
            return text[: m.start()]
    return text


# -------------------------------------------------------------------- sources


def http_get(url, timeout=25, retries=2):
    last = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/rss+xml, text/xml, */*"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", "replace")
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"{url[:90]}… : {last}")


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
        for c in e:
            tag = c.tag.split("}")[-1].lower()
            if tag == "title":
                title = (c.text or "").strip()
            elif tag == "link":
                link = link or (c.get("href") or (c.text or "")).strip()
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
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


MAX_ARTICLE_READS = 400  # first run reads a few hundred; later runs read only what is new


def crawl_feeds(cfg, staff, cutoff, checked, today, delay=0.3, out=sys.stdout):
    """Read every new story in the outlets' own feeds, in full, and keep those
    that name Appleseed or its staff.

    This is the half that finds body-only mentions ("said Devin Thomas of
    Hawaiʻi Appleseed"), which the news search engines never index. Each story
    is read once: `checked` remembers it (id -> date). A story whose page will
    not load is remembered too, and counted per outlet in the run report, so a
    paywalled outlet shows up as blind rather than as quiet."""
    found, reads = [], 0
    blind, seen_total = {}, 0
    for feed in cfg.get("outlet_feeds", []):
        name = feed["name"]
        try:
            items = parse_feed(http_get(feed["url"], timeout=20, retries=1), name)
        except (RuntimeError, ET.ParseError) as e:
            print(f"::warning::feed {name} failed: {e}", file=out)
            continue
        finally:
            time.sleep(delay)
        for it in items:
            d = parse_any_date(it["published"])
            if d is not None and d < cutoff:
                continue
            iid = story_id(title_key(it["title"]))
            if iid in checked or is_own(it, cfg):
                continue
            seen_total += 1
            text = it["snippet"]
            if len(text) < 1500 and reads < MAX_ARTICLE_READS:   # an excerpt, not the story
                reads += 1
                page = fetch_article_text(it["url"])
                time.sleep(delay)
                if page is None:
                    blind[name] = blind.get(name, 0) + 1
                else:
                    text = page
            verdict = classify({"title": it["title"], "snippet": text}, cfg, staff, full_text=len(text) >= 1500)
            if verdict is None or verdict[0] == "low":
                checked[iid] = today   # a miss is remembered; a hit is remembered by mentions.json
                continue
            it["confidence"], it["reasons"], it["matched"] = verdict
            it["query"] = f"feed: {name}"
            it["published_iso"] = d.strftime("%Y-%m-%dT%H:%M:%SZ") if d else ""
            found.append(it)
    note = f" · could not read: {', '.join(f'{k} ×{v}' for k, v in blind.items())}" if blind else ""
    print(f"feeds: {seen_total} new stories read{note}", file=out)
    return found


def load_checked(path=CHECKED_PATH, keep_days=14):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    floor = (dt.date.today() - dt.timedelta(days=keep_days)).isoformat()
    return {k: v for k, v in data.items() if isinstance(v, str) and v >= floor}


def save_checked(checked, path=CHECKED_PATH):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(checked, sort_keys=True), encoding="utf-8")


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
    and lede. Then a staff name proves nothing without the word Appleseed: an
    article that merely says "Devin Thomas" near "tax" is far more likely to
    be about someone else than a headline that does."""
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
    elif appleseed and hawaii:
        bump("medium", "“Appleseed” with Hawaiʻi context")
    for name in staff:
        if not has_phrase(text, name):
            continue
        if appleseed:
            bump("medium", f"staff: {name}, with Appleseed", name)
        elif hawaii and policy and not full_text:
            bump("medium", f"staff: {name}, with Hawaiʻi policy context", name)
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


def is_weak(rec):
    """Needs the article read before it is believed: a bare staff name, or a
    match nobody has seen the words of."""
    return rec["confidence"] == "low" or rec["reasons"] == [UNCHECKED]


def verify_article(text, cfg):
    """Judge an article's full text. Returns (confidence, reason), or None if
    it never mentions Appleseed."""
    t = norm(text)
    if has_phrase(t, "hawaii appleseed") or has_phrase(t, "appleseed center for law and economic justice"):
        return "high", "article text names Hawaiʻi Appleseed"
    if has_phrase(t, "appleseed") and any(has_phrase(t, w) for w in cfg.get("hawaii_context", [])):
        return "medium", "article text mentions Appleseed, with Hawaiʻi context"
    return None


def merge_found(found):
    """One entry per story. The same story from two sources, or from two
    queries, is merged; the direct URL beats a Google redirect."""
    by_key = {}
    for f in found:
        k = title_key(f["title"])
        if not k:
            continue
        cur = by_key.get(k)
        if cur is None:
            by_key[k] = {**f, "sources": [f["source"]], "queries": [f.get("query", "")]}
            continue
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


def load_site_press(path=NEWS_PATH):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
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


def is_own(item, cfg):
    hosts = {host_of(item.get("outlet_url", "")), host_of(item["url"])}
    return any(h == d or h.endswith("." + d) for h in hosts if h for d in cfg.get("own_domains", []))


# ---------------------------------------------------------------------- state


def load_state(path=STATE_PATH):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"_generated": "Written by scripts/media_watch.py. `status` is the one field a person may edit "
                              "(new | added | ignore); the script never overwrites it.", "items": []}


def story_id(key):
    return hashlib.sha1(key.encode()).hexdigest()[:12]


def update_state(state, merged, now_iso):
    """Fold this run's stories into state. Returns the items first seen now."""
    by_id = {i["id"]: i for i in state["items"]}
    fresh = []
    for key, m in merged.items():
        iid = story_id(key)
        rec = by_id.get(iid)
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


def render_digest(items, today, min_conf):
    show = [i for i in items if RANK[i["confidence"]] >= RANK[min_conf] and not i.get("onSite")]
    lines = [f"# Media watch — {today}", "",
             f"{len(show)} new {'story' if len(show) == 1 else 'stories'} mentioning Hawaiʻi Appleseed, "
             "its work, or its staff, not yet on [In the News](https://hiappleseed.org/in-the-news).", ""]
    for level, head in (("high", "Names Hawaiʻi Appleseed"), ("medium", "Its work or its staff")):
        group = [i for i in show if i["confidence"] == level]
        if not group:
            continue
        lines += [f"## {head}", ""]
        for i in group:
            when = (i.get("published") or "")[:10]
            lines.append(f"- [{i['title']}]({i['url']}) — {i['outlet'] or 'unknown outlet'}, {when}  ")
            lines.append(f"  _{'; '.join(i['reasons'])}_")
        lines.append("")
    lines += ["To post one: add it to the Squarespace `/in-the-news` collection. To stop one resurfacing, "
              "set its `status` to `ignore` in `media-watch/mentions.json`.", ""]
    return "\n".join(lines), len(show)


# ------------------------------------------------------------------------ run


MAX_RESOLVE = 40   # Google links resolved per run (two requests each)
MAX_VERIFY = 30    # articles read per run


def settle(merged, state, cfg, checked, today, delay=0.5, out=sys.stdout):
    """Turn feed guesses into facts, for stories not already known.

    Resolves opaque Google links to the real URL (which also lets on_site()
    match by URL), then reads the article behind every weak match. A page that
    loads and never says Appleseed is a rejection, remembered in
    `checked` so it is not fetched again tomorrow. A page that will not
    load leaves the match as it was: an unchecked engine match stays, a bare
    staff name is dropped by the confidence filter. Mutates `merged`."""
    known = {i["id"] for i in state["items"]}
    resolved = read = 0
    for key in list(merged):
        m, iid = merged[key], story_id(key)
        if iid in known:
            continue
        if iid in checked:
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
        m["reasons"] = [r for r in m["reasons"] if r != UNCHECKED and not r.endswith(" only")] + [verdict[1]]
    print(f"resolved {resolved} links, read {read} articles", file=out)


def run(days=None, dry_run=False, delay=REQUEST_DELAY, out=sys.stdout):
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    days = days or cfg.get("lookback_days", 3)
    min_conf = cfg.get("min_confidence", "medium")
    staff = read_staff(cfg)
    if len(staff) < 3:
        print(f"::warning::only {len(staff)} staff names read from {cfg.get('staff_from')}; "
              "the team page markup may have changed", file=out)
    queries = build_queries(cfg, staff)
    now = dt.datetime.now(dt.timezone.utc)
    cutoff = now - dt.timedelta(days=days + 1)

    found, ok, failed = [], 0, 0
    for kind, q in queries:
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
                if d is not None and d < cutoff:
                    continue
                if is_own(it, cfg):
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

    today = now.strftime("%Y-%m-%d")
    checked = load_checked()
    found += crawl_feeds(cfg, staff, cutoff, checked, today, delay=delay * 0.3, out=out)
    merged = merge_found(found)
    state = load_state()
    before = json.dumps(state, sort_keys=True)
    settle(merged, state, cfg, checked, today, delay=delay * 0.5, out=out)
    merged = {k: m for k, m in merged.items() if RANK[m["confidence"]] >= RANK[min_conf]}
    press = load_site_press()
    for m in merged.values():
        m["on_site"] = on_site(m, press)

    fresh = update_state(state, merged, now.strftime("%Y-%m-%dT%H:%M:%SZ"))
    changed = json.dumps(state, sort_keys=True) != before

    digest, shown = render_digest(fresh, today, min_conf)
    print(f"queries ok={ok} failed={failed} · staff watched={len(staff)} · stories matched={len(merged)} · "
          f"new={len(fresh)} · to review={shown}", file=out)
    print(digest if shown else "(nothing new to review)", file=out)

    if not dry_run:
        if changed:
            WATCH_DIR.mkdir(exist_ok=True)
            STATE_PATH.write_text(json.dumps(state, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        if shown:
            DIGEST_PATH.write_text(digest, encoding="utf-8")
        save_checked(checked)
    gh = os.environ.get("GITHUB_OUTPUT")
    if gh:
        with open(gh, "a") as f:
            f.write(f"new={shown}\nchanged={'true' if changed and not dry_run else 'false'}\n")
    return 0, shown


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--days", type=int, help="lookback window (default: config lookback_days)")
    ap.add_argument("--dry-run", action="store_true", help="search and report, write nothing")
    a = ap.parse_args(argv)
    code, _ = run(days=a.days, dry_run=a.dry_run)
    return code


if __name__ == "__main__":
    sys.exit(main())
