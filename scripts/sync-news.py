#!/usr/bin/env python3
"""
Sync blog posts and press mentions from hiappleseed.org into news.json.

Mirrors the publications sync pattern (scripts/sync-publications.py):
fetches the Squarespace JSON API for /blog and /in-the-news, paginates,
slims each item to the fields the page renderers actually use, and
writes a single news.json with three top-level keys: blog, press,
lastSynced.

Run locally or via the GitHub Action in
.github/workflows/sync-publications.yml.
"""
import http.client
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

SOURCES = {
    "blog":           "https://hiappleseed.org/blog?format=json",
    "press":          "https://hiappleseed.org/in-the-news?format=json",
    "press_releases": "https://hiappleseed.org/press-releases?format=json",
}
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "news.json")

# Map of sourceUrl hosts to canonical outlet display names. Used to
# normalize the "outlet" field on press items — author.bio sometimes
# carries an Appleseed-staffer biography (when staff co-author an
# op-ed) instead of the publishing outlet, so the URL host is a more
# reliable signal.
HOST_TO_OUTLET = {
    'www.civilbeat.org':         'Honolulu Civil Beat',
    'civilbeat.org':             'Honolulu Civil Beat',
    'www.staradvertiser.com':    'Honolulu Star-Advertiser',
    'staradvertiser.com':        'Honolulu Star-Advertiser',
    'www.hawaiipublicradio.org': 'Hawaiʻi Public Radio',
    'hawaiipublicradio.org':     'Hawaiʻi Public Radio',
    'www.khon2.com':             'KHON2',
    'khon2.com':                 'KHON2',
    'www.hawaiinewsnow.com':     'Hawaii News Now',
    'hawaiinewsnow.com':         'Hawaii News Now',
    'www.pbshawaii.org':         'PBS Hawaiʻi',
    'pbshawaii.org':             'PBS Hawaiʻi',
    'www.youtube.com':           'PBS Hawaiʻi',  # PBS Hawaiʻi archives content on YouTube
    'youtube.com':               'PBS Hawaiʻi',
    'www.mauinews.com':          'The Maui News',
    'mauinews.com':              'The Maui News',
    'www.thegardenisland.com':   'The Garden Island',
    'thegardenisland.com':       'The Garden Island',
    'www.bigislandnow.com':      'Big Island Now',
    'bigislandnow.com':          'Big Island Now',
    'www.kitv.com':              'KITV4',
    'kitv.com':                  'KITV4',
    'www.mauinow.com':           'Maui Now',
    'mauinow.com':               'Maui Now',
    'apnews.com':                'Associated Press',
    'www.apnews.com':            'Associated Press',
    'www.usnews.com':            'Associated Press',  # AP wire stories often republished via US News
    'www.overstoryhawaii.org':   'Overstory',
    'overstoryhawaii.org':       'Overstory',
    'www.hawaiibusiness.com':    'Hawaii Business',
    'hawaiibusiness.com':        'Hawaii Business',
}

_BIO_TAG_RE = re.compile(r"<[^>]+>")
# Heuristic: detect when author.bio is a person's biography rather
# than the outlet name (common for op-eds co-authored by Appleseed
# staff — the bio is then the staffer's title, not the outlet).
_BIO_TELLTALES_RE = re.compile(
    r"\b(is\s+(the|a)\s+(executive\s+director|president|director|founder|"
    r"editor|writer|reporter|policy|deputy|senior|associate|attorney|"
    r"researcher|analyst))\b",
    re.IGNORECASE,
)


def derive_outlet(item):
    """Return the cleanest available outlet display name for a press item.

    Order of preference:
    1. URL host mapped via HOST_TO_OUTLET (most reliable)
    2. author.bio if it's short and doesn't look like a biography
    3. Bare URL host (lowercase) as a fallback
    4. "Press" as last resort
    """
    raw_bio = (item.get("author") or {}).get("bio", "") or ""
    bio_text = _BIO_TAG_RE.sub("", raw_bio).strip()

    url = item.get("sourceUrl") or ""
    if url:
        host = (urllib.parse.urlparse(url).hostname or "").lower()
        if host in HOST_TO_OUTLET:
            return HOST_TO_OUTLET[host]
        if bio_text and len(bio_text) < 60 and not _BIO_TELLTALES_RE.search(bio_text):
            return bio_text
        return host or "Press"

    if bio_text and len(bio_text) < 60 and not _BIO_TELLTALES_RE.search(bio_text):
        return bio_text
    return "Press"


# Transient errors worth retrying: Squarespace occasionally returns a
# truncated chunked response (IncompleteRead / "invalid literal for int()
# with base 16") or drops the connection. These are intermittent, so a
# short backoff-and-retry clears them rather than failing the whole run.
_RETRYABLE = (
    http.client.IncompleteRead,
    http.client.HTTPException,
    urllib.error.URLError,
    ConnectionError,
    TimeoutError,
    # ValueError also covers json.JSONDecodeError from a partial body and the
    # "invalid literal for int() with base 16" chunk-size error.
    ValueError,
)


