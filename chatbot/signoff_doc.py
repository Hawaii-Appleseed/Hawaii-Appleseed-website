#!/usr/bin/env python3
"""The staff sign-off review for "Ask Hawaiʻi Appleseed", as a Google Doc: build it, file it, read the decisions back.

The assistant says things on the organization's behalf that no model checks: a stated position, a ready-made answer, a
fixed reply. This renders every one of them exactly as a visitor would see it, with the chart that goes with it, the
reports linked under it, and each figure beside the published sentence it was matched to (figures.py), then a box to tick.

Run it with the Drive pipeline's own Python (it has the Google libraries):

    P=~/internal-tools/appleseed-drive/.venv/bin/python
    $P chatbot/signoff_doc.py --html out.html          just render the HTML (no Google needed)
    $P chatbot/signoff_doc.py --file                   create the Doc in Communications & Media > Website
    $P chatbot/signoff_doc.py --read DOC_ID            list what reviewers decided
    $P chatbot/signoff_doc.py --read DOC_ID --apply    mark ticked "Approve as written" positions approved in positions.md
    $P chatbot/signoff_doc.py --update DOC_ID          re-render into an existing Doc (refuses if anyone has ticked a box)

Every item carries a "Ref:" line. The reader goes by those refs and by the unicode boxes, so staff can edit the text freely
around them; to tick a box, change ☐ to ☒. Applying writes `<!-- status: approved by NAME YYYY-MM-DD -->` and nothing else:
an approved position still needs `build_index.py --public` and a deploy before it goes live.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_index as b  # noqa: E402

DRIVE_DIR = Path(os.environ.get("APPLESEED_DRIVE", Path.home() / "internal-tools" / "appleseed-drive"))
WEBSITE_FOLDER = "1H7lGHOkqse73Qzl47wOSrZGnbdE54FqB"  # Communications & Media > Website
DOC_NAME = "Ask Hawaiʻi Appleseed: Sign-off Review (Draft)"
BOX, TICKED = "☐", ("☒", "☑", "✅", "✔")

# Brand: charcoal text, Deep Teal accents, Ash Light fills. Inline styles only: Drive's importer ignores most of <style>.
CHAR, TEAL, ASH_LIGHT, MUTED = "#2F3E46", "#52796F", "#E5E9E2", "#5B6A70"
BODY = f"font-family:Poppins,Arial,sans-serif;font-size:10pt;color:{CHAR};line-height:1.4"
HEAD = "font-family:Manrope,Arial,sans-serif;font-weight:800;color:" + CHAR


def e(s) -> str:
    return html.escape(str(s), quote=False)


def a(text, url) -> str:
    return f'<a href="{html.escape(url, quote=True)}" style="color:{TEAL}">{e(text)}</a>' if url else e(text)


def cited(text: str) -> str:
    """Answer text with [n] markers as superscripts, the way the page shows them."""
    return re.sub(r"\[(\d+)\]", r"<sup>[\1]</sup>", e(text))


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", re.sub(r"\(.*?\)", "", s.lower())).strip("-")


def small(s: str) -> str:
    return f'<p style="{BODY};font-size:8.5pt;color:{MUTED};margin:2pt 0">{s}</p>'


def p(s: str, extra: str = "") -> str:
    return f'<p style="{BODY};margin:3pt 0;{extra}">{s}</p>'


def table(rows: list[list[str]], widths: list[int], head: list[str] | None = None) -> str:
    out = [f'<table data-w="{",".join(map(str, widths))}" border="1" cellspacing="0" cellpadding="5" style="border-collapse:collapse;width:100%;border-color:#CAD2C5">']
    if head:
        out.append("<tr>" + "".join(f'<th width="{w}%" align="left" bgcolor="{ASH_LIGHT}" style="{BODY};font-weight:700;background:{ASH_LIGHT}">{h}</th>' for h, w in zip(head, widths)) + "</tr>")
    for r in rows:
        out.append("<tr>" + "".join(f'<td width="{w}%" valign="top" style="{BODY}">{c}</td>' for c, w in zip(r, widths)) + "</tr>")
    out.append("</table>")
    return "".join(out)


def node_json(expr: str):
    """Evaluate a JS expression over the Worker's own modules, so the doc quotes the exact strings the page and Worker use."""
    code = f"import('{(HERE / 'worker' / 'src' / 'legal.js').as_posix()}').then(async L => {{ const H = await import('{(HERE / 'worker' / 'src' / 'handler.js').as_posix()}'); console.log(JSON.stringify({expr})); }})"
    return json.loads(subprocess.run(["node", "-e", code], capture_output=True, text=True, check=True).stdout)


