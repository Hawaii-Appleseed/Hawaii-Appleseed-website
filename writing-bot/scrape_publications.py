#!/usr/bin/env python3
"""
Scrape Hawaiʻi Appleseed content into the writing-bot corpus.

Two sources:
  - publications  → PDF policy briefs/reports  → publications/YYYY-MM-DD_slug.txt
  - blog          → inline HTML blog posts     → blog-posts/<year>/<title-slug>.txt

Idempotent and safe to run repeatedly (e.g. weekly from the content monitor):
  - publications skip if the dated output file already exists
  - blog posts skip if the title-slug file exists OR the body already lives in
    another blog file (content dedup, for legacy hand-named files), and a URL
    manifest (content-monitor/blog-urls.json) lets incremental runs stop early
    once they hit already-seen posts.

Filenames are derived from the post H1 title (matching the existing corpus
convention), NOT the URL slug — the two diverge on this site.

Usage:
  python scrape_publications.py --all                 # blog + publications
  python scrape_publications.py --blog                # blog only (full backfill)
  python scrape_publications.py --publications        # publications only
  python scrape_publications.py --all --stop-after-known 5 --max-pages 2  # incremental (monitor)
  python scrape_publications.py --blog --dry-run      # report, write nothing

Exit codes: 0 ok · 1 fetch error · 2 self-test failed (listing yielded 0 links).
"""

import argparse
import glob
import json
import os
import re
import sys
import time
import unicodedata
from datetime import datetime
from io import BytesIO
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from pdfminer.high_level import extract_text as pdf_extract_text
from pdfminer.pdfparser import PDFSyntaxError

BASE_URL = "https://hiappleseed.org"
ROOT = Path(__file__).parent
PUB_DIR = ROOT / "publications"
BLOG_DIR = ROOT / "blog-posts"
MONITOR_DIR = ROOT / "content-monitor"
BLOG_MANIFEST = MONITOR_DIR / "blog-urls.json"
BLOG_SOURCES = MONITOR_DIR / "blog-sources.json"  # {title-slug: live url} for source linking

PUB_STOP_DATE = datetime(2021, 8, 2)  # don't crawl publications older than this

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
}
session = requests.Session()
session.headers.update(HEADERS)


def log(msg):
    print(msg, flush=True)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def slugify(title: str) -> str:
    """Title → filename stem, matching the existing corpus naming.

    Lowercase; strip diacritics (kahakō) and ʻokina/apostrophes; collapse every
    other run of non-alphanumerics to a single hyphen. Reproduces the existing
    blog filenames including em-dash/ellipsis cases.
    """
    t = unicodedata.normalize("NFKD", title)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.lower()
    t = re.sub(r"[’'ʻ‘`]", "", t)        # apostrophes / ʻokina → nothing (no hyphen)
    t = re.sub(r"[^a-z0-9]+", "-", t)     # any other run → hyphen
    return t.strip("-")[:150]


def json_ld_date(soup: BeautifulSoup):
    """Return a datetime from JSON-LD datePublished, or None."""
    for sc in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(sc.string or "")
        except Exception:
            continue
        candidates = data if isinstance(data, list) else [data]
        for d in candidates:
            if isinstance(d, dict) and d.get("datePublished"):
                try:
                    return datetime.fromisoformat(d["datePublished"].replace("Z", "")).replace(tzinfo=None)
                except Exception:
                    pass
    return None


def load_manifest(path: Path) -> set:
    if path.exists():
        try:
            return set(json.loads(path.read_text()))
        except Exception:
            return set()
    return set()


def save_manifest(path: Path, urls: set):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sorted(urls), indent=2))


def load_blog_sources() -> dict:
    if BLOG_SOURCES.exists():
        try:
            return json.loads(BLOG_SOURCES.read_text())
        except Exception:
            return {}
    return {}


def save_blog_sources(mapping: dict):
    BLOG_SOURCES.parent.mkdir(parents=True, exist_ok=True)
    BLOG_SOURCES.write_text(json.dumps(mapping, indent=2, sort_keys=True))


