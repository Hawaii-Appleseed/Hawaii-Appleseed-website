#!/usr/bin/env python3
"""
Build paste-ready Squarespace Code Block files, one per page, into
squarespace-ready/.

Two kinds of pages:

1. Marker pages — the standalone HTML already contains a
   `BEGIN ha-xxx` … `END ha-xxx` block authored for injection. We just
   slice that block out (dropping the preview-only <html>/<head>/nav
   chrome) and write it to its own file.

2. Homepage (index.html) — never had injection markers. It was built as
   a full standalone page with global CSS resets and a fixed-nav chrome.
   We assemble a scoped injection: fonts + the head <style> (with the 6
   global rules scoped to #ha-home-embed so they can't leak into the
   Squarespace template) + the content sections (hero…get-involved,
   dropping announce/nav/footer) + the behaviour scripts (the two chrome
   scripts are null-guarded, so they no-op harmlessly).

Run:  python3 scripts/build_squarespace.py
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "squarespace-ready")

# Relative asset paths (assets/…) resolve against the Squarespace page URL
# once pasted, so images 404. Rewrite them to absolute URLs on the GitHub
# Pages host, which serves the same asset tree. NOTE: this hotlinks assets
# from GitHub Pages — a stopgap; for production, upload the images to
# Squarespace and swap these URLs so the site doesn't depend on Pages.
ASSET_BASE = "https://dtomkatsu.github.io/Hawaii-Appleseed-website/"


# The issue pages carry fixed-position scroll enhancements — a scroll
# progress bar and a sticky pill/tab nav pinned at top:107px (below the
# GitHub site's fixed nav). position:fixed can't anchor to the viewport
# inside a code block (transformed section wrappers capture it, and there
# is no fixed site nav at 107px). Rebuild the nav as position:sticky
# (code-block-safe) anchored at top:0, collapsing to 0 height until its
# reveal-on-scroll class fires so it leaves no gap in the flow. The thin
# scroll-progress line has no sticky equivalent, so it stays hidden. Class
# names exist only on the issue pages, so this is a no-op elsewhere.
# How the sticky rebuild works (verified in-browser):
#   1. The page roots use overflow-x:hidden, which forces overflow-y:auto —
#      a scroll container that traps position:sticky (it anchors to the root
#      instead of the viewport and never engages). overflow:clip clips the
#      same way WITHOUT creating a scroll container.
#   2. The bar becomes position:sticky top:0 (its markup is already the
#      first child of the page-root section, so it can stick for the whole
#      page).
#   3. A tiny script gives the bar a negative bottom margin equal to its
#      height, so it occupies ZERO net flow space — while hidden (opacity 0,
#      the original reveal state) it overlays the hero top with no gap, and
#      the page's existing IntersectionObserver reveal keeps working as
#      designed. ResizeObserver keeps the margin in sync when pills wrap.
# The thin scroll-progress line has no sticky equivalent and stays hidden.
STICKY_BAR_OVERRIDE = (
    "\n<style>\n"
    "/* Squarespace-fit: fixed-position bars can't anchor to the viewport\n"
    "   inside a code block. Hide the progress line; rebuild the pill/tab\n"
    "   nav as a sticky overlay (see build_squarespace.py). */\n"
    ".ha-progress { display: none !important; }\n"
    ".ha-issues, .ha-tax, .ha-food, .ha-housing, .ha-transit, .ha-wages "
    "{ overflow: clip !important; }\n"
    "/* absolute at FIRST PAINT so the (invisible) bar contributes zero\n"
    "   flow height from the very first frame — the script below converts\n"
    "   it to sticky + negative margin, which also nets to zero flow, so\n"
    "   the conversion causes no layout shift. (When this was sticky from\n"
    "   the start, the bar's 49-92px flow height was in the first paint\n"
    "   and everything below it visibly snapped UP once the script's\n"
    "   negative margin landed.) */\n"
    ".ha-nav-bar, [class*=\"__stuck-bar\"] {\n"
    "  position: absolute !important; top: 0 !important;\n"
    "  left: 0 !important; right: 0 !important;\n"
    "}\n"
    "</style>\n"
    "<script>\n"
    "(function(){\n"
    "  // Convert absolute -> sticky overlay. Both states occupy zero net\n"
    "  // flow space (absolute: out of flow; sticky: height cancelled by\n"
    "  // the negative margin), and the switch happens inside one\n"
    "  // synchronous pass — no paint can interleave — so there is no\n"
    "  // layout shift at any point. ResizeObserver resyncs the margin\n"
    "  // when the pills wrap at narrow widths.\n"
    "  document.querySelectorAll('.ha-nav-bar, [class*=\"__stuck-bar\"]')"
    ".forEach(function(bar){\n"
    "    var sync = function(){ bar.style.setProperty("
    "'margin-bottom', -bar.offsetHeight + 'px', 'important'); };\n"
    "    bar.style.setProperty('position', 'sticky', 'important');\n"
    "    bar.style.setProperty('top', '0', 'important');\n"
    "    bar.style.setProperty('left', 'auto', 'important');\n"
    "    bar.style.setProperty('right', 'auto', 'important');\n"
    "    sync();\n"
    "    if (window.ResizeObserver) "
    "new ResizeObserver(sync).observe(bar);\n"
    "    window.addEventListener('resize', sync);\n"
    "  });\n"
    "})();\n"
    "</script>\n"
)


# Squarespace pads the code block's content column on mobile (<=1080px),
# leaving side gutters even though every page's own layout is already
# edge-to-edge — same root cause as the homepage and support page (see
# build_homepage()/build_support()). Pull each marker page's top-level
# wrapper out to the full viewport width on mobile only; desktop already
# spans full width, and 100vw there can add a scrollbar. One shared block
# lists every marker page's root wrapper class (confirmed each one already
# has box-sizing:border-box with no padding of its own — padding lives on
# inner .ha-wrap/section containers, so this can't cause overflow). A class
# absent from a given page is simply a no-op there, same as STICKY_BAR_OVERRIDE.
FULL_BLEED_OVERRIDE = (
    "\n<style>\n"
    "/* Squarespace-fit: counter the code block's mobile content-column\n"
    "   padding by breaking the page wrapper out to 100vw. Mobile-only —\n"
    "   desktop already spans full width. */\n"
    "@media (max-width:1080px){\n"
    "  .ha-mission, .ha-story, .ha-issues, .ha-team, .ha-board,\n"
    "  .ha-tax, .ha-food, .ha-housing, .ha-transit, .ha-wages,\n"
    "  .ha-pub, .ha-news {\n"
    "    width: 100vw !important;\n"
    "    max-width: 100vw !important;\n"
    "    margin-left: calc(50% - 50vw) !important;\n"
    "    margin-right: calc(50% - 50vw) !important;\n"
    "  }\n"
    "}\n"
    "</style>\n"
)


# Internal cross-page links (href="food-security.html", "issues.html", …)
# point at our source filenames, which don't exist as Squarespace pages —
# the live site uses its own slugs. Confirmed against the real site
# (hiappleseed.org) and from the user directly. Query strings and #anchors
# on the original href are preserved (e.g. "support.html#give" ->
# "/support#give", "publications.html?cat=X" -> "/publications?cat=X").
INTERNAL_LINK_MAP = {
    "index.html":               "/",
    "issues.html":               "/issues",
    "our-mission.html":          "/our-mission",
    "our-mission-light.html":    "/our-mission",
    "our-story.html":            "/our-history",
    "our-story-light.html":      "/our-history",
    "our-team.html":             "/our-team",
    "board-of-directors.html":   "/board-of-directors",
    "publications.html":         "/publications",
    "in-the-news.html":          "/in-the-news",
    "support.html":              "/support",
    "taxes-budget.html":         "/taxes-budget",
    "food-security.html":        "/food-equity",
    "housing.html":              "/affordable-housing",
    "transportation.html":       "/transportation-equity",
    "wages-labor.html":          "/wages-labor",
}


def remap_internal_links(html):
    """href="food-security.html?cat=X#foo" -> href="/food-equity?cat=X#foo" """
    names = "|".join(re.escape(k) for k in INTERNAL_LINK_MAP)
    pattern = r'href="(' + names + r')((?:[?#][^"]*)?)"'
    return re.sub(
        pattern,
        lambda m: 'href="' + INTERNAL_LINK_MAP[m.group(1)] + m.group(2) + '"',
        html,
    )


# Sub-sites that live in THIS repo and are served by GitHub Pages, linked from
# the issue pages with bare relative hrefs (href="ufsm/"). A relative href
# resolves against the Squarespace page slug once pasted — "/food-equity" +
# "ufsm/" -> "/food-equity/ufsm/" -> 404, which is exactly why the UFSM
# dashboard link was dead. Same latent bug hit the "Explore the Tax Fairness
# Coalition" link, the "Read the SB 3125 FAQ" link
# (tax-fairness/faq_squarespace.html) and the RxKids link (rxkids/).
# Absolutize the whole path to the Pages host, like assets/.
PAGES_SUBSITES = ("ufsm", "tax-fairness", "rxkids")


def absolutize_assets(html):
    """Rewrite relative resource paths to absolute Pages URLs:
      • src/url()/href to assets/…  (images, etc.)
      • the data files scripts fetch() at the site root — publications.json,
        news.json — which otherwise 404 against the Squarespace domain and
        collapse the section to its fallback text. GitHub Pages serves these
        with Access-Control-Allow-Origin:* so the cross-origin fetch works.
      • href="<subsite>/" links to repo-hosted sub-sites (see PAGES_SUBSITES),
        which would otherwise resolve against the Squarespace page slug.
    Internal .html page links are handled separately by
    remap_internal_links(), below, since they map to real Squarespace
    page slugs rather than the Pages preview."""
    html = re.sub(r"""(["'(])(?:\./)?(assets/)""",
                  lambda m: m.group(1) + ASSET_BASE + m.group(2), html)
    html = re.sub(r"""(["'])((?:publications|news)\.json)(["'])""",
                  lambda m: m.group(1) + ASSET_BASE + m.group(2) + m.group(3),
                  html)
    subsites = "|".join(re.escape(s) for s in PAGES_SUBSITES)
    # Match the whole relative path, not just the bare dir, so deeper links
    # like tax-fairness/faq_squarespace.html are absolutized too. Already-
    # absolute hrefs start with a scheme and can't match.
    html = re.sub(r'href="(?:\./)?((?:' + subsites + r')/[^"]*)"',
                  lambda m: 'href="' + ASSET_BASE + m.group(1) + '"', html)
    return html

# (source file, marker slug, Squarespace page name, note)
MARKER_PAGES = [
    ("our-mission.html",        "ha-mission",      "Our Mission",     ""),
    ("our-mission-light.html",  "ha-mission",      "Our Mission",     "light-background variant — use this OR our-mission, not both"),
    ("our-story.html",          "ha-story",        "Our Story",       ""),
    ("our-story-light.html",    "ha-story",        "Our Story",       "light-background variant — use this OR our-story, not both"),
    ("issues.html",             "ha-issues",       "Issues",          ""),
    ("our-team.html",           "ha-team",         "Our Team",        ""),
    ("board-of-directors.html", "ha-board",        "Board",           ""),
    ("taxes-budget.html",       "ha-tax",          "Taxes & Budget",  ""),
    ("food-security.html",      "ha-food",         "Food Security",   ""),
    ("housing.html",            "ha-housing",      "Housing",         ""),
    ("transportation.html",     "ha-transit",      "Transportation",  ""),
    ("wages-labor.html",        "ha-wages",        "Wages & Labor",   ""),
    ("publications.html",       "ha-publications", "Publications",    ""),
    ("in-the-news.html",        "ha-news",         "In the News",     ""),
]


def read(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as f:
        return f.read().split("\n")


def entity_encode(html):
    """Escape every non-ASCII character so the output survives pasting into
    a Squarespace Code Block regardless of how Squarespace (mis)handles the
    byte encoding — a raw paste showed 'Hawai ᵃi' / 'ISSUES,üi'.

    Encoding is context-aware, because the right escape differs by where the
    character sits:
      • markup/text  -> HTML numeric entity   (&#699;)
      • <script> JS  -> JS unicode escape      (\\u02bb)  — valid in string
                        literals, harmless in comments; entities would NOT
                        be decoded here.
      • <style> CSS  -> CSS hex escape         (\\2bb ) — valid in values,
                        harmless in comments.
    The surrounding <script>/<style> tags are ASCII, so only the inner
    non-ASCII characters are touched."""
    parts = re.split(r"(<script[\s\S]*?</script>|<style[\s\S]*?</style>)", html,
                     flags=re.I)
    out = []
    for i, part in enumerate(parts):
        if i % 2 == 0:                                   # markup / text
            out.append("".join(
                c if ord(c) < 128 else "&#%d;" % ord(c) for c in part))
        elif part[:7].lower() == "<script":             # JS
            out.append("".join(
                c if ord(c) < 128 else "\\u%04x" % ord(c) for c in part))
        else:                                            # CSS
            out.append("".join(
                c if ord(c) < 128 else "\\%x " % ord(c) for c in part))
    return "".join(out)


def header(page, note):
    n = ("\n     NOTE: " + note) if note else ""
    return (
        "<!-- =====================================================================\n"
        "     PASTE-READY Squarespace injection for the \"%s\" page.\n"
        "     Generated by scripts/build_squarespace.py — do not hand-edit;\n"
        "     edit the source page and re-run the script.\n"
        "     HOW: %s page > Edit > add a Code Block > paste ALL of this >\n"
        "          make sure \"Display Source\" is OFF > Save.%s\n"
        "     ===================================================================== -->\n"
        % (page, page, n)
    )


def extract_marker(lines, slug):
    """Return the lines between the BEGIN and END markers for a slug,
    working for all three marker comment styles.

    The instruction comment itself mentions "BEGIN <slug>" and "END
    <slug>" in prose, so we take the LAST occurrence of each — that is
    always the real marker, never the prose mention."""
    begins = [i for i, l in enumerate(lines) if ("BEGIN " + slug) in l]
    ends = [i for i, l in enumerate(lines) if ("END " + slug) in l]
    begin = begins[-1]
    # the BEGIN token may sit inside a multi-line instruction comment;
    # content starts after that comment closes.
    j = begin
    while "-->" not in lines[j]:
        j += 1
    start = j + 1
    end = ends[-1]
    return lines[start:end]


def _find(lines, needle, start=0):
    return next(i for i in range(start, len(lines)) if needle in lines[i])


def scope_css_selectors(css, wrapper_id):
    """Prefix every top-level CSS selector with '#wrapper_id ' so a page
    built with unscoped generic classes (.hero, .btn, .form, .section-title,
    …) can't collide with the Squarespace template or other injected pages
    reusing those same common names.

    A brace-depth-aware scan (not a full CSS parser, but enough for this
    codebase's hand-written, non-pathological CSS) so nested content is
    handled correctly:
      • Text immediately before a '{' is a selector (or an at-rule like
        '@media (...)') — prefix it, UNLESS:
          - it's an at-rule ('@media', '@keyframes', '@supports', …) —
            passed through untouched, and if it's '@keyframes' every
            selector inside its body (0%, 50%, from, to) is also left
            alone until that body's closing brace.
          - it's exactly ':root' — left alone, so custom properties stay
            on the true document root and inherit normally into scoped
            descendants.
          - it already starts with the wrapper id (idempotent — rules
            already scoped by an earlier literal replace aren't doubled).
      • Multiple comma-separated selectors are each prefixed individually.
      • /* comment */ spans are passed through untouched and do NOT enter
        the selector buffer — a comment sitting directly before a rule
        (no brace in between, e.g. a "/* ANIMATIONS */" banner before
        "@keyframes fadeUp") would otherwise get glued onto that rule's
        selector text, so "@keyframes fadeUp".strip().startswith("@")
        silently fails (the combined string starts with the comment's
        "/*" instead) and the whole keyframes body gets misprefixed.
    """
    out = []
    buf = []
    depth = 0
    keyframes_depth = None  # depth level whose body is a @keyframes block

    def flush_as_selector():
        text = "".join(buf)
        stripped = text.strip()
        if not stripped:
            return text
        if stripped.startswith("@"):
            return text
        if keyframes_depth is not None and depth >= keyframes_depth:
            return text
        if stripped == ":root":
            return text
        parts = [p.strip() for p in text.split(",")]
        scoped = []
        for p in parts:
            if not p:
                continue
            if p.startswith("#" + wrapper_id):
                scoped.append(p)
            else:
                scoped.append("#" + wrapper_id + " " + p)
        # Preserve original leading whitespace/newlines for readability.
        leading_ws = text[:len(text) - len(text.lstrip())]
        return leading_ws + ", ".join(scoped)

    i = 0
    n = len(css)
    while i < n:
        ch = css[i]
        if ch == "/" and i + 1 < n and css[i + 1] == "*":
            end = css.find("*/", i + 2)
            end = (end + 2) if end != -1 else n
            # Flush whatever selector text had accumulated before the
            # comment as plain output (no brace follows it here, so it
            # isn't a rule to prefix — just carried text, e.g. blank
            # lines between rules), then emit the comment untouched.
            out.append("".join(buf))
            buf = []
            out.append(css[i:end])
            i = end
            continue
        if ch == "{":
            selector_text = flush_as_selector()
            was_at_rule = selector_text.strip().startswith("@")
            out.append(selector_text)
            out.append("{")
            depth += 1
            if was_at_rule and selector_text.strip().startswith("@keyframes"):
                keyframes_depth = depth
            buf = []
        elif ch == "}":
            out.append("".join(buf))
            out.append("}")
            if keyframes_depth is not None and depth == keyframes_depth:
                keyframes_depth = None
            depth = max(0, depth - 1)
            buf = []
        else:
            buf.append(ch)
        i += 1
    out.append("".join(buf))
    return "".join(out)


def build_support(lines):
    """support.html (Donate/Support page) predates the .ha-xxx namespacing
    convention: it's written like a standalone mockup with plain global
    classes (.hero, .btn, .mission-band, .form, …) and the same 6 kinds of
    global resets the homepage had. Assemble a scoped injection the same
    way as build_homepage(), but since almost EVERY selector here is
    unscoped (not just 6 known rules), use scope_css_selectors() to prefix
    all of them under #ha-support-embed rather than hand-listing each one.
    """
    body_i = _find(lines, "<body")

    f_pre = _find(lines, 'rel="preconnect" href="https://fonts.gstatic.com"')
    f_css = _find(lines, "fonts.googleapis.com/css2")
    fonts = "\n".join([lines[f_pre], lines[f_css]])

    css_start = _find(lines, "<style>")
    css_end = max(i for i in range(body_i) if "</style>" in lines[i])
    # Exclude the <style>/</style> tag lines themselves from what gets fed to
    # scope_css_selectors() below — its brace-depth scanner treats all text
    # before a rule's "{" as that rule's selector, so a leading "<style>"
    # line gets glued onto the first real selector (":root" no longer
    # matches its exact-string special-case) and prefixed right along with
    # it, leaving the literal characters "#ha-support-embed <style>" as
    # stray visible text in front of a still-otherwise-working style block.
    # Re-added after scoping, below.
    css = "\n".join(lines[css_start + 1:css_end])

    hero_i = _find(lines, '<section class="hero">')
    footer_i = _find(lines, 'class="px-footer"', hero_i)
    markup_lines = lines[hero_i:footer_i]
    while markup_lines and (not markup_lines[-1].strip()
                            or markup_lines[-1].strip().startswith("<!--")):
        markup_lines.pop()
    markup = "\n".join(markup_lines)

    footer_close = _find(lines, "</footer>", footer_i)
    scripts_start = _find(lines, "<script", footer_close)
    body_close = _find(lines, "</body>")
    scripts = "\n".join(lines[scripts_start:body_close])

    # Scope the CSS: the two universal (*) resets get :where() (zero
    # specificity — matches the homepage fix), the few single-element
    # global rules just get element-swapped to the wrapper id, and EVERY
    # remaining selector (.hero, .btn, .mission-band, …) is prefixed by
    # the brace-depth scanner above.
    css = css.replace(
        "*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }",
        ":where(#ha-support-embed, #ha-support-embed *, #ha-support-embed *::before, #ha-support-embed *::after) { box-sizing: border-box; margin: 0; padding: 0; }",
    )
    css = css.replace(
        "*, *::before, *::after{",
        ":where(#ha-support-embed *, #ha-support-embed *::before, #ha-support-embed *::after){",
    )
    css = css.replace("html { scroll-behavior: smooth; }", "")
    css = re.sub(r"(?m)^(\s*)body\s*\{", r"\1#ha-support-embed {", css, count=1)
    css = css.replace(
        "section[id] { scroll-margin-top: 124px; }",
        "#ha-support-embed section[id] { scroll-margin-top: 124px; }",
    )
    css = css.replace(
        "a, button { -webkit-tap-highlight-color: transparent; }",
        "#ha-support-embed a, #ha-support-embed button { -webkit-tap-highlight-color: transparent; }",
    )
    css = "<style>\n" + scope_css_selectors(css, "ha-support-embed") + "\n</style>"

    # Full-bleed breakout on mobile (same fix as the homepage): Squarespace
    # pads the code block's content column on mobile, leaving side gutters.
    # The source page is already edge-to-edge, so pull the wrapper out to the
    # full viewport width to counter that padding. Mobile-only: desktop spans
    # full width already, and 100vw there can add a scrollbar.
    css += (
        "\n<style>\n"
        "@media (max-width:1080px){\n"
        "  #ha-support-embed{\n"
        "    width: 100vw !important;\n"
        "    max-width: 100vw !important;\n"
        "    margin-left: calc(50% - 50vw) !important;\n"
        "    margin-right: calc(50% - 50vw) !important;\n"
        "  }\n"
        "}\n"
        "</style>\n"
    )

    note = ("this page predates the .ha-xxx namespacing convention (plain "
            "global classes like .hero/.btn/.form) — every CSS selector is "
            "auto-scoped under #ha-support-embed by the builder so it can't "
            "collide with the Squarespace template or other pages")
    return (
        header("Support / Donate", note)
        + "<!-- BEGIN ha-support -->\n"
        + '<div id="ha-support-embed">\n'
        + fonts + "\n"
        + css + "\n"
        + markup + "\n"
        + scripts + "\n"
        + "</div>\n"
        + "<!-- END ha-support -->\n"
    )


def build_ufsm(lines):
    """ufsm/index.html is a standalone page under ufsm/ — not marker-based,
    and normally served on its own via GitHub Pages (see PAGES_SUBSITES).
    It predates the .ha-xxx namespacing convention (global :root/*/body/
    h1-h4 selectors), so scope it under #ha-ufsm-embed with
    scope_css_selectors(), the same recipe as build_homepage()/build_support().

    Two UFSM-specific fixes on top of the standard scoping:

    1. .ufsm-pdf-fab is position:fixed, which can't anchor to the viewport
       inside a Squarespace Code Block (same root cause as
       STICKY_BAR_OVERRIDE above). Override it to position:sticky as a
       DIRECT child of #ha-ufsm-embed (so its sticky containing block spans
       the whole embedded page, keeping it pinned through the full scroll),
       right-aligned via margin-left:auto instead of right:18px. This
       reserves ~50px of one-time flow height at the very top of the
       content instead of floating from pixel zero — a minor visual
       tradeoff for something that actually works in a code block.

    2. ufsm/index.html's PDF-export script toggles the .ufsm-pdf-capture
       class directly ON its capture root (#ha-ufsm-embed when present,
       document.body in the standalone deploy — see its `captureRoot`
       variable), not on some deeper element. scope_css_selectors() would
       otherwise turn `.ufsm-pdf-capture X` into the DESCENDANT selector
       `#ha-ufsm-embed .ufsm-pdf-capture X`, which can never match (the
       class lands ON #ha-ufsm-embed itself, not a descendant of it). Pre-
       rewrite those rules to the compound form
       `#ha-ufsm-embed.ufsm-pdf-capture X` before scoping runs;
       scope_css_selectors() treats anything already starting with the
       wrapper id as pre-scoped and leaves it alone.
    """
    body_i = _find(lines, "<body")

    f_start = _find(lines, 'rel="preconnect" href="https://fonts.googleapis.com"')
    f_end = _find(lines, "jspdf@")
    fonts = "\n".join(lines[f_start:f_end + 1])

    css_start = _find(lines, "<style>")
    css_end = max(i for i in range(body_i) if "</style>" in lines[i])
    # Exclude the <style>/</style> tag lines themselves — see the matching
    # comment in build_support() for why (scope_css_selectors()'s brace
    # scanner would otherwise glue a leading "<style>" onto ":root" and
    # stop it from matching that exact-string special-case, leaving stray
    # "#ha-ufsm-embed <style>" text visible on the page). Re-added below.
    css = "\n".join(lines[css_start + 1:css_end])
    css = css.replace(".ufsm-pdf-capture ", "#ha-ufsm-embed.ufsm-pdf-capture ")

    button_i = _find(lines, 'id="ufsm-pdf-btn"')
    markup_start = max(i for i in range(body_i, button_i + 1) if "<button" in lines[i])
    scripts_start = _find(lines, "<script>", markup_start)
    markup_lines = lines[markup_start:scripts_start]
    while markup_lines and not markup_lines[-1].strip():
        markup_lines.pop()
    markup = "\n".join(markup_lines)

    body_close = _find(lines, "</body>")
    scripts = "\n".join(lines[scripts_start:body_close])

    css = css.replace(
        "*, *::before, *::after { box-sizing: border-box; }",
        "#ha-ufsm-embed, #ha-ufsm-embed *, #ha-ufsm-embed *::before, #ha-ufsm-embed *::after { box-sizing: border-box; }",
    )
    css = css.replace("* { box-sizing: border-box; }",
                       "#ha-ufsm-embed *, #ha-ufsm-embed *::before, #ha-ufsm-embed *::after { box-sizing: border-box; }")
    css = re.sub(r"(?m)^(\s*)body\s*\{", r"\1#ha-ufsm-embed {", css, count=1)
    css = css.replace("overflow-x: hidden;", "overflow: clip;")
    css = "<style>\n" + scope_css_selectors(css, "ha-ufsm-embed") + "\n</style>"

    css += (
        "\n<style>\n"
        "/* Squarespace-fit: position:fixed can't anchor to the viewport inside\n"
        "   a code block. Rebuild the Download-PDF pill as a sticky, direct\n"
        "   child of #ha-ufsm-embed (its containing block spans the whole\n"
        "   embedded page, so it stays pinned through the full scroll) instead\n"
        "   of fixed at a hard-coded viewport offset. */\n"
        "#ha-ufsm-embed .ufsm-pdf-fab{\n"
        "  position: sticky !important; top: 12px !important; right: auto !important;\n"
        "  display: block !important; width: fit-content !important;\n"
        "  margin: 12px 18px 0 auto !important;\n"
        "}\n"
        "@media (max-width:767px){\n"
        "  #ha-ufsm-embed .ufsm-pdf-fab{ margin: 10px 12px 0 auto !important; }\n"
        "}\n"
        "/* Print only the flyer, not the surrounding Squarespace page. These\n"
        "   rules target the HOST page's elements, so they must live in this\n"
        "   unscoped block — the scoped stylesheet can only reach inside the\n"
        "   embed. visibility (not display) keeps the embed's layout intact\n"
        "   while blanking the host chrome, and re-showing a child of a hidden\n"
        "   ancestor is exactly what visibility permits. Pulling the embed out\n"
        "   of flow (position:absolute) lifts it to the top of page 1 and\n"
        "   collapses the document height the hidden host content occupied,\n"
        "   so there are no leading/trailing blank pages. */\n"
        "@media print {\n"
        "  body * { visibility: hidden !important; }\n"
        "  #ha-ufsm-embed, #ha-ufsm-embed * { visibility: visible !important; }\n"
        "  #ha-ufsm-embed { position: absolute !important; top: 0 !important; left: 0 !important; width: 100% !important; margin: 0 !important; }\n"
        "  html, body { height: auto !important; overflow: visible !important; }\n"
        "}\n"
        "</style>\n"
    )

    note = ("standalone GitHub Pages subsite (ufsm/) — predates the .ha-xxx "
            "namespacing convention (global :root/*/body/h1-h4 selectors), "
            "auto-scoped under #ha-ufsm-embed by the builder; the floating "
            "Download-PDF button is rebuilt as a sticky element since "
            "position:fixed can't anchor to the viewport in a code block")
    return (
        header("Universal Free School Meals (UFSM)", note)
        + "<!-- BEGIN ha-ufsm -->\n"
        + '<div id="ha-ufsm-embed">\n'
        + fonts + "\n"
        + css + "\n"
        + markup + "\n"
        + scripts + "\n"
        + "</div>\n"
        + "<!-- END ha-ufsm -->\n"
    )


def build_homepage(lines):
    # Locate everything by content landmarks (not line numbers) so the
    # script survives edits to index.html.
    body_i = _find(lines, "<body")

    # Fonts: the preconnect + the googleapis css2 stylesheet link (head).
    f_pre = _find(lines, 'rel="preconnect" href="https://fonts.gstatic.com"')
    f_css = _find(lines, "fonts.googleapis.com/css2")
    fonts = "\n".join([lines[f_pre], lines[f_css]])

    # CSS: first <style> in the head through the last </style> before <body>.
    css_start = _find(lines, "<style>")
    css_end = max(i for i in range(body_i) if "</style>" in lines[i])
    css = "\n".join(lines[css_start:css_end + 1])

    # Markup: the real hero (big headline + 3D parallax) through the last
    # content section, footer chrome excluded. The clipping that once forced
    # a swap to the simpler video-hero card was the ID-specificity reset
    # zeroing the hero's padding — now fixed with :where() below — plus a
    # container-fit override appended to the CSS.
    hero_i = _find(lines, '<section class="ha-home__hero"')
    footer_i = _find(lines, 'class="px-footer"', hero_i)
    markup_lines = lines[hero_i:footer_i]
    while markup_lines and (not markup_lines[-1].strip()
                            or markup_lines[-1].strip().startswith("<!--")):
        markup_lines.pop()
    markup = "\n".join(markup_lines)

    # Scripts: everything between </footer> and </body> (behaviour scripts;
    # the two chrome scripts are null-guarded no-ops).
    footer_close = _find(lines, "</footer>", footer_i)
    scripts_start = _find(lines, "<script", footer_close)
    body_close = _find(lines, "</body>")
    scripts = "\n".join(lines[scripts_start:body_close])

    # Scope the 6 global rules so they cannot bleed into the Squarespace page.
    #
    # The two universal (*) resets MUST stay at zero specificity, so wrap them
    # in :where(): a plain `#ha-home-embed *{padding:0}` carries ID specificity
    # and would beat every class rule like `.ha-home__issues{padding:7rem 8%}`,
    # collapsing all section padding (content jams to the left edge). :where()
    # contributes 0 specificity, preserving the original global-reset cascade
    # where class padding wins.
    css = css.replace(
        "*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }",
        ":where(#ha-home-embed, #ha-home-embed *, #ha-home-embed *::before, #ha-home-embed *::after) { box-sizing: border-box; margin: 0; padding: 0; }",
    )
    css = css.replace(
        "*, *::before, *::after{",
        ":where(#ha-home-embed *, #ha-home-embed *::before, #ha-home-embed *::after){",
    )
    # These target specific elements (not `*`), so ID specificity is harmless.
    css = css.replace("html { scroll-behavior: smooth; }", "")
    css = re.sub(r"(?m)^(\s*)body\s*\{", r"\1#ha-home-embed {", css, count=1)
    css = css.replace(
        "section[id] { scroll-margin-top: 124px; }",
        "#ha-home-embed section[id] { scroll-margin-top: 124px; }",
    )
    css = css.replace(
        "a, button { -webkit-tap-highlight-color: transparent; }",
        "#ha-home-embed a, #ha-home-embed button { -webkit-tap-highlight-color: transparent; }",
    )

    # Squarespace-fit override (appended so it wins the cascade). The hero's
    # 92svh height + 7rem top padding assume a fixed nav overlapping its top
    # (as on GitHub Pages). A Squarespace section has no such overlap, so that
    # space reads as a big gap under the header — trim the height and top pad.
    # NOTE: css includes its own <style>…</style> tags, so the override must
    # live in its OWN <style> block or it lands outside any stylesheet.
    css += (
        "\n<style>\n"
        "/* --- Squarespace-fit hero (no fixed-nav overlap here) --- */\n"
        "/* Desktop split hero: 72svh (the source's 84svh assumes a fixed nav\n"
        "   overlapping the top). The film's height cap reserves only 150px so\n"
        "   that on wide+tall screens 54vw wins the min() and the film renders\n"
        "   full size; the cap binds ONLY on short viewports, shrinking the\n"
        "   film there so the mission band never laps it. Tuned live on\n"
        "   Squarespace (2026-07): 72svh + 3.5rem headline pad + film offset\n"
        "   +1rem reads tight with no dead slate band under the film. */\n"
        "@media (min-width:1081px){\n"
        "  #ha-home-embed .ha-home__hero, #ha-home-embed .hero-inner "
        "{ min-height: 72svh !important; }\n"
        "  /* Push the content down off the nav (headline pad + film offset) while\n"
        "     72svh keeps the band below tight. */\n"
        "  #ha-home-embed .hero-inner { padding-top: 3.5rem !important; }\n"
        "  #ha-home-embed .ha-home__hero-media {\n"
        "    top: calc(50% + 1rem) !important;\n"
        "    width: min(54vw, calc((72svh - 150px) * 16 / 9)) !important;\n"
        "    /* Same left-anchor trick as the source (full film -> 43vw, capped\n"
        "       film hugs the text at 46vw) but with the embed's height math. */\n"
        "    left: min(46vw, calc(97vw - min(54vw, (72svh - 150px) * 16 / 9))) !important;\n"
        "    right: auto !important;\n"
        "  }\n"
        "}\n"
        "/* Stacked layout keeps the source's min-height:auto; only trim its\n"
        "   9.5rem top pad (that too was to clear the GitHub fixed nav). */\n"
        "@media (max-width:1080px){\n"
        "  #ha-home-embed .hero-inner { padding-top: 2.5rem !important; }\n"
        "  /* Full-bleed breakout: Squarespace pads the code block's content\n"
        "     column on mobile, leaving side gutters. The source page is\n"
        "     already edge-to-edge, so pull the wrapper out to the full\n"
        "     viewport width to counter that padding. Mobile-only: desktop\n"
        "     already spans full width, and 100vw there can add a scrollbar. */\n"
        "  #ha-home-embed{\n"
        "    width: 100vw !important;\n"
        "    max-width: 100vw !important;\n"
        "    margin-left: calc(50% - 50vw) !important;\n"
        "    margin-right: calc(50% - 50vw) !important;\n"
        "  }\n"
        "}\n"
        "</style>\n"
    )

    note = ("the real homepage hero (big headline + parallax) with a "
            "Squarespace-fit height override; everything below is the live "
            "homepage. Video controls sit bottom-left with a seek scrubber.")
    return (
        header("Home", note)
        + "<!-- BEGIN ha-home -->\n"
        + '<div id="ha-home-embed">\n'
        + fonts + "\n"
        + css + "\n"
        + markup + "\n"
        + scripts + "\n"
        + "</div>\n"
        + "<!-- END ha-home -->\n"
    )


# The ʻokina (U+02BB) is missing from both Manrope and Poppins, so the pages
# carry one-glyph faces in assets/okina.css and lead every stack with the
# matching Okina* family. Each builder hand-picks the font <link> lines out of
# the <head>, so that stylesheet has to be re-attached here or the injected
# blocks name a family the browser never loads — and every ʻokina on the live
# site quietly falls back to Helvetica again. Hotlinked from Pages like the
# images above, and subject to the same stopgap caveat.
OKINA_CSS = ASSET_BASE + "assets/okina.css"


def ensure_okina(html):
    """Attach assets/okina.css after the Google Fonts link, once."""
    if "okina.css" in html:
        return html
    link = '<link rel="stylesheet" href="%s">' % OKINA_CSS
    out, n = re.subn(r'(<link[^>]*fonts\.googleapis\.com/css2[^>]*>)',
                     lambda m: m.group(1) + "\n" + link, html, count=1)
    if n:
        return out
    # Blocks whose marker starts below the <head> carry no font link of their
    # own (they inherit the Squarespace template's). They still name the
    # Okina* families in their CSS, so the stylesheet goes in ahead of it.
    return html.replace("<style>", link + "\n<style>", 1)


def main():
    os.makedirs(OUT, exist_ok=True)
    manifest = []

    for src, slug, page, note in MARKER_PAGES:
        block = extract_marker(read(src), slug)
        out_name = src  # keep the same stem so the mapping is obvious
        body = entity_encode(ensure_okina(remap_internal_links(absolutize_assets(
            header(page, note) + "\n".join(block).strip()
            + STICKY_BAR_OVERRIDE + FULL_BLEED_OVERRIDE))))
        with open(os.path.join(OUT, out_name), "w", encoding="utf-8") as f:
            f.write(body)
        manifest.append((out_name, page, len(body)))

    home = entity_encode(ensure_okina(remap_internal_links(
        absolutize_assets(build_homepage(read("index.html"))))))
    with open(os.path.join(OUT, "index.html"), "w", encoding="utf-8") as f:
        f.write(home)
    manifest.append(("index.html", "Home", len(home)))

    support = entity_encode(ensure_okina(remap_internal_links(
        absolutize_assets(build_support(read("support.html"))))))
    with open(os.path.join(OUT, "support.html"), "w", encoding="utf-8") as f:
        f.write(support)
    manifest.append(("support.html", "Support / Donate", len(support)))

    ufsm = entity_encode(ensure_okina(remap_internal_links(
        absolutize_assets(build_ufsm(read("ufsm/index.html"))))))
    with open(os.path.join(OUT, "ufsm.html"), "w", encoding="utf-8") as f:
        f.write(ufsm)
    manifest.append(("ufsm.html", "Universal Free School Meals (UFSM)", len(ufsm)))

    print("Wrote %d files to squarespace-ready/:" % len(manifest))
    for name, page, size in manifest:
        print("  %-26s -> %-16s (%d KB)" % (name, page, round(size / 1024)))


if __name__ == "__main__":
    main()