# ------------------------------------------------------------------- the three parts
def decision(ref: str, what: str = "this") -> str:
    left = "".join(p(f"{BOX} {t}") for t in (f"Approve {what} as written", "Approve with the edits in Notes", "Hold: not ready", "Remove it from the assistant")) + small(f"Ref: {ref}")
    right = p("<b>Reviewed by</b> (name and date): ") + p("<b>Notes</b> (edit the text above directly, or say what to change here): ")
    return table([[left, right]], [45, 55], head=["Decision (change ☐ to ☒)", "Who and why"])


def graphic_lines(g: dict) -> str:
    rows = g.get("rows") or g.get("items") or []
    if g["type"] == "bars":
        lines = [f'{r["label"]}: {r["display"]}' for r in rows]
    elif g["type"] == "stats":
        lines = [f'{r["value"]}: {r["label"]}' for r in rows]
    elif g["type"] == "timeline":
        lines = [f'{r["when"]}: {r["what"]}' for r in rows]
    else:
        lines = [f'{r["item"]} ({r["status"]}): {r["what"]}. {r["outcome"]}' for r in rows]
    tag = " (a made-up illustration, labeled as one)" if g.get("illustration") else ""
    out = p(f"<b>{e(g['title'])}</b>{tag}") + "<ul>" + "".join(f'<li style="{BODY}">{e(l)}</li>' for l in lines) + "</ul>"
    if g.get("note"):
        out += small(e(g["note"]))
    return out


def figure_rows(sec_report: dict, allow: dict, title: str) -> tuple[str, int]:
    rows, bills = [], []
    for r in sec_report["figures"]:
        if r["key"].startswith(("bill:", "act:")):
            bills.append(r["figure"])
            continue
        src = r.get("source")
        if r["status"] == "accepted":
            al = allow.get((title, r["key"]), {})
            pub = e(al.get("reason", "")) + (f"<br/>Source: {e(al.get('source', ''))}" if al.get("source") else "")
            check = f"Accepted after a first read by Claude.<br/>{BOX} Staff confirm"
        elif r["status"] == "sentence" and isinstance(src, dict):
            pub = f"“{e(src['sentence'][:300])}”<br/>" + a(src["title"], src.get("url"))
            check = "Backed by a published sentence"
        else:
            pub = (a(src["title"], src.get("url")) if isinstance(src, dict) else "") or "none found"
            check = f"{e(r['status'])}: read against the source<br/>{BOX} Staff confirm"
        rows.append([f"<b>{e(r['figure'])}</b>", e(r["sentence"][:260]), pub, check])
    html_ = ""
    if rows:
        html_ += table(rows, [11, 33, 38, 18], head=["Figure", "Our wording", "Published wording", "Check"])
    if bills:
        html_ += small("Bills and Acts named: " + e(", ".join(dict.fromkeys(bills))) + ". Each appears in a report or in the Legislature’s feed.")
    return html_, len(rows)


def figure_summary(c: dict) -> str:
    bits = [f"{c['sentence']} backed"] if c["sentence"] else []
    if c["accepted"]:
        bits.append(f"{c['accepted']} accepted")
    if c["topic"]:
        bits.append(f"{c['topic']} to check")
    return ", ".join(bits) or "no figures"


