#!/usr/bin/env python3
"""Bring Hawaiʻi Appleseed's submitted testimony from the shared Drive into writing-bot/testimony/.

Run weekly by .github/workflows/refresh-testimony.yml; safe to run by hand:

    python writing-bot/sync_testimony.py            # add new testimony, update the record
    python writing-bot/sync_testimony.py --dry-run  # say what it would add, write nothing

What counts as testimony to add (each rule is something a real Drive file got wrong):
  - it sits in a testimony folder under one of ROOTS (state-legislative work only)
  - it is a Google Doc, Word .docx, or PDF with a text layer
  - Hawaiʻi Appleseed (or its legal name) is in the letterhead or signature, not just mentioned
    (folders also hold other groups' testimony and the Legislature's compiled packets)
  - it names a bill (HB/SB/HCR/SCR/HR/SR) and reads as testimony
  - no template placeholders ("[INSERT…", "[Your Name]"), and not named sample, template, tool kit,
    DRAFT, NOT SUBMITTED, talking points, or oral/verbal/spoken notes
  - not a copy of testimony already in the corpus (a PDF beside its Doc, or the same letter
    sent to a second committee)

The record of every Drive file looked at, and what became of it, is content-monitor/testimony-drive.json
(Drive ids, dates and decisions only: no names, folder paths or text, since this repository is public). A file is looked at again only if it changed since.
A file already added is never rewritten: submitted testimony does not change, and a later edit in
Drive is more likely a reuse for next session than a correction.

Credentials: GOOGLE_DRIVE_TOKEN (authorized-user JSON with a refresh token, drive.readonly scope),
else ~/.config/appleseed-drive/token.json. It reads as that person, so Drive's own sharing applies.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEST = ROOT / "testimony"
STATE = ROOT / "content-monitor" / "testimony-drive.json"

# Folders (by path under the shared drive) that hold the organization's own state-legislative testimony.
ROOTS = re.compile(
    r"^Drive/(Legislative/State legislative/"
    r"|Projects/Transportation Equity Projects/Legislation/20\d\d"
    r"|Projects/Food Equity Projects/Universal Free School Meals"
    r"|Projects/Housing Projects/Community Engagement/20\d\d Testimony"
    r"|Litigation - LEJ/Legislative)"
)
SKIP_PATH = re.compile(
    r"(?i)sample|template|tool ?kit|brochure|report card|graphics|memes|customer testimony|model testimony"
    r"|spoken testimon|verbal testimony|oral testimony|one pager|research and data|talking points|speech"
    r"|\bdraft\b|not submitted"
)
FOLDER = "application/vnd.google-apps.folder"
GDOC = "application/vnd.google-apps.document"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PDF = "application/pdf"

BILL = re.compile(r"(?<![A-Za-z])(HB|SB|HCR|SCR|HR|SR|H\.B\.|S\.B\.)\s*(\d{1,4})(?!\d)")
ORG = re.compile(r"(?i)appleseed|law and economic justice|budget (and|&) policy center")
PLACEHOLDER = re.compile(r"(?i)\[\s*(insert|your|name|please|personal|add|tk|xx)|\bTK\b|\[\s*\]|lorem ipsum|<<")
LIKE_TESTIMONY = re.compile(r"(?i)testif|testimony|\bchair\b|committee")
PACKET = re.compile(r"_TESTIMONY_[A-Z-]+_\d")  # the Legislature's compiled packet of everyone's testimony
MONTH = r"(January|February|March|April|May|June|July|August|September|October|November|December)"
COMMITTEE = re.compile(
    r"(?<![A-Z])(FIN|WAM|HHS|HSH|EDN|EDU|JDC|JHA|CPC|CPN|HSG|HOU|LBT|LAB|TRN|TRS|ECD|AGR|AEN|HLT|HUS|PSM|LCA|GVO"
    r"|JGO|WLA|EEP|WTL|HHH|HRE|HET|PDP|LMG|TCA|ACR|CMV|HED)(?![A-Z])"
)
TOPIC_BY_PATH = [("labor", "Foster Care"), ("food-equity", "Food Equity"), ("transportation", "Transportation"),
                 ("housing", "Housing"), ("labor", "Labor"), ("labor", "Healthcare"), ("tax-and-budget", "Tax"),
                 ("tax-and-budget", "HBPC")]
TOPIC_WORDS = [("food-equity", r"(?i)food|meal|snap|farm|hunger|nutrition|wic\b"),
               ("transportation", r"(?i)transport|transit|pedestrian|bike|bus\b|traffic|street|walk|vehicle|road"),
               ("housing", r"(?i)housing|tenant|landlord|evict|rent|homeless|zoning|conveyance"),
               ("labor", r"(?i)labor|wage|worker|leave|employ|health|medical|insurance|immigra"),
               ("tax-and-budget", r"(?i)tax|budget|revenue|credit|eitc|appropriat")]


# ------------------------------------------------------------------ pure rules (tested)
def judge(name: str, path: str, text: str) -> str | None:
    """Why this file is not testimony to add, or None if it is."""
    if SKIP_PATH.search(path + "/" + name):
        return "sample, draft, notes or other non-testimony"
    if PACKET.search(name):
        return "the Legislature's compiled packet"
    t = text.strip()
    if len(t.split()) < 150:
        return "too short, or a scan with no text"
    if re.match(r"(?i)\s*﻿?\s*(draft|current draft)\b", t):
        return "marked draft"
    if not (ORG.search(t[:900]) or ORG.search(t[-1500:]) or re.search(r"(?i)\bHA\b|appleseed", name)):
        return "not Hawaiʻi Appleseed's"
    if not BILL.search(name) and not BILL.search(t[:3000]):
        return "names no bill"
    if not LIKE_TESTIMONY.search(t[:3000]):
        return "does not read as testimony"
    if PLACEHOLDER.search(t):
        return "template placeholders"
    return None


def bill_of(name: str, text: str) -> str:
    m = BILL.search(name) or BILL.search(text[:3000])
    return m.group(1).replace(".", "").upper() + str(int(m.group(2)))


def year_of(path: str, text: str, modified: str) -> int:
    """The session: the deepest year in the folder path, else the hearing date, else when the file last changed."""
    ys = re.findall(r"(?<!\d)(20[012]\d)(?!\d)", path.replace("2024 and prior", ""))
    if ys:
        return int(ys[-1])
    m = re.search(MONTH + r"\.?\s+\d{1,2},?\s+(20[012]\d)", text[:2500])
    return int(m.group(2)) if m else int(modified[:4])


def topic_of(path: str, name: str, text: str) -> str:
    for topic, key in TOPIC_BY_PATH:
        if key in path:
            return topic
    head = name + " " + text[:1500]
    scores = {t: len(re.findall(rx, head)) for t, rx in TOPIC_WORDS}
    return max(scores, key=scores.get)


def file_name(name: str, text: str, year: int) -> str:
    """BILL_COMMITTEE_subject_YEAR.txt, the corpus convention (bot.py and the Q&A bot read bill and year from it)."""
    bill = bill_of(name, text)
    comm = COMMITTEE.search(name)
    stem = re.sub(r"(?i)\.(pdf|docx?|txt)$", "", name)
    stem = BILL.sub("", stem)
    if comm:
        stem = re.sub(r"(?<![A-Z])" + comm.group(1) + r"(?![A-Z])", "", stem)
    stem = re.sub(r"(?i)testimony|\b20\d\d\b|\d+[./]\d+[./]\d+", "", stem)
    slug = re.sub(r"[^A-Za-z0-9]+", "_", stem).strip("_")[:40] or "testimony"
    return "_".join(x for x in [bill, comm.group(1) if comm else None, slug, str(year)] if x) + ".txt"


def clean(text: str, from_pdf: bool) -> str:
    t = text.replace("\r\n", "\n").replace("\r", "\n").lstrip("﻿")
    if from_pdf:
        t = re.sub(r"[ \t]*\n[ \t]*", "\n", t)
        t = re.sub(r"(?<![.!?:;\n])\n(?!\n)", " ", t)  # rejoin hard-wrapped lines
        t = re.sub(r"[ \t]{2,}", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return fix_okina(t.strip()) + "\n"


def fix_okina(t: str) -> str:
    """Word and PDFs turn the ʻokina into a quote mark ("Hawai'i", "O‘ahu"); the corpus uses U+02BB, as the  # okina-lint:ignore
    repo's pre-commit lint requires. A quote between letters followed by a vowel is an ʻokina; English
    contractions and possessives are followed by a consonant (don't, it's, Appleseed's)."""
    return re.sub(r"(?<=[A-Za-zāēīōūĀĒĪŌŪ])[‘’'`](?=[aeiouāēīōū])", "ʻ", t)


def words(text: str) -> set[str]:
    return set(re.findall(r"[a-z]{4,}", text.lower()))


def is_copy(new: set[str], old: set[str]) -> bool:
    """Same letter: a PDF beside its Doc, a re-send to a second committee, or a piece already in the corpus."""
    return len(new & old) / max(1, min(len(new), len(old))) > 0.8


# ------------------------------------------------------------------ Drive
def drive():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    raw = os.environ.get("GOOGLE_DRIVE_TOKEN")
    if raw:
        info = json.loads(raw)
    else:
        info = json.loads((Path.home() / ".config" / "appleseed-drive" / "token.json").read_text())
    creds = Credentials.from_authorized_user_info(info)
    if not creds.valid:
        creds.refresh(Request())
    return build("drive", "v3", credentials=creds, cache_discovery=False)


KW = dict(corpora="allDrives", includeItemsFromAllDrives=True, supportsAllDrives=True)


def listing(d, q: str) -> list[dict]:
    out, tok = [], None
    while True:
        r = d.files().list(q=q, pageSize=200, pageToken=tok,
                           fields="nextPageToken,files(id,name,mimeType,parents,modifiedTime)", **KW).execute()
        out += r["files"]
        tok = r.get("nextPageToken")
        if not tok:
            return out


def testimony_files(d) -> list[dict]:
    """Every Doc/Word/PDF under a testimony folder in ROOTS, with its folder path."""
    names: dict[str, tuple[str, str | None]] = {}

    def path(fid):
        parts = []
        while fid and len(parts) < 10:
            if fid not in names:
                try:
                    f = d.files().get(fileId=fid, fields="name,parents", supportsAllDrives=True).execute()
                    names[fid] = (f["name"], (f.get("parents") or [None])[0])
                except Exception:  # noqa: BLE001  (a parent we cannot see ends the path)
                    names[fid] = ("?", None)
            n, fid = names[fid]
            parts.append(n)
        return "/".join(reversed(parts))

    folders = listing(d, f"mimeType='{FOLDER}' and name contains 'testimony' and trashed=false")
    folders = [f for f in folders if ROOTS.search(path(f["id"]))]
    seen, stack, files = set(), [f["id"] for f in folders], {}
    while stack:
        fid = stack.pop()
        if fid in seen:
            continue
        seen.add(fid)
        for f in listing(d, f"'{fid}' in parents and trashed=false"):
            if f["mimeType"] == FOLDER:
                stack.append(f["id"])
            elif f["mimeType"] in (GDOC, DOCX, PDF):
                files[f["id"]] = f
    for f in files.values():
        f["path"] = path((f.get("parents") or [None])[0])
    return [f for f in files.values() if ROOTS.search(f["path"])]


def text_of(d, f) -> str:
    if f["mimeType"] == GDOC:
        return d.files().export(fileId=f["id"], mimeType="text/plain").execute().decode("utf-8", "ignore")
    data = d.files().get_media(fileId=f["id"], supportsAllDrives=True).execute()
    if f["mimeType"] == PDF:
        import pypdf
        try:
            return "\n".join((p.extract_text() or "") for p in pypdf.PdfReader(io.BytesIO(data)).pages)
        except Exception:  # noqa: BLE001  (a broken PDF is just not added)
            return ""
    import docx
    return "\n".join(p.text for p in docx.Document(io.BytesIO(data)).paragraphs)


# ------------------------------------------------------------------ run
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    corpus = {p: words(p.read_text(encoding="utf-8", errors="ignore"))
              for p in DEST.glob("*/*.txt") if not p.name.startswith("sample_")}
    d = drive()
    files = testimony_files(d)
    todo = [f for f in files if f["id"] not in state
            or (state[f["id"]].get("file") is None and f["modifiedTime"] > state[f["id"]]["modified"])]
    # Docs before PDFs (Doc text extracts cleanly), newest first, so the copy kept is the best one.
    todo.sort(key=lambda f: f["modifiedTime"], reverse=True)
    todo.sort(key=lambda f: f["mimeType"] == PDF)  # stable: Docs (newest first), then PDFs
    added = []
    for f in todo:
        text = text_of(d, f)
        why = judge(f["name"], f["path"], text)
        out = None
        if not why:
            body = clean(text, f["mimeType"] == PDF)
            w = words(body)
            twin = next((p for p, o in corpus.items() if is_copy(w, o)), None)
            if twin:
                why = f"copy of {twin.relative_to(ROOT)}"
            else:
                y = year_of(f["path"], text, f["modifiedTime"])
                out = DEST / topic_of(f["path"], f["name"], text) / file_name(f["name"], text, y)
                n = 2
                while out.exists() or out in corpus:
                    out = out.with_name(f"{out.stem.rsplit('_v', 1)[0]}_v{n}.txt"); n += 1
                corpus[out] = w
                added.append(str(out.relative_to(ROOT)))
                if not args.dry_run:
                    out.parent.mkdir(parents=True, exist_ok=True)
                    out.write_text(body, encoding="utf-8")
        # Ids, dates and decisions only: this repository is public, and Drive names and folder paths are internal.
        state[f["id"]] = {"modified": f["modifiedTime"],
                          "file": str(out.relative_to(ROOT)) if out else None, "why_not": why}
    if not args.dry_run:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(dict(sorted(state.items())), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"testimony: {len(files)} Drive files in testimony folders, {len(todo)} new or changed, {len(added)} added")
    for a in added:
        print(f"  {a}")
    print(f"NEW_FILES={len(added)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