# ---------------------------------------------------------------------------
# Blog
# ---------------------------------------------------------------------------

def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def load_existing_blog_bodies() -> list[str]:
    """Normalized text of every existing blog file, for content dedup."""
    bodies = []
    for p in glob.glob(str(BLOG_DIR / "**" / "*.txt"), recursive=True):
        try:
            bodies.append(_norm(Path(p).read_text(encoding="utf-8", errors="ignore")))
        except Exception:
            pass
    return bodies


def blog_listing_urls(max_pages):
    """Yield blog post URLs in listing order (newest first), paginating lazily.

    Lazy generator: the caller can stop consuming to avoid fetching older pages.
    """
    url = BASE_URL + "/blog"
    pages = 0
    seen = set()
    while url and (max_pages is None or pages < max_pages):
        r = session.get(url, timeout=30)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        pages += 1

        page_count = 0
        for a in soup.find_all("a", href=True):
            h = a["href"]
            if (
                h.startswith("/blog/")
                and h != "/blog/"
                and "/category/" not in h
                and "/author/" not in h
                and "/tag/" not in h
                and "?" not in h
            ):
                full = BASE_URL + h
                if full not in seen:
                    seen.add(full)
                    page_count += 1
                    yield full

        # self-test: a structural change that breaks extraction shows up as 0
        if pages == 1 and page_count == 0:
            raise RuntimeError("blog listing yielded 0 post links — site structure may have changed")

        next_url = None
        for a in soup.find_all("a", href=True):
            if "older" in a.get_text(strip=True).lower() and "offset" in a["href"]:
                next_url = a["href"] if a["href"].startswith("http") else BASE_URL + a["href"]
                break
        url = next_url
        if url:
            time.sleep(1)


def parse_blog_post(html: str):
    """Return (title, datetime|None, body_text)."""
    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.find("h1")
    title = h1.get_text(strip=True) if h1 else None
    date = json_ld_date(soup)
    body_el = soup.select_one("div.blog-item-content")
    body = body_el.get_text("\n", strip=True) if body_el else ""
    return title, date, body


def scrape_blog(max_pages, stop_after_known, since, dry_run):
    log("--- Blog ---")
    manifest = load_manifest(BLOG_MANIFEST)
    blog_sources = load_blog_sources()
    existing_bodies = load_existing_blog_bodies()
    new_files = []
    known_streak = 0
    old_streak = 0
    fetched = 0
    total_seen = 0

    for url in blog_listing_urls(max_pages):
        total_seen += 1

        if url in manifest:
            known_streak += 1
            if stop_after_known and known_streak >= stop_after_known:
                log(f"  hit {known_streak} consecutive known posts — stopping crawl")
                break
            continue
        known_streak = 0

        try:
            r = session.get(url, timeout=30)
            r.raise_for_status()
        except Exception as e:
            log(f"  ERROR fetching {url}: {e}")
            continue
        fetched += 1
        title, date, body = parse_blog_post(r.text)
        time.sleep(0.5)

        if not title or not body:
            log(f"  SKIP {url} (no title/body extracted)")
            continue
        if since and date and date < since:
            # listing is reverse-chronological; a run of old posts means we're past the horizon
            manifest.add(url)
            old_streak += 1
            if old_streak >= 3:
                log(f"  reached --since horizon ({since.date()}) — stopping crawl")
                break
            continue
        old_streak = 0

        slug = slugify(title)
        blog_sources[slug] = url  # record live URL for source linking (every fetched post)
        year = str(date.year) if date else "undated"
        out_path = BLOG_DIR / year / f"{slug}.txt"

        # idempotency: title-slug file already present in any year folder
        if out_path.exists() or any(
            (BLOG_DIR / y / f"{slug}.txt").exists() for y in os.listdir(BLOG_DIR)
            if (BLOG_DIR / y).is_dir()
        ):
            manifest.add(url)
            continue

        # content dedup: same body already saved under a different (legacy) name
        sig = _norm(body)[80:280]
        if sig and any(sig in b for b in existing_bodies):
            log(f"  DEDUP {slug} (body already in corpus under another filename) — {url}")
            manifest.add(url)
            continue

        date_str = date.date().isoformat() if date else "unknown"
        if dry_run:
            log(f"  NEW (dry-run) {year}/{slug}.txt  [{date_str}]  {len(body)} chars")
        else:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(f"{title}\n\n{body}\n", encoding="utf-8")
            existing_bodies.append(_norm(f"{title}\n\n{body}"))
            log(f"  SAVED {year}/{slug}.txt  [{date_str}]  {len(body)} chars")
        new_files.append(str(out_path.relative_to(ROOT)))
        manifest.add(url)

    if not dry_run:
        save_manifest(BLOG_MANIFEST, manifest)
        save_blog_sources(blog_sources)
    log(f"  blog: {total_seen} seen, {fetched} fetched, {len(new_files)} new")
    return new_files