def positions_part(idx: dict, report: dict, allow: dict) -> tuple[str, list[dict]]:
    pos = [c for c in idx["core"] if c.get("pos")]
    by_title = {s["title"]: s for s in report["sections"]}
    gfx = {g["id"]: g for g in idx["graphics"]}
    out = [f'<h2 style="{HEAD}">Part 1. Policy positions ({len(pos)})</h2>',
           p("Each position is what the assistant says, word for word, when a visitor asks where Hawaiʻi Appleseed stands on that topic "
             "(for example, “What is your stance on the conveyance tax?”). No model is involved in that answer. The text comes from "
             "<code>positions.md</code>, adapted from the staff positions file, so approving a position means approving this wording.")]
    summary = []
    for n, c in enumerate(pos, 1):
        ref = f"position/{slug(c['title'])}"
        srep = by_title.get(c["title"], {"figures": []})
        counts = {k: sum(1 for r in srep["figures"] if r["status"] == k and not r["key"].startswith(("bill:", "act:"))) for k in ("sentence", "accepted", "topic")}
        summary.append((n, c["title"], c["group"], ref, [gfx[g]["title"] for g in c.get("graphics", []) if g in gfx], counts))
        research = [idx["pubs"][u] for u in c.get("research", []) if u in idx["pubs"]]
        rel = "<ul>" + "".join(f'<li style="{BODY}">{a(pb["t"], u)}' + (f" ({pb['y']})" if pb.get("y") else "") + "</li>" for u, pb in zip(c.get("research", []), research)) + "</ul>" if research else "None."
        details = [
            ["<b>What the assistant says</b>", p(cited(c["text"].strip() + " [1]"), "margin:0") + small(f"<sup>[1]</sup> {a(c['title'], c['url'])}  (the link shown under the answer)")],
            ["<b>Related research shown</b>", rel],
            ["<b>Chart shown with it</b>", "".join(graphic_lines(gfx[g]) for g in c.get("graphics", []) if g in gfx) or "None."],
            ["<b>How visitors reach it</b>", p(e("; ".join(c.get("aliases", []))) or "Its title only.") + small("A question about any of these topics gets this answer.")],
        ]
        figs, nfig = figure_rows(srep, allow, c["title"])
        out.append(f'<h3 style="{HEAD}">{n}. {e(c["title"])}</h3>' + small(f"{e(c['group'])} · status: draft"))
        out.append(table(details, [20, 80]))
        out.append(f'<p style="{BODY};margin:6pt 0 2pt"><b>Figures in this position and where they were found</b></p>' + (figs or p("No figures.")))
        out.append(f'<p style="{BODY};margin:8pt 0 2pt"></p>' + decision(ref, "this position"))
    return "\n".join(out), summary


def faq_part(idx: dict) -> str:
    entries = [f for f in idx["faq"] if f["variants"]]
    out = [f'<h2 style="{HEAD}">Part 2. Ready-made answers ({len(entries)})</h2>',
           p("These answer the questions asked most (mission, history, how to give, contact, jobs, “are you a bot?”, hello, thanks) "
             "instantly and identically, with no model. A question matches only when its topic words are exactly a listed phrasing’s, "
             "so a more specific question goes to the model instead.")]
    for n, f in enumerate(entries, 1):
        shown = f["variants"][:5]
        rest = len(f["variants"]) - len(shown)
        srcs = "".join(small(f"<sup>[{s['n']}]</sup> {a(s['title'], s['url'])}") for s in f["sources"])
        rows = [["<b>Asked as</b>", p("; ".join(e(v) for v in shown) + (f" … and {rest} more phrasings" if rest else ""))],
                ["<b>The assistant answers</b>", p(cited(f["answer"]), "margin:0") + srcs]]
        if f.get("graphic"):
            rows.append(["<b>Chart shown with it</b>", e(f["graphic"])])
        out.append(f'<h3 style="{HEAD}">{n}. {e(f["id"].replace("-", " ").capitalize())}</h3>' + table(rows, [20, 80]) + '<p style="margin:6pt 0 2pt"></p>' + decision(f"answer/{f['id']}", "this answer"))
    return "\n".join(out)