def fetch_page(url, retries=4, backoff=2.0):
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                # Read the full body first so a truncated chunked response
                # raises here (retryable) rather than mid-parse.
                body = r.read()
            return json.loads(body)
        except _RETRYABLE as e:
            last_err = e
            if attempt < retries:
                wait = backoff * attempt
                print(f"  fetch failed ({type(e).__name__}: {e}); "
                      f"retry {attempt}/{retries - 1} in {wait:.0f}s")
                time.sleep(wait)
    raise RuntimeError(f"fetch_page failed after {retries} attempts: {url}") from last_err


def slim_blog(item):
    """Slim a /blog item to the fields the issue-page renderer uses.

    author here is a small dict with just displayName — the Squarespace
    response carries a richer object (firstName, lastName, bio, avatar,
    etc.) but the page renderer only ever uses the visible name.
    """
    author = item.get("author") or {}
    return {
        "id":         item.get("id", ""),
        "title":      item.get("title", ""),
        "excerpt":    item.get("excerpt", ""),
        "fullUrl":    item.get("fullUrl", ""),
        "publishOn":  item.get("publishOn", 0),
        "categories": item.get("categories", []),
        "tags":       item.get("tags", []),
        "author":     {"displayName": author.get("displayName", "")},
        # Post image, served off the Squarespace CDN. Kept as the bare
        # original URL — renderers append ?format=<width>w to get a
        # thumbnail rather than the ~2500px original.
        "assetUrl":   item.get("assetUrl", ""),
    }


def slim_press(item):
    """Slim an /in-the-news item.

    Press mentions carry an extra `sourceUrl` (external link to the
    outlet's story) plus author.bio (often the outlet name, but
    sometimes the staffer biography on co-authored op-eds — see
    derive_outlet for the normalization).

    The slimmed item carries:
      - the original author.{displayName, bio} for transparency
      - a NEW "outlet" field with the resolved, render-ready display
        name (preferred by the page renderers)
    """
    author = item.get("author") or {}
    return {
        "id":         item.get("id", ""),
        "title":      item.get("title", ""),
        "excerpt":    item.get("excerpt", ""),
        "fullUrl":    item.get("fullUrl", ""),
        "sourceUrl":  item.get("sourceUrl", ""),
        "publishOn":  item.get("publishOn", 0),
        "categories": item.get("categories", []),
        "tags":       item.get("tags", []),
        "author": {
            "displayName": author.get("displayName", ""),
            "bio":         author.get("bio", ""),
        },
        "outlet":     derive_outlet(item),
    }


# Press releases are a Squarespace blog-type collection (internal content
# with fullUrl, no external sourceUrl), so they slim the same way as blog.
SLIMMERS = {"blog": slim_blog, "press": slim_press, "press_releases": slim_blog}


def fetch_all(name, source_url):
    """Walk paginated Squarespace results and collect every item."""
    items = []
    url = source_url
    while url:
        data = fetch_page(url)
        page = data.get("items", [])
        items.extend(page)
        print(f"  [{name}] page fetched: {len(page)} items (running total: {len(items)})")

        pagination = data.get("pagination", {})
        if pagination.get("nextPage") and pagination.get("nextPageOffset"):
            url = f"{source_url}&offset={pagination['nextPageOffset']}"
            time.sleep(0.5)  # be polite
        else:
            url = None
    return items


def load_existing(path):
    """Previous news.json, or {} on first run / unreadable file."""
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def main():
    out_path = os.path.abspath(OUT_PATH)
    previous = load_existing(out_path)

    output = {}
    for name, source_url in SOURCES.items():
        print(f"Fetching {name} from {source_url} ...")
        raw_items = fetch_all(name, source_url)
        slim = SLIMMERS[name]
        slimmed = [slim(i) for i in raw_items]
        # Sort newest-first by publishOn so renderers can take items[0].
        slimmed.sort(key=lambda i: i.get("publishOn", 0), reverse=True)
        output[name] = slimmed
        print(f"  [{name}] slimmed: {len(slimmed)} items")

    # A Squarespace collection that gets renamed, unpublished, or replaced by
    # a static page still answers 200 with zero items — indistinguishable from
    # a healthy empty feed. Writing that through silently wipes a section of
    # the site, so refuse to overwrite a non-empty feed with nothing and let
    # the workflow fail loudly instead.
    emptied = [
        name for name in SOURCES
        if not output[name] and previous.get(name)
    ]
    if emptied:
        detail = ", ".join(
            f"{n} (had {len(previous[n])}, got 0)" for n in emptied
        )
        raise SystemExit(
            f"ABORT: refusing to write news.json — {detail}. "
            "The source collection is probably renamed, unpublished, or "
            "shadowed by a static page at the same slug. Existing "
            "news.json left untouched."
        )

    output["lastSynced"] = int(time.time() * 1000)

    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    print(
        f"Wrote {len(output['blog'])} blog posts, {len(output['press'])} press "
        f"mentions, and {len(output['press_releases'])} press releases to {out_path}"
    )


if __name__ == "__main__":
    main()