def rebuild_blog_sources(max_pages=None):
    """Crawl the whole blog and write content-monitor/blog-sources.json {slug: url}.

    Backfill for source linking — covers every post, independent of which files
    are already saved. Run once after the initial backfill, or to repair the map.
    """
    log("--- Rebuilding blog source URLs ---")
    mapping = load_blog_sources()
    seen = 0
    for url in blog_listing_urls(max_pages):
        try:
            r = session.get(url, timeout=30)
            r.raise_for_status()
        except Exception as e:
            log(f"  ERROR fetching {url}: {e}")
            continue
        title, _date, _body = parse_blog_post(r.text)
        time.sleep(0.4)
        if title:
            mapping[slugify(title)] = url
            seen += 1
    save_blog_sources(mapping)
    log(f"  wrote {len(mapping)} blog source URLs ({seen} crawled this run)")
    return mapping


# ---------------------------------------------------------------------------
# Publications (PDF)
# ---------------------------------------------------------------------------

def pub_listing(url):
    """Fetch a publications listing page → (post_urls, next_url, oldest_date)."""
    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    seen, links = set(), []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if (
            href.startswith("/publications/")
            and href != "/publications/"
            and "/category/" not in href
            and "?" not in href
        ):
            full = BASE_URL + href
            if full not in seen:
                seen.add(full)
                links.append(full)

    oldest = None
    for t in soup.find_all("time", datetime=True):
        try:
            dt = datetime.fromisoformat(t["datetime"].replace("Z", "")).replace(tzinfo=None)
            if oldest is None or dt < oldest:
                oldest = dt
        except Exception:
            pass

    next_url = None
    for a in soup.find_all("a", href=True):
        if "older" in a.get_text(strip=True).lower() and "offset" in a["href"]:
            next_url = a["href"] if a["href"].startswith("http") else BASE_URL + a["href"]
            break
    return links, next_url, oldest


def parse_pub_post(url):
    """Return (title, datetime|None, pdf_url)."""
    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    title_el = soup.find("h1") or soup.find("h2")
    title = title_el.get_text(strip=True) if title_el else os.path.basename(url)

    date = json_ld_date(soup)
    if not date:
        for t in soup.find_all("time", datetime=True):
            try:
                val = t["datetime"]
                if len(val) > 6:
                    date = datetime.fromisoformat(val.replace("Z", "")).replace(tzinfo=None)
                    break
            except Exception:
                pass

    pdf_url = None
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if ".pdf" in href.lower():
            pdf_url = BASE_URL + href if href.startswith("/") else href if href.startswith("http") else None
            if pdf_url:
                break
    return title, date, pdf_url


def extract_pdf_text(pdf_url):
    try:
        resp = session.get(pdf_url, timeout=60)
        resp.raise_for_status()
        text = pdf_extract_text(BytesIO(resp.content))
        return text.strip() if text else None
    except PDFSyntaxError as e:
        log(f"    PDF parse error: {e}")
    except Exception as e:
        log(f"    error extracting PDF: {e}")
    return None


