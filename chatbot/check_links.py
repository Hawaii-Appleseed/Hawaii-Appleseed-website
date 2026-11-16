#!/usr/bin/env python3
"""Fetch every link the assistant can show and report any that do not answer 200.

Run before a deploy and after any site restructure; it caught that the home page's
"Stay Informed" card points at support#connect, an anchor that does not exist.
    python3 chatbot/check_links.py
Needs the network. Some third-party hosts refuse scripts; those show as WARN, not FAIL.
"""
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_index as b  # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 (compatible; ha-ask-link-check)"}
OURS = ("hiappleseed.org", "hitaxfairness.org")


def get(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception as e:  # noqa: BLE001
        return type(e).__name__


idx = b.build(public=False)
urls = {c["url"].split("#")[0] for c in idx["core"] if c["url"]}
urls |= {u for c in idx["core"] for u in c["research"]}
urls |= {p["p"] for p in idx["pubs"].values() if p["p"]}
bad = 0
for u in sorted(urls):
    st = get(u)
    ours = any(h in u for h in OURS)
    flag = "ok  " if st == 200 else ("FAIL" if ours else "WARN")
    bad += flag == "FAIL"
    if st != 200:
        print(f"{flag} {st} {u}")
print(f"{len(urls)} links checked, {bad} failing")
sys.exit(1 if bad else 0)
