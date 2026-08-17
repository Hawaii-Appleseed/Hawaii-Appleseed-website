#!/usr/bin/env python3
"""
Fully automated Squarespace publish: rebuild a page's payload and drive the
Squarespace editor to paste and save it. No clipboard, no DevTools, no
hand-pasting.

    .venv/bin/python scripts/publish_squarespace.py --login      # once, ever
    .venv/bin/python scripts/publish_squarespace.py our-team --dry-run
    .venv/bin/python scripts/publish_squarespace.py our-team

`--login` opens a browser so you can sign in to Squarespace once; the session
is kept in .sqs-profile/ (gitignored) and reused forever after.

Then each run: rebuilds the payload via squarespace.py, opens the page in the
editor, replaces the Code Block's contents, and clicks SAVE. `--dry-run` does
everything except the final SAVE click and leaves the browser open so you can
look at it.

The payload is injected straight from the local file, so — unlike the
`--snippet` flow — this needs no push and no GitHub Pages round trip.

Editor mechanics (verified live, see README "Pasting from the browser"):
Squarespace's code editor is CodeMirror 6 with no EditorView on the DOM, so
the document is replaced through the two events CM6 listens for: a synthetic
Mod-A keydown (its keymap selects the whole STATE; a DOM Selection cannot,
because CM6 only renders the visible lines) followed by a synthetic paste
carrying a DataTransfer. Squarespace's change tracking observes that paste,
which is what re-enables SAVE.
"""
import argparse
import json
import os
import subprocess
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILE = os.path.join(ROOT, ".sqs-profile")
SITE = "https://hiappleseed.org"
PAGES_URL = SITE + "/config/pages"

# target -> the page's title as it appears in the editor's Pages sidebar.
# Filename != live slug != sidebar title, so this is its own mapping; the
# slugs live in INTERNAL_LINK_MAP in build_squarespace.py.
PAGE_TITLES = {
    "index": "Home",
    "home": "Home",
    "our-mission": "Our Mission",
    "our-story": "Our History",
    "our-team": "Our Team",
    "board-of-directors": "Board of Directors",
    "issues": "Issues",
    "taxes-budget": "Taxes & Budget",
    "food-security": "Food Equity",
    "housing": "Affordable Housing",
    "transportation": "Transportation Equity",
    "wages-labor": "Wages & Labor",
    "publications": "Publications",
    "in-the-news": "In the News",
    "support": "Support",
}

# The JS that does the actual replacement, run inside the editor page.
INJECT_JS = """
(text) => {
  const c = document.querySelector('.cm-content');
  if (!c) throw new Error('code editor (.cm-content) not found');
  c.focus();
  c.dispatchEvent(new KeyboardEvent('keydown', {key:'a', code:'KeyA', metaKey:true,
    keyCode:65, which:65, bubbles:true, cancelable:true}));
  const d = new DataTransfer();
  d.setData('text/plain', text);
  const ev = new ClipboardEvent('paste', {clipboardData:d, bubbles:true, cancelable:true});
  c.dispatchEvent(ev);
  return {handled: ev.defaultPrevented, chars: text.length};
}
"""


def rebuild(target):
    """Rebuild the payload via squarespace.py and return (rel_path, text)."""
    out = subprocess.run(
        [sys.executable, os.path.join(ROOT, "scripts", "squarespace.py"),
         target, "--no-copy"],
        capture_output=True, text=True, cwd=ROOT)
    if out.returncode != 0:
        sys.exit("rebuild failed:\n" + out.stdout + out.stderr)
    rel = out.stdout.strip().splitlines()[-1].strip()
    path = os.path.join(ROOT, rel)
    if not os.path.exists(path):
        sys.exit("rebuild did not produce a file (got %r)" % rel)
    with open(path, encoding="utf-8") as f:
        return rel, f.read()


def page_title(target):
    if target in PAGE_TITLES:
        return PAGE_TITLES[target]
    # Fall back to the live site's own title for the slug.
    try:
        with urllib.request.urlopen("%s/%s?format=json" % (SITE, target), timeout=15) as r:
            return json.load(r).get("collection", {}).get("title")
    except Exception:
        return None