def fixed_part(idx: dict) -> str:
    fx = node_json("({legal: L.LEGAL_REPLY, declined: H.FRIENDLY.declined, unavailable: H.FRIENDLY.unavailable, sources: L.LEGAL_SOURCES})")
    nopos = next(f for f in idx["faq"] if f["id"] == "no-position")
    privacy = re.search(r'<p class="ha-ask__note">(.*?)</p>', (HERE / "index.html").read_text(encoding="utf-8"), re.S).group(1)
    privacy = html.unescape(re.sub(r"<[^>]+>", "", privacy)).strip()
    welcome = re.search(r"add\('bot', '(Hello\..*?)'\);", (HERE / "index.html").read_text(encoding="utf-8")).group(1)
    page_src = (HERE / "index.html").read_text(encoding="utf-8")
    person = json.loads(re.search(r"var PERSON = (\{.*?\});", page_src).group(1))
    c = idx["contact"]
    hand = "<br/>".join(e(x) for x in [
        f"{person['label']}  [{person['button']}]  [{person['call']} {c['phone']}]  [{person['page']}: {c['page']}]", person["help"], "",
        f"When the visitor clicks the button, their email app opens, addressed to {c['email']}, with this subject and message (they can edit it, and nothing is sent until they send it):", "",
        "Subject: " + person["subject"], "", *person["body"].replace("{question}", "<the visitor’s question>").split("\n")])
    share = json.loads(re.search(r"var SHARE = (\{.*?\});", page_src).group(1))
    share_html = "<br/>".join(e(x) for x in [
        f"Under every chart: [{share['image']}]  [{share['table']}]", "",
        "“" + share["image"] + "” puts a picture of the chart on the clipboard (or saves it as a file when the browser will not allow that). The picture carries the chart, its unit and note, its source, and this footer, so it keeps its source wherever it is pasted:",
        share["footer"],
        "On a chart the assistant drew itself, the picture also says: " + share["drawn"],
        "On a made-up illustration, it says: " + share["illustration"], "",
        "“" + share["table"] + "” copies the chart's figures as tab-separated text (with the note and the source) for a spreadsheet or document.",
        "Messages: " + " / ".join([share["copied"], share["saved"], share["failed"], share["manual"]])])
    items = [
        ("legal-help", "Reply to any request for legal help", "Always this exact text, never model-written. Triggered by a clear request for legal advice, a lawyer, or help with a personal case.",
         fx["legal"].replace(" [1]", "") + "  [link: " + fx["sources"][0]["title"] + "]"),
        ("no-position", "Reply when our work never covers a topic", "Used when a visitor asks where Hawaiʻi Appleseed stands on something its published work never touches. It never repeats the visitor’s words.", nopos["answer"]),
        ("cannot-answer", "Reply when the model declines", "", fx["declined"]),
        ("unavailable", "Reply when the assistant is down or out of budget", "", fx["unavailable"]),
        ("ask-a-person", "“Ask a person” button and prefilled email",
         "Shown under an answer when the assistant could not answer (it says it lacks the information, or the question is about the visitor’s own situation, or only staff could decide), and under the no-position reply. Never shown on a legal-help reply. The assistant never contacts anyone; the visitor sends the email from their own mail app.", {"html": hand}),
        ("share-chart", "Copy-a-chart buttons and the picture's footer",
         "Under every chart, so reporters, legislative staff and partners can reuse it with its source attached.", {"html": share_html}),
        ("welcome", "First message on the page", "", welcome),
        ("privacy-note", "Note under the chat box", "What visitors are told about AI, accuracy, legal advice, and privacy. Someone with authority over the organization’s public statements should approve this one.", privacy),
    ]
    out = [f'<h2 style="{HEAD}">Part 3. Fixed replies and page text ({len(items)})</h2>', p("Words the page or the Worker always uses, however a question is phrased.")]
    for n, (ref, title, why, text) in enumerate(items, 1):
        body_html = text["html"] if isinstance(text, dict) else cited(text)
        rows = [["<b>Exact text</b>", p(body_html, "margin:0")]]
        if why:
            rows.append(["<b>When it is used</b>", e(why)])
        out.append(f'<h3 style="{HEAD}">{n}. {e(title)}</h3>' + table(rows, [20, 80]) + '<p style="margin:6pt 0 2pt"></p>' + decision(f"fixed/{ref}", "this text"))
    return "\n".join(out)


