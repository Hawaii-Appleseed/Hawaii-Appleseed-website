#!/usr/bin/env python3
"""Build the printable PDFs linked from the /resources page.

Reads the three guides out of tax-fairness/resources_guides_squarespace.html (the single
source of truth for their wording), wraps each in a print template, and prints it to PDF with
headless Chrome. Output: tax-fairness/assets/guides/*.pdf (served by GitHub Pages, linked from
the Resources cards). Re-run after editing the guides, then commit the PDFs.

    python3 tax-fairness/scripts/build_resource_pdfs.py
"""
import base64
import html
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "resources_guides_squarespace.html"
OUT = ROOT / "assets" / "guides"
LOGO = ROOT / "assets" / "brand" / "HawaiiTaxFairness_Horizontal_white-text.png"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

GUIDES = [
    ("messaging-guide", "Messaging Guide", "A Fair Tax System to Fund Hawaiʻi’s Future",
     "Hawaii-Tax-Fairness-2027-Messaging-Guide.pdf"),
    ("talking-points", "2027 Campaign Talking Points", "Working families tax credits, women, and children",
     "Hawaii-Tax-Fairness-2027-Talking-Points.pdf"),
    ("get-involved", "How to Get Involved", "Who we are, our core priorities, and ways to join the coalition",
     "Hawaii-Tax-Fairness-How-to-Get-Involved.pdf"),
]

CSS = """
@page { size: Letter; margin: 0.7in 0.75in 0.8in; }
@page :first { margin-top: 0; }
* { box-sizing: border-box; }
body { font-family: "Helvetica Neue", Helvetica, Arial, sans-serif; font-size: 11.5pt; line-height: 1.5; color: #253551; margin: 0; }
.band { background: #253551; margin: 0 -0.75in 0.35in; padding: 0.3in 0.75in; display: flex; align-items: center; justify-content: space-between; }
.band img { height: 0.55in; }
.band span { color: #fff; font-size: 10pt; letter-spacing: .05em; text-transform: uppercase; }
h1 { font-size: 26pt; line-height: 1.15; margin: 0 0 4pt; font-weight: 400; }
.sub { font-size: 13pt; color: #4a5568; margin: 0 0 18pt; }
h3 { font-size: 16pt; line-height: 1.25; margin: 20pt 0 6pt; font-weight: 400; color: #253551; break-after: avoid; }
h4 { font-size: 12.5pt; margin: 14pt 0 4pt; font-weight: 700; break-after: avoid; }
p { margin: 0 0 9pt; }
ul { margin: 0 0 10pt; padding-left: 18pt; }
li { margin: 0 0 5pt; }
a { color: #3c73b9; text-decoration: underline; }
.tfc-res-lede { font-size: 12.5pt; color: #4a5568; }
.tfc-res-tags { font-weight: 700; color: #3c73b9; }
.tfc-res-note { font-size: 8.5pt; color: #4a5568; }
table { width: 100%; border-collapse: collapse; margin: 0 0 14pt; font-size: 10pt; line-height: 1.4; }
th, td { text-align: left; vertical-align: top; padding: 6pt 8pt; border: 0.75pt solid #cfd5df; }
th { background: #253551; color: #fff; }
td:first-child { background: #f5f7fa; font-weight: 600; width: 28%; }
td p { margin: 0 0 5pt; }
tr { break-inside: avoid; }
.foot { margin-top: 22pt; padding-top: 8pt; border-top: 0.75pt solid #cfd5df; font-size: 9.5pt; color: #4a5568; }
"""


def body_of(src: str, gid: str) -> str:
    m = re.search(r'<details class="tfc-res-guide" id="%s">.*?<div class="tfc-res-body">(.*?)</div>\s*</details>' % gid, src, re.S)
    if not m:
        sys.exit(f"guide {gid} not found in {SRC.name}")
    # the on-page "Prefer a printable copy?" line has no place inside the PDF itself
    return re.sub(r'<p class="tfc-res-pdfnote">.*?</p>', '', m.group(1), flags=re.S).strip()


def main():
    src = SRC.read_text()
    OUT.mkdir(parents=True, exist_ok=True)
    logo = "data:image/png;base64," + base64.b64encode(LOGO.read_bytes()).decode()
    for gid, title, sub, fname in GUIDES:
        doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{html.escape(title)} — Hawaiʻi Tax Fairness Coalition</title>
<style>{CSS}</style></head><body>
<div class="band"><img src="{logo}" alt="Hawaiʻi Tax Fairness"><span>hitaxfairness.org</span></div>
<h1>{html.escape(title)}</h1><p class="sub">{html.escape(sub)}</p>
{body_of(src, gid)}
<p class="foot">Hawaiʻi Tax Fairness Coalition · hitaxfairness.org · info@hitaxfairness.org</p>
</body></html>"""
        with tempfile.TemporaryDirectory() as td:
            page = pathlib.Path(td) / "guide.html"
            page.write_text(doc)
            subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                            f"--print-to-pdf={OUT / fname}", page.as_uri()],
                           check=True, capture_output=True, timeout=120)
        print("wrote", OUT / fname, (OUT / fname).stat().st_size, "bytes")


if __name__ == "__main__":
    main()
