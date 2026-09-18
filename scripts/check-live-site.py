#!/usr/bin/env python3
"""
Is what's published still wired to what this repo builds?

Everything here is checkable without a browser, which is the point — the live
pages render their cards client-side, so a screenshot proves nothing anyway
(CLAUDE.md says as much). These assertions test the *inputs* to that render
instead, and between them they cover the ways it has actually broken:

  1. paste drift   — every live page still contains the payload committed here.
                     STALE means someone edited in Squarespace, or a --go was
                     started and never finished with the SAVE click.

  2. asset hosts   — every github.io URL the live pages reference resolves.
                     This is the generic form of the 2026-08-11 outage: the repo
                     moved to the Hawaii-Appleseed org, GitHub Pages does not
                     follow the repo-transfer redirect, and every
                     dtomkatsu.github.io URL baked into an already-pasted page
                     went dead. Images broke visibly; publications.json broke
                     silently, because the homepage's Latest section answers a
                     failed fetch with a line of prose that reads like ordinary
                     copy. This check does not know that host is bad — it asks
                     whether the URLs on the page resolve, so the next host move
                     is caught the same day without anyone anticipating it.

  3. data files    — publications.json / news.json on Pages still fetch and
                     parse, with a non-empty items list.

Exit 1 if any check fails. Alerting is triage.yml's job: it watches this
workflow by name, so a failure here opens a triage issue with the cause in it
and pushes to ntfy, and canary.yml's escalation job re-nags daily until the
issue is closed.

Run it locally the same way CI does:  python3 scripts/check-live-site.py
"""
import html
import json
import os
import re
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import squarespace as sq
import build_squarespace as bs

UA = "Mozilla/5.0 (check-live-site.py)"

# Any URL on a live page pointing at a GitHub Pages host. Stops at whitespace,
# quotes, brackets and backslashes, which is every delimiter these appear behind
# in the payload (href/src attributes, CSS url(), JS string literals).
GITHUB_IO_URL = re.compile(r"""https?://[A-Za-z0-9.-]+\.github\.io/[^\s"'()<>\\]+""")

# The data files the live pages fetch at runtime off Pages.
DATA_FILES = ("publications.json", "news.json")

# Deliberately loose. sync-publications.yml only commits — and so only bumps
# lastSynced — when Squarespace actually returned new content, so a quiet week
# with no new posts is normal and a tight threshold here would alert on nothing.
# "Did the sync run at all" is canary.yml's job, watching the workflow's own
# schedule. This only catches the file going permanently cold.
MAX_LASTSYNCED_DAYS = 14


def fetch(url, method="GET"):
    """(status, body) — status is an int, or a string when the request never
    got far enough to have one."""
    req = urllib.request.Request(url, method=method, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status, (r.read() if method == "GET" else b"")
    except urllib.error.HTTPError as e:
        # Not every host allows HEAD; fall back rather than report a false 405.
        if method == "HEAD" and e.code in (403, 405, 501):
            return fetch(url, "GET")
        return e.code, b""
    except Exception as e:  # URLError, timeout, bad TLS, DNS
        return "%s: %s" % (type(e).__name__, e), b""


def check_drift():
    """1. Live pages vs the payloads committed here."""
    print("== 1. paste drift ==\n")
    print("live pages vs the payloads in this repo:\n")
    rc = sq.status()
    return rc


def live_page_html():
    """The page bodies status() just fetched, by URL.

    Read from its cache rather than re-fetching: Squarespace 429s a fast sweep
    of every page, which is why fetch_live paces and caches in the first place.
    One GET per page per run, shared by both checks.
    """
    pages = {}
    for _, rel in sq.live_targets():
        path = sq.live_path(rel)
        if not path:
            continue
        url = sq.SITE + ("" if path == "/" else path)
        if url in sq._LIVE_CACHE:
            pages[url] = sq._LIVE_CACHE[url]
    return pages


def check_asset_hosts(pages):
    """2. Every github.io URL the live pages reference still resolves."""
    print("\n== 2. asset hosts referenced by live pages ==\n")

    if not pages:
        print("  no live page was reachable — nothing to scan")
        print("  FAIL: could not read a single page from %s" % sq.SITE)
        return 1

    found = {}  # url -> set of pages referencing it
    for url, body in pages.items():
        for m in GITHUB_IO_URL.finditer(html.unescape(body)):
            asset = m.group(0).rstrip(".,;:")
            found.setdefault(asset, set()).add(url)

    if not found:
        # Every live page should reference the Pages host for at least its
        # assets. None at all means the pages are not the ones we think.
        print("  FAIL: %d pages scanned, not one github.io URL among them"
              % len(pages))
        return 1

    expected_host = bs.ASSET_BASE.split("/")[2]
    bad = []
    for asset in sorted(found):
        code, _ = fetch(asset, "HEAD")
        ok = code == 200
        host = asset.split("/")[2]
        note = "" if host == expected_host else "  <- not %s" % expected_host
        print("  %-6s %s%s" % (code if ok else "FAIL", asset, note))
        if not ok:
            bad.append((asset, code, sorted(found[asset])))

    print("\n  %d github.io URL(s) across %d live page(s); %d broken"
          % (len(found), len(pages), len(bad)))
    for asset, code, refs in bad:
        print("  BROKEN %s (%s)" % (asset, code))
        for ref in refs:
            print("           referenced by %s" % ref)
    return 1 if bad else 0


def check_data_files():
    """3. The JSON the live pages fetch at runtime is served and parses."""
    print("\n== 3. data files on Pages ==\n")
    import time

    rc = 0
    for name in DATA_FILES:
        url = bs.ASSET_BASE + name
        code, body = fetch(url)
        if code != 200:
            print("  FAIL   %s -> %s" % (url, code))
            rc = 1
            continue
        try:
            data = json.loads(body)
        except ValueError as e:
            print("  FAIL   %s -> 200 but does not parse (%s)" % (url, e))
            rc = 1
            continue

        items = data.get("items")
        if items is None:  # news.json groups by kind instead
            items = [x for k in ("blog", "press", "press_releases")
                     for x in data.get(k, [])]
        if not items:
            print("  FAIL   %s -> parses but has no items" % url)
            rc = 1
            continue

        synced = data.get("lastSynced")
        age_d = (time.time() * 1000 - synced) / 86400000.0 if synced else None
        stale = age_d is not None and age_d > MAX_LASTSYNCED_DAYS
        print("  %-6s %s -> %d items, lastSynced %s"
              % ("FAIL" if stale else "ok", url, len(items),
                 "%.1f days ago" % age_d if age_d is not None else "absent"))
        if stale:
            print("         over the %d-day limit — the file has gone cold"
                  % MAX_LASTSYNCED_DAYS)
            rc = 1
    return rc


def main():
    drift = check_drift()
    assets = check_asset_hosts(live_page_html())
    data = check_data_files()

    print("\n== summary ==\n")
    for label, rc in (("paste drift", drift), ("asset hosts", assets),
                      ("data files", data)):
        print("  %-12s %s" % (label, "FAIL" if rc else "ok"))
    failed = drift or assets or data
    print("\n%s" % ("one or more checks failed" if failed else "all checks passed"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