def build_html() -> str:
    idx = b.build(public=False)
    report = idx["_report"]["figures"]
    ap = HERE / "content" / "figures.json"
    allow = {(x["section"], x["figure"]): x for x in json.loads(ap.read_text(encoding="utf-8"))["allow"]} if ap.exists() else {}
    commit = subprocess.run(["git", "-C", str(HERE), "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip() or "unknown"
    pos_html, summary = positions_part(idx, report, allow)
    rows = [[str(n), f"<b>{e(t)}</b>", e(g), e("; ".join(gt)) or "none", figure_summary(c)] for n, t, g, _, gt, c in summary]
    intro = f"""
<h1 style="{HEAD};font-size:22pt;margin-bottom:2pt">Ask Hawaiʻi Appleseed: Sign-off Review</h1>
<p style="{BODY};color:{TEAL};font-weight:700;letter-spacing:1pt;margin:0">DRAFT FOR STAFF REVIEW · built {date.today().isoformat()} from commit {e(commit)}</p>
{p("Ask Hawaiʻi Appleseed is a question-and-answer assistant for hiappleseed.org. It answers from our own published writing, links its sources, and answers any request for legal help with a fixed “no” plus a bar-association referral. "
   "<b>Nothing here is public yet.</b> A position goes live only after someone on staff approves it in this document and the site is rebuilt.")}
<h2 style="{HEAD}">How to review</h2>
<ol>
<li style="{BODY}">Read each item as a visitor would see it. The wording in the “What the assistant says” rows is exactly what the assistant will say, and it will say it without a model checking it.</li>
<li style="{BODY}">For positions, read the figures table. Each number is shown beside the published sentence it was matched to; the check proves the number was published in a similar context, not that our sentence means the same thing, so please compare the two. Rows marked “Staff confirm” are figures a first read accepted and a person should verify.</li>
<li style="{BODY}">In each decision box change ☐ to ☒ on one line, add your name and the date, and put edits or concerns in Notes. You can also edit the wording directly in the doc (use Suggesting mode so the change is visible).</li>
<li style="{BODY}">Leave the “Ref:” lines alone. They are how the decisions get applied.</li>
</ol>
<h2 style="{HEAD}">What gets approved</h2>
{table([[e(x), e(y)] for x, y in (("Part 1: positions", f"{len(summary)} stated positions. Each is shown with its chart, research links, and figures."),
                                      ("Part 2: ready-made answers", "Questions asked most, answered with fixed text."),
                                      ("Part 3: fixed replies and page text", "The legal-help reply, the no-position reply, the “ask a person” button and its prefilled email, the chart-sharing buttons, error messages, the welcome line, and the privacy note."))], [30, 70])}
{small("Everything else the assistant says comes from a model working only from our publications under strict rules (it must cite, may not invent a position or number, and may not give legal advice). That part is tested separately.")}
<h2 style="{HEAD}">Positions at a glance</h2>
{table(rows, [5, 28, 17, 28, 22], head=["#", "Position", "Area", "Chart", "Figures"])}
"""
    body = intro + pos_html + faq_part(idx) + fixed_part(idx) + f"""
<h2 style="{HEAD}">After review</h2>
{p("Decisions are read back from this document by reference (<code>chatbot/signoff_doc.py --read</code>). A ticked “Approve as written” with a name marks that position approved in <code>positions.md</code>; edits, holds, and removals are listed for a person to handle. An approved position still has to be built into the public version and deployed before visitors see it, and a public build checks its figures against our published work again.")}
"""
    return f'<html><head><meta charset="utf-8"><title>{e(DOC_NAME)}</title></head><body style="{BODY}">{body}</body></html>'


# ------------------------------------------------------------------ Google Drive side
def drive_python() -> list[str]:
    py = DRIVE_DIR / ".venv" / "bin" / "python"
    return [str(py), str(DRIVE_DIR / "filer.py")]


def fix_widths(doc_id: str, html_page: str) -> int:
    """Drive's importer ignores column widths, so every table comes out as equal columns. Set them from the data-w
    attributes, in document order."""
    sys.path.insert(0, str(DRIVE_DIR))
    from auth import services  # noqa: E402
    _, docs = services()
    specs = [[int(x) for x in m.split(",")] for m in re.findall(r'<table data-w="([\d,]+)"', html_page)]
    doc = docs.documents().get(documentId=doc_id).execute()
    st = doc["documentStyle"]
    usable = st["pageSize"]["width"]["magnitude"] - st.get("marginLeft", {}).get("magnitude", 72) - st.get("marginRight", {}).get("magnitude", 72)
    tables = [el for el in doc["body"]["content"] if "table" in el]
    if len(tables) != len(specs):
        print(f"widths: {len(tables)} tables in the Doc but {len(specs)} expected; leaving widths alone")
        return 0
    reqs = []
    for el, spec in zip(tables, specs):
        cols = len(el["table"]["tableRows"][0]["tableCells"])
        if cols != len(spec):
            continue
        for i, w in enumerate(spec):
            reqs.append({"updateTableColumnProperties": {
                "tableStartLocation": {"index": el["startIndex"]}, "columnIndices": [i],
                "tableColumnProperties": {"widthType": "FIXED_WIDTH", "width": {"magnitude": round(usable * w / sum(spec), 1), "unit": "PT"}},
                "fields": "widthType,width"}})
    for k in range(0, len(reqs), 150):
        docs.documents().batchUpdate(documentId=doc_id, body={"requests": reqs[k:k + 150]}).execute()
    return len(tables)


def break_pages(doc_id: str) -> int:
    """Start every position on its own page. Drive's importer ignores CSS page breaks, so insert real ones, last first
    so earlier positions do not shift."""
    sys.path.insert(0, str(DRIVE_DIR))
    from auth import services  # noqa: E402
    _, docs = services()
    body = docs.documents().get(documentId=doc_id).execute()["body"]["content"]
    inside, starts = False, []
    for el in body:
        para = el.get("paragraph")
        if not para:
            continue
        text = "".join(r.get("textRun", {}).get("content", "") for r in para["elements"]).strip()
        if para["paragraphStyle"].get("namedStyleType") == "HEADING_2":
            inside = text.startswith("Part 1.")
        elif inside and para["paragraphStyle"].get("namedStyleType") == "HEADING_3" and re.match(r"\d+\. ", text):
            starts.append(el["startIndex"])
    reqs = [{"insertPageBreak": {"location": {"index": i}}} for i in reversed(starts)]
    for k in range(0, len(reqs), 50):
        docs.documents().batchUpdate(documentId=doc_id, body={"requests": reqs[k:k + 50]}).execute()
    return len(reqs)


def set_fonts(doc_id: str) -> int:
    """Brand fonts: Poppins for text, Manrope for headings. Drive's importer applies them on create but falls back to Arial on
    update, so set them the same way every time."""
    sys.path.insert(0, str(DRIVE_DIR))
    from auth import services  # noqa: E402
    _, docs = services()
    body = docs.documents().get(documentId=doc_id).execute()["body"]["content"]
    end = body[-1]["endIndex"] - 1
    reqs = [{"updateTextStyle": {"range": {"startIndex": 1, "endIndex": end}, "fields": "weightedFontFamily",
                                 "textStyle": {"weightedFontFamily": {"fontFamily": "Poppins", "weight": 400}}}}]
    for el in body:
        para = el.get("paragraph")
        if para and para["paragraphStyle"].get("namedStyleType", "").startswith("HEADING") and el["endIndex"] - 1 > el["startIndex"]:
            reqs.append({"updateTextStyle": {"range": {"startIndex": el["startIndex"], "endIndex": el["endIndex"] - 1}, "fields": "weightedFontFamily",
                                             "textStyle": {"weightedFontFamily": {"fontFamily": "Manrope", "weight": 800}}}})
    for k in range(0, len(reqs), 100):
        docs.documents().batchUpdate(documentId=doc_id, body={"requests": reqs[k:k + 100]}).execute()
    return len(reqs) - 1


def doc_text(doc_id: str) -> list[str]:
    """Every paragraph of the Doc in reading order (tables included), as plain text."""
    sys.path.insert(0, str(DRIVE_DIR))
    from auth import services  # noqa: E402
    _, docs = services()
    doc = docs.documents().get(documentId=doc_id).execute()
    out: list[str] = []

    def walk(content):
        for el in content:
            if "paragraph" in el:
                out.append("".join(r.get("textRun", {}).get("content", "") for r in el["paragraph"]["elements"]).rstrip("\n"))
            elif "table" in el:
                for row in el["table"]["tableRows"]:
                    for cell in row["tableCells"]:
                        walk(cell["content"])
    walk(doc["body"]["content"])
    return out


def decisions(lines: list[str]) -> dict[str, dict]:
    """ref -> {ticked: [...], by: str, notes: str}, reading each item's lines between its Ref line and the next."""
    out: dict[str, dict] = {}
    cur = None
    for ln in lines:
        m = re.match(r"\s*Ref:\s*(\S+)", ln)
        if m:
            cur = out.setdefault(m.group(1), {"ticked": [], "by": "", "notes": ""})
            continue
        if cur is None:
            continue
        s = ln.strip()
        if s[:1] in TICKED:
            cur["ticked"].append(s[1:].strip())
        elif s.lower().startswith("reviewed by"):
            cur["by"] = s.split(":", 1)[1].strip() if ":" in s else ""
        elif s.lower().startswith("notes"):
            cur["notes"] = s.split(":", 1)[1].strip() if ":" in s else ""
    return out


def apply_approvals(found: dict[str, dict], write: bool) -> list[str]:
    path = HERE / "content" / "positions.md"
    text = path.read_text(encoding="utf-8")
    log = []
    for ref, d in found.items():
        if not ref.startswith("position/") or not d["ticked"]:
            continue
        slug_ = ref.split("/", 1)[1]
        if len(d["ticked"]) > 1:
            log.append(f"{ref}: more than one box ticked ({'; '.join(d['ticked'])}); not applied")
            continue
        if not d["ticked"][0].lower().startswith("approve") or "edits" in d["ticked"][0].lower():
            log.append(f"{ref}: {d['ticked'][0]!r}; for a person to handle. Notes: {d['notes'] or '-'}")
            continue
        m_date = re.search(r"\d{4}-\d{2}-\d{2}", d["by"])
        when = m_date.group(0) if m_date else date.today().isoformat()
        name = re.sub(r"\s+", " ", re.sub(r"\d{1,4}[-/]\d{1,2}[-/]\d{1,4}", "", d["by"])).strip(" ,;-")
        if not name:
            log.append(f"{ref}: approved but no reviewer name; not applied")
            continue
        m = None
        for h in re.finditer(r"^### (.+)$", text, re.M):
            if slug(h.group(1)) == slug_:
                m = h
                break
        if not m:
            log.append(f"{ref}: no such position in positions.md")
            continue
        end = text.find("\n### ", m.end())
        end = len(text) if end < 0 else end
        block = text[m.end():end]
        new, n = re.subn(r"<!--\s*status:.*?-->", f"<!-- status: approved by {name} {when} -->", block, count=1)
        if not n:
            log.append(f"{ref}: no status line to change")
            continue
        text = text[:m.end()] + new + text[end:]
        log.append(f"{ref}: approved by {name} {when}")
    if write:
        path.write_text(text, encoding="utf-8")
    return log


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--html", type=Path, help="write the review as HTML to this path")
    ap.add_argument("--file", action="store_true", help="create the Doc in Communications & Media > Website")
    ap.add_argument("--update", metavar="DOC_ID", help="replace an existing review's body (refuses if any box is ticked)")
    ap.add_argument("--read", metavar="DOC_ID", help="list the decisions made in the Doc")
    ap.add_argument("--apply", action="store_true", help="with --read: write approvals into positions.md")
    ap.add_argument("--force", action="store_true", help="with --update: overwrite even if boxes are ticked")
    a_ = ap.parse_args()

    if a_.read:
        found = decisions(doc_text(a_.read))
        print(f"{len(found)} items; {sum(1 for d in found.values() if d['ticked'])} with a decision")
        for ref, d in found.items():
            if d["ticked"]:
                print(f"  {ref}: {'; '.join(d['ticked'])}  | by: {d['by'] or '-'}  | notes: {d['notes'] or '-'}")
        log = apply_approvals(found, write=a_.apply)
        print(("\napplied to content/positions.md:" if a_.apply else "\nwould apply (dry run; add --apply):"))
        print("\n".join("  " + l for l in log) or "  nothing")
        return 0

    page = build_html()
    out = a_.html or Path("/tmp/signoff-review.html")
    out.write_text(page, encoding="utf-8")
    if a_.html and not (a_.file or a_.update):
        print(f"wrote {out} ({len(page) // 1024} KB)")
        return 0
    if a_.update:
        if not a_.force and any(d["ticked"] for d in decisions(doc_text(a_.update)).values()):
            raise SystemExit("someone has ticked a box in that Doc; --update would erase it. Read the decisions first, or pass --force.")
        cmd = drive_python() + [str(out), "--update", a_.update]
    elif a_.file:
        cmd = drive_python() + [str(out), "--folder", WEBSITE_FOLDER, "--name", DOC_NAME]
    else:
        raise SystemExit("pass --html, --file, --update, or --read")
    done = subprocess.run(cmd, capture_output=True, text=True)
    print(done.stdout, end="")
    if done.returncode:
        print(done.stderr, file=sys.stderr)
        return done.returncode
    doc_id = a_.update or re.search(r"^id\s*:\s*(\S+)", done.stdout, re.M).group(1)
    print(f"column widths set on {fix_widths(doc_id, page)} tables; page breaks before {break_pages(doc_id)} positions; "
          f"brand fonts on the text and {set_fonts(doc_id)} headings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
