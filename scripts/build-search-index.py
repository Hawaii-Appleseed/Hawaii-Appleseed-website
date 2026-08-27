#!/usr/bin/env python3
"""
Build search-index.json — the lightweight client-side index behind the
header search typeahead (see squarespace-header-search.html).

The typeahead is a hybrid: this index answers instantly from memory while
the visitor types, and a debounced call to Squarespace's own
/api/search/GeneralSearch fills in full-text matches a moment later. This
file only has to be good enough for "jump me to the obvious thing", so it
carries titles and URLs, not body text.

Why an index at all, when Squarespace has a search API? Measured against
the live endpoint: 270ms-5.6s latency (highly variable even within a single
burst) and 78-156KB per query at the default page size. That is fine for a
results page and far too slow and heavy to fire on every keystroke.

Three sources, deliberately:

  1. news.json          - blog posts, press mentions, press releases
  2. publications.json  - reports and briefs
  3. sitemap.xml        - the ~48 static pages (Our Team, Issues, the five
                          issue deep-dives, ...), which live in neither JSON
                          because they are Squarespace pages, not collection
                          items. Titles are fetched per page; there are only
                          ~48 so this stays cheap.

The sitemap is 5,297 URLs but most of it is noise: ~4,200 are
/blog/category/..., /tag/..., /author/... taxonomy pages that would be junk
autocomplete results. Those are dropped. Collection items are dropped too —
they come from the JSON files above, which carry categories and dates the
sitemap does not.

Run locally or via .github/workflows/sync-publications.yml (nightly), after
sync-news.py and sync-publications.py have refreshed their inputs.
"""
import concurrent.futures
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

SITE = "https://hiappleseed.org"
SITEMAP = f"{SITE}/sitemap.xml"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

NEWS_PATH = os.path.join(ROOT, "news.json")
PUBS_PATH = os.path.join(ROOT, "publications.json")
OUT_PATH = os.path.join(ROOT, "search-index.json")

UA = "hiappleseed-search-index/1.0 (+https://github.com/Hawaii-Appleseed)"

# Anything under these prefixes is a collection item; it comes from the JSON
# files, which know its category and publish date. The sitemap does not.
COLLECTION_PREFIXES = ("/blog/", "/in-the-news/", "/press-releases/", "/publications/")

# Squarespace emits a page per category/tag/author. ~4,200 of them here.
TAXONOMY_RE = re.compile(r"/(category|tag|author)/", re.I)

# Legacy duplicates and internals that should not surface in autocomplete.
# /home is the homepage and is added explicitly as "/" below.
STATIC_DENYLIST = {
    "/home", "/home1", "/food-equity1",
    "/blog-home",   # the code-block mirror of /blog
    "/lej", "/hibudget",  # legacy stubs
}

TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
# Squarespace renders "<page> &mdash; Hawaiʻi Appleseed"; keep the page part.
TITLE_SUFFIX_RE = re.compile(r"\s*[—–-]\s*Hawai.i Appleseed\s*$", re.I)


def fetch(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def clean_title(raw):
    t = html.unescape(raw or "").strip()
    t = re.sub(r"\s+", " ", t)
    return TITLE_SUFFIX_RE.sub("", t).strip()


def collection_items(news, pubs):
    """Blog / press / press-releases / publications, from the synced JSON."""
    out = []
    if news:
        for key, kind in (("blog", "blog"), ("press", "press"),
                          ("press_releases", "press")):
            for p in news.get(key) or []:
                url = p.get("fullUrl") or ""
                title = clean_title(p.get("title"))
                if not url or not title:
                    continue
                cats = p.get("categories") or []
                out.append({
                    "t": title,
                    "u": url,
                    "k": kind,
                    "c": cats[0] if cats else None,
                    "d": p.get("publishOn"),
                })
    if pubs:
        for p in pubs.get("items") or []:
            url = p.get("fullUrl") or ""
            title = clean_title(p.get("title"))
            if not url or not title:
                continue
            out.append({"t": title, "u": url, "k": "publication",
                        "c": None, "d": p.get("publishOn")})
    return out


def static_page_paths():
    """Static Squarespace pages from the sitemap, minus taxonomy + collections."""
    xml = fetch(SITEMAP)
    locs = re.findall(r"<loc>(.*?)</loc>", xml)
    if not locs:
        raise SystemExit(
            "ABORT: sitemap.xml returned no <loc> entries. The site structure "
            "or the sitemap URL probably changed; build-search-index.py needs "
            "updating rather than writing a truncated index."
        )
    paths = set()
    for loc in locs:
        path = re.sub(r"^https?://[^/]+", "", html.unescape(loc)).split("#")[0]
        if not path.startswith("/"):
            continue
        if TAXONOMY_RE.search(path):
            continue
        if path.startswith(COLLECTION_PREFIXES):
            continue
        if path in STATIC_DENYLIST:
            continue
        paths.add(path)
    # The sitemap lists the homepage as /home, which 200s but is not the URL
    # anyone should land on. Denylisted above; add the canonical "/" instead.
    paths.add("/")
    return sorted(paths)


def fetch_static_titles(paths):
    """Titles for the ~48 static pages. Cheap enough to just fetch each."""
    def one(path):
        try:
            body = fetch(SITE + path, timeout=20)
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            print(f"  warn: {path} -> {e}", file=sys.stderr)
            return None
        m = TITLE_RE.search(body)
        title = clean_title(m.group(1)) if m else ""
        if not title:
            print(f"  warn: {path} -> no <title>", file=sys.stderr)
            return None
        return {"t": title, "u": path, "k": "page", "c": None, "d": None}

    out = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for res in pool.map(one, paths):
            if res:
                out.append(res)
    return out


def main():
    news = load_json(NEWS_PATH)
    pubs = load_json(PUBS_PATH)
    if news is None:
        raise SystemExit(f"ABORT: could not read {NEWS_PATH}")

    items = collection_items(news, pubs)
    n_collection = len(items)

    paths = static_page_paths()
    print(f"Fetching titles for {len(paths)} static pages…")
    pages = fetch_static_titles(paths)
    items.extend(pages)

    # Same guard as sync-news.py: a source that silently goes empty would
    # otherwise wipe most of the index and ship a broken typeahead.
    previous = load_json(OUT_PATH) or {}
    prev_items = previous.get("items") or []
    if prev_items and len(items) < len(prev_items) * 0.5:
        raise SystemExit(
            f"ABORT: refusing to write search-index.json — item count "
            f"collapsed from {len(prev_items)} to {len(items)}. A source "
            f"feed is probably broken. Existing index left untouched."
        )
    if not items:
        raise SystemExit("ABORT: no items collected; refusing to write an empty index.")

    # Deterministic order so the nightly diff shows real content change only.
    items.sort(key=lambda i: (i["k"], i["u"]))

    out = {
        "_generated": (
            "DO NOT HAND-EDIT — regenerated by scripts/build-search-index.py "
            "via .github/workflows/sync-publications.yml (nightly)."
        ),
        "lastSynced": int(time.time() * 1000),
        "items": items,
    }
    with open(OUT_PATH, "w") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)

    size = os.path.getsize(OUT_PATH)
    by_kind = {}
    for i in items:
        by_kind[i["k"]] = by_kind.get(i["k"], 0) + 1
    print(
        f"Wrote {len(items)} items to {OUT_PATH} ({size/1024:.0f} KB raw) — "
        f"{n_collection} collection items, {len(pages)} static pages; "
        f"by kind: {by_kind}"
    )


if __name__ == "__main__":
    main()
