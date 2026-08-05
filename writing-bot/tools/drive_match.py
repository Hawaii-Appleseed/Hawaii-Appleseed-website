#!/usr/bin/env python3
"""
Match each corpus document to its Google Doc in a Drive folder, by title, and
bake the resulting links into static-search/data/docs.json (field: ref.gdoc).

Runs at BUILD time only — the static site never touches the Drive API or any
credentials; it just reads the precomputed URL. By default only documents that
have NO existing link (testimony, reference) get a Drive link (--scope missing);
pass --scope all to link every document.

Auth: a Google service account with VIEWER access to the folder (share the
folder with the service account's client_email). Point GOOGLE_APPLICATION_CREDENTIALS
at its JSON key. Folder: pass --folder <id-or-url> or set DRIVE_FOLDER_ID.

    pip install google-api-python-client google-auth
    GOOGLE_APPLICATION_CREDENTIALS=sa.json \
      python tools/drive_match.py --folder <drive-folder-url-or-id> --scope missing

Reports matched / unmatched documents so gaps are visible (never silent).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS_JSON = ROOT / "static-search" / "data" / "docs.json"

GOOGLE_DOC_MIME = "application/vnd.google-apps.document"
FOLDER_MIME = "application/vnd.google-apps.folder"


def _norm(s: str) -> str:
    """Normalize a title for matching: lowercase, drop the ʻokina and
    punctuation, collapse whitespace."""
    s = s.replace("ʻ", "").replace("'", "").lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _folder_id(arg: str | None) -> str:
    val = arg or os.environ.get("DRIVE_FOLDER_ID", "")
    if not val:
        sys.exit("No folder given. Pass --folder <url-or-id> or set DRIVE_FOLDER_ID.")
    # Accept a full URL (…/folders/<id>?…) or a bare id.
    m = re.search(r"/folders/([A-Za-z0-9_-]+)", val)
    return m.group(1) if m else val


SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


def _service():
    """Authenticate via, in order: a service-account JSON pointed at by
    GOOGLE_APPLICATION_CREDENTIALS, else application-default credentials
    (e.g. `gcloud auth application-default login --scopes=...,drive.readonly`)."""
    try:
        from googleapiclient.discovery import build
    except ImportError:
        sys.exit("Missing deps. Run: pip install google-api-python-client google-auth")

    key = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if key and Path(key).exists():
        from google.oauth2 import service_account
        creds = service_account.Credentials.from_service_account_file(key, scopes=SCOPES)
    else:
        import google.auth
        try:
            creds, _ = google.auth.default(scopes=SCOPES)
        except Exception:
            sys.exit(
                "No Google credentials. Either set GOOGLE_APPLICATION_CREDENTIALS to a "
                "service-account JSON (folder shared to it), or run:\n"
                "  gcloud auth application-default login "
                "--scopes=openid,https://www.googleapis.com/auth/drive.readonly")
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def list_folder(svc, folder_id: str) -> list[dict]:
    """Recursively list all files (not sub-folders) under `folder_id`."""
    out, stack = [], [folder_id]
    while stack:
        fid = stack.pop()
        page_token = None
        while True:
            resp = svc.files().list(
                q=f"'{fid}' in parents and trashed = false",
                fields="nextPageToken, files(id, name, mimeType, webViewLink)",
                pageSize=1000, pageToken=page_token,
                supportsAllDrives=True, includeItemsFromAllDrives=True,
            ).execute()
            for f in resp.get("files", []):
                if f["mimeType"] == FOLDER_MIME:
                    stack.append(f["id"])
                else:
                    out.append(f)
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
    return out


def build_title_index(files: list[dict]) -> dict[str, dict]:
    """normalized-title -> file. Prefer native Google Docs on collision."""
    idx: dict[str, dict] = {}
    for f in files:
        key = _norm(f["name"])
        if not key:
            continue
        cur = idx.get(key)
        if cur is None or (f["mimeType"] == GOOGLE_DOC_MIME and cur["mimeType"] != GOOGLE_DOC_MIME):
            idx[key] = f
    return idx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", help="Drive folder URL or id (or DRIVE_FOLDER_ID env)")
    ap.add_argument("--scope", choices=["missing", "all"], default="missing")
    ap.add_argument("--dry-run", action="store_true", help="report matches, don't write")
    args = ap.parse_args()

    if not DOCS_JSON.exists():
        sys.exit(f"{DOCS_JSON} not found — run tools/build_static.py first.")
    docs = json.loads(DOCS_JSON.read_text())

    svc = _service()
    files = list_folder(svc, _folder_id(args.folder))
    print(f"Drive folder: {len(files)} files")
    idx = build_title_index(files)

    matched, unmatched = [], []
    for src, d in docs.items():
        ref = d.get("ref") or {}
        has_link = ref.get("url") or ref.get("pdf")
        if args.scope == "missing" and has_link:
            continue
        # Try the document's display title, then the filename stem.
        stem = Path(src).stem
        stem = re.sub(r"^\d{4}-\d{2}-\d{2}[_-]", "", stem)  # drop date prefix
        cand_keys = [_norm(d.get("title", "")), _norm(stem.replace("-", " "))]
        hit = next((idx[k] for k in cand_keys if k and k in idx), None)
        if hit:
            ref["gdoc"] = hit["webViewLink"]
            d["ref"] = ref
            matched.append((src, hit["name"]))
        else:
            unmatched.append((src, d.get("title", "")))

    print(f"\nMatched {len(matched)} document(s) to a Google Doc:")
    for src, name in matched[:50]:
        print(f"  ✓ {Path(src).name}  ->  {name}")
    if unmatched:
        print(f"\nUnmatched ({len(unmatched)}) — no title match in the folder:")
        for src, title in unmatched[:50]:
            print(f"  -- {Path(src).name}  ({title})")

    if args.dry_run:
        print("\n(dry run — docs.json not written)")
        return
    DOCS_JSON.write_text(json.dumps(docs, ensure_ascii=False))
    print(f"\nWrote ref.gdoc into {DOCS_JSON.relative_to(ROOT)} for {len(matched)} docs.")


if __name__ == "__main__":
    main()
