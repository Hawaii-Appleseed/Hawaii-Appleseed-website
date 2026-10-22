# Squarespace hybrid loader (parked, tested 2026-10-22)

**Status: parked.** Proven on one page, not rolled out. Nothing in `squarespace.py`
or the live site uses it. Pick it up when someone other than Devin needs to edit
issue pages without a Claude subscription.

## The idea
Squarespace 7.1 has no API to write a Code Block, so every publish is a manual
paste (`squarespace.py <target> --go`, or by hand in the editor). With this
approach you paste **once per page**; after that an edit goes live when the
payload on GitHub Pages changes (i.e. when it reaches `main`), with no paste.

## What gets pasted (`build_hybrid.py`)
`<div id="ha-live-root" data-src=PAGES_URL data-sha256=HASH>` + the **full current
payload as a snapshot** + a ~25-line script. On load the script fetches
`PAGES_URL`, hashes it, and if it differs from the snapshot swaps the new nodes in
(scripts re-created so they run); if equal it does nothing (no flash). Any error
keeps the snapshot.

Why a snapshot: the first version (`loader-only.example.html`, a bare loader) left
only ~1,000 chars of text in the raw HTML versus ~11,900 for the inline page, so
crawlers, link previews and no-JS readers saw almost nothing. The snapshot fixes that.

## Test results (unlinked duplicate page `/food-equity1`, never the live nav pages)
- Loader-only: content/fonts/tabs worked, fetch 122 ms; **SEO gap** confirmed.
- Hybrid: no-JS text 11,857 chars (= inline page), vision + priorities text present;
  with Pages ahead of the snapshot the page refreshed (`data-refreshed="1"`),
  3 quotes appeared where the snapshot had 0; Overview/Priorities tabs worked after
  the swap; browser SHA-256 of the Pages file equals `shasum -a 256` of it.
- **Not seen running:** the "hashes equal, do nothing" branch (Pages was behind).

## Limits / open questions
- Crawlers see the **snapshot**, so re-paste occasionally (monthly or after big text edits).
- After a swap, old-copy scripts may still be listening alongside new ones. Harmless
  in the test; worth watching, or have the swap reload the section instead.
- Pages deploys from `main`: edits are invisible until merged. That merge is the
  natural approval gate (Cider Publisher GitHub App route).
- Squarespace has a **second** Food Equity page at `/food-equity1` (unlinked
  duplicate); the real one is `/food-equity`. Pick sidebar rows by preview path.
- Still unknown: whether Cider can open these root-level issue pages as editable
  projects (they are plain HTML in this repo, not Cider projects).

## To resume
1. Decide the edit surface (Cider vs. editing HTML) and the approval step.
2. `python3 scripts/hybrid-loader/build_hybrid.py <payload> <pages-url> <out>`,
   paste once into the page's Code Block (real Cmd+V, then SAVE; see the
   squarespace pipeline notes), and check `/food-equity1` first.
3. Add it to `squarespace.py` as an option (`--hybrid`) so `--go` can emit it.