def scrape_publications(max_pages, since, dry_run):
    log("--- Publications ---")
    PUB_DIR.mkdir(parents=True, exist_ok=True)
    stop = since or PUB_STOP_DATE

    post_urls, page_url, pages = [], BASE_URL + "/publications", 0
    while page_url and (max_pages is None or pages < max_pages):
        try:
            links, next_url, oldest = pub_listing(page_url)
        except Exception as e:
            log(f"  error fetching listing: {e}")
            break
        pages += 1
        if pages == 1 and not links:
            raise RuntimeError("publications listing yielded 0 post links — site structure may have changed")
        post_urls.extend(links)
        if oldest and oldest <= stop:
            break
        if not next_url:
            break
        page_url = next_url
        time.sleep(1)

    # dedupe, preserve order
    post_urls = list(dict.fromkeys(post_urls))

    new_files = []
    for url in post_urls:
        slug = url.rstrip("/").split("/")[-1]
        try:
            title, date, pdf_url = parse_pub_post(url)
        except Exception as e:
            log(f"  error fetching {slug}: {e}")
            time.sleep(0.5)
            continue
        if date and date < stop:
            continue
        if not pdf_url:
            log(f"  SKIP {slug} (no PDF)")
            time.sleep(0.3)
            continue

        date_prefix = date.strftime("%Y-%m-%d") if date else "undated"
        out_path = PUB_DIR / f"{date_prefix}_{slug}.txt"
        if out_path.exists():
            continue

        if dry_run:
            log(f"  NEW (dry-run) {out_path.name}  ({title[:50]})")
            new_files.append(str(out_path.relative_to(ROOT)))
            time.sleep(0.3)
            continue

        text = extract_pdf_text(pdf_url)
        if not text:
            log(f"  SKIP {slug} (text extraction failed)")
            continue
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(f"Title: {title}\n")
            f.write(f"Date: {date.date() if date else 'unknown'}\n")
            f.write(f"URL: {url}\n")
            f.write(f"PDF: {pdf_url}\n")
            f.write("=" * 60 + "\n\n")
            f.write(text)
        log(f"  SAVED {out_path.name} ({len(text):,} chars)")
        new_files.append(str(out_path.relative_to(ROOT)))
        time.sleep(1)

    log(f"  publications: {len(post_urls)} seen, {len(new_files)} new")
    return new_files


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Scrape Hawaiʻi Appleseed content into the bot corpus.")
    ap.add_argument("--blog", action="store_true", help="scrape blog posts")
    ap.add_argument("--publications", action="store_true", help="scrape publications")
    ap.add_argument("--all", action="store_true", help="scrape both (default if none specified)")
    ap.add_argument("--max-pages", type=int, default=None, help="max listing pages to crawl per source")
    ap.add_argument("--stop-after-known", type=int, default=0,
                    help="blog: stop crawling after N consecutive already-seen posts (incremental)")
    ap.add_argument("--since", help="skip posts older than this date (YYYY-MM-DD)")
    ap.add_argument("--dry-run", action="store_true", help="report what would be fetched; write nothing")
    ap.add_argument("--rebuild-sources", action="store_true",
                    help="crawl the whole blog and rebuild content-monitor/blog-sources.json (source-link backfill); writes no .txt files")
    args = ap.parse_args()

    if args.rebuild_sources:
        try:
            rebuild_blog_sources(args.max_pages)
        except requests.RequestException as e:
            log(f"FETCH ERROR: {e}")
            sys.exit(1)
        return

    do_blog = args.blog or args.all or not (args.blog or args.publications)
    do_pubs = args.publications or args.all or not (args.blog or args.publications)
    since = datetime.fromisoformat(args.since) if args.since else None

    new = []
    try:
        if do_blog:
            new += scrape_blog(args.max_pages, args.stop_after_known, since, args.dry_run)
        if do_pubs:
            new += scrape_publications(args.max_pages, since, args.dry_run)
    except RuntimeError as e:
        log(f"SELF-TEST FAILED: {e}")
        sys.exit(2)
    except requests.RequestException as e:
        log(f"FETCH ERROR: {e}")
        sys.exit(1)

    log(f"\nNEW_FILES={len(new)}")
    for f in new:
        log(f"  {f}")


if __name__ == "__main__":
    main()