def run(target, dry_run, keep_open, block_index):
    from playwright.sync_api import sync_playwright

    rel, payload = rebuild(target)
    title = page_title(target)
    if not title:
        sys.exit("Don't know which Squarespace page '%s' is. Add it to "
                 "PAGE_TITLES in this script." % target)
    print("payload : %s (%d chars)" % (rel, len(payload)))
    print("page    : %s" % title)

    with sync_playwright() as p:
        ctx = _launch(p, {"width": 1500, "height": 950})
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.set_default_timeout(45000)

        page.goto(PAGES_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        if "/config" not in page.url or _needs_login(page):
            ctx.close()
            sys.exit("Not logged in. Run once with --login, sign in, then retry.")

        # 1. Pick the page in the Pages sidebar.
        item = page.get_by_text(title, exact=True).first
        item.click()
        page.wait_for_timeout(2500)

        # 2. Enter edit mode.
        page.get_by_role("button", name="EDIT", exact=False).first.click()
        page.wait_for_timeout(3000)

        # 3. Open the Code Block's editor. The block is inside the same-origin
        #    site preview iframe; double-clicking near its TOP edge opens the
        #    editor without landing on the embed's own interactive content.
        frame = page.frame_locator("#sqs-site-frame")
        blocks = frame.locator(".sqs-block-code")
        n = blocks.count()
        if n == 0:
            _fail(ctx, "no Code Block found on this page")
        if n > 1 and block_index is None:
            _fail(ctx, "%d Code Blocks on this page; pass --block-index 0..%d"
                       % (n, n - 1))
        block = blocks.nth(block_index or 0)
        box = block.bounding_box()
        block.dblclick(position={"x": min(box["width"] / 2, 400), "y": 40})
        page.wait_for_selector(".cm-content", timeout=30000)
        page.wait_for_timeout(1200)

        # 4. Replace the document.
        res = page.evaluate(INJECT_JS, payload)
        if not res["handled"]:
            _fail(ctx, "CodeMirror did not accept the paste event")
        page.wait_for_timeout(1500)

        # 5. SAVE is disabled when nothing changed, which is the "already in
        #    sync" case rather than a failure.
        save = page.get_by_role("button", name="SAVE", exact=True).first
        if save.is_disabled():
            print("\nSAVE is greyed out -> the live page already matched this "
                  "payload byte for byte. Nothing to do.")
            _finish(ctx, keep_open)
            return 0

        if dry_run:
            print("\nDRY RUN: %d chars staged, SAVE is lit but NOT clicked." % res["chars"])
            _finish(ctx, keep_open or True)
            return 0

        save.click()
        page.wait_for_timeout(6000)
        print("\nSaved. %d chars published to '%s'." % (res["chars"], title))
        _finish(ctx, keep_open)
        return 0


def _launch(p, viewport):
    """Prefer the Google Chrome already installed on this Mac (no 150MB
    Playwright browser download, and the same engine the site is tested in).
    PROFILE is a dedicated directory, so this never fights your running
    Chrome for its profile lock."""
    kw = dict(user_data_dir=PROFILE, headless=False, viewport=viewport,
              args=["--disable-blink-features=AutomationControlled"])
    try:
        return p.chromium.launch_persistent_context(channel="chrome", **kw)
    except Exception:
        return p.chromium.launch_persistent_context(**kw)


def _needs_login(page):
    u = page.url
    return "login" in u or "account" in u


def _fail(ctx, msg):
    shot = os.path.join(ROOT, ".sqs-profile", "failure.png")
    try:
        ctx.pages[0].screenshot(path=shot)
        msg += "\n(screenshot: %s)" % shot
    except Exception:
        pass
    ctx.close()
    sys.exit("FAILED: " + msg)


def _finish(ctx, keep_open):
    if keep_open:
        print("Browser left open. Press Enter here to close it.")
        try:
            input()
        except EOFError:
            pass
    ctx.close()


def login():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        ctx = _launch(p, {"width": 1400, "height": 900})
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(PAGES_URL)
        print("Sign in to Squarespace in the browser window that just opened.")
        print("When you can see the Pages panel, come back here and press Enter.")
        try:
            input()
        except EOFError:
            pass
        ctx.close()
    print("Session saved to %s — you should not need to do this again." % PROFILE)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("target", nargs="?", help="page target, e.g. our-team")
    ap.add_argument("--login", action="store_true", help="one-time sign-in")
    ap.add_argument("--dry-run", action="store_true",
                    help="paste but do not click SAVE")
    ap.add_argument("--keep-open", action="store_true")
    ap.add_argument("--block-index", type=int, default=None)
    a = ap.parse_args()
    if a.login:
        return login()
    if not a.target:
        ap.error("give a target (e.g. our-team) or --login")
    return run(a.target, a.dry_run, a.keep_open, a.block_index)


if __name__ == "__main__":
    sys.exit(main() or 0)
