"""End-to-end test of the monday app skeleton, with no monday account required.

Fakes the two JWTs monday would send, posts the payloads monday would post, and checks a
real document comes out the other end.

    DOCUGEN_FAKE_MONDAY=1 .venv/bin/python monday-app/tests_app.py
"""

from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import sys
import tempfile

SIGNING_SECRET = "test-signing-secret"
CLIENT_SECRET = "test-client-secret"
BASE_URL = "https://docugen.example.com"

WORK = pathlib.Path(tempfile.mkdtemp(prefix="docugen-app-test-"))
os.environ.update({
    "MONDAY_SIGNING_SECRET": SIGNING_SECRET,
    "MONDAY_CLIENT_SECRET": CLIENT_SECRET,
    "PUBLIC_BASE_URL": BASE_URL,
    "MONDAY_API_TOKEN": "fallback-token-for-item-view",
    "DOCUGEN_FAKE_MONDAY": "1",
    "DOCUGEN_TEMPLATE_DIR": str(WORK / "templates"),
    "DOCUGEN_OUTPUT_DIR": str(WORK / "output"),
})

sys.path.insert(0, str(pathlib.Path(__file__).parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import jwt  # noqa: E402

import docugen  # noqa: E402
import app as flask_app  # noqa: E402
import generator  # noqa: E402
import jobs  # noqa: E402

BOARD = {
    "id": "111", "name": "Client Projects",
    "columns": [
        {"id": "text", "title": "Client Name", "type": "text"},
        {"id": "status", "title": "Status", "type": "status"},
        {"id": "numbers", "title": "Amount", "type": "numbers"},
        {"id": "date4", "title": "Due Date", "type": "date"},
    ],
    "groups": [{"id": "topics", "title": "Q3"}],
}

checks = []


def check(name: str, condition: bool, detail: str = "") -> None:
    checks.append((name, condition, detail))
    print(f"{'PASS' if condition else 'FAIL'}  {name}{'  — ' + detail if detail else ''}")


def integration_jwt(path: str, *, secret=SIGNING_SECRET, expired=False) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    return jwt.encode({
        "accountId": 1825528, "userId": 4012689,
        "aud": f"{BASE_URL}{path}",
        "iat": now, "exp": now + dt.timedelta(minutes=-5 if expired else 5),
        "shortLivedToken": "short-lived-abc",
    }, secret, algorithm="HS256")


def session_jwt(secret=CLIENT_SECRET) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    return jwt.encode({"accountId": 1825528, "userId": 4012689,
                       "iat": now, "exp": now + dt.timedelta(minutes=30)},
                      secret, algorithm="HS256")


def main() -> int:
    generator.TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    docugen.scaffold_template(BOARD, generator.TEMPLATE_DIR / "quote.docx", "item")
    client = flask_app.app.test_client()

    # ---- auth ------------------------------------------------------------------
    path = "/monday/actions/generate"
    payload = {"payload": {"blockKind": "action", "inputFields": {
        "itemId": "555", "template": "quote.docx", "outputFormat": "docx"}}}

    r = client.post(path, json=payload)
    check("missing JWT rejected", r.status_code == 401, r.get_data(as_text=True)[:80])

    r = client.post(path, json=payload,
                    headers={"Authorization": integration_jwt(path, secret="wrong")})
    check("JWT signed with the wrong secret rejected", r.status_code == 401)

    r = client.post(path, json=payload,
                    headers={"Authorization": integration_jwt(path, expired=True)})
    check("expired JWT rejected", r.status_code == 401)

    r = client.post(path, json=payload,
                    headers={"Authorization": integration_jwt("/monday/fields/templates")})
    check("JWT for a different endpoint rejected (aud check)", r.status_code == 401)

    r = client.post("/api/generate", json={"itemId": "555"},
                    headers={"Authorization": session_jwt(secret=SIGNING_SECRET)})
    check("signing-secret token rejected on a session endpoint", r.status_code == 401)

    # ---- custom action ---------------------------------------------------------
    r = client.post(path, json=payload,
                    headers={"Authorization": f"Bearer {integration_jwt(path)}"})
    check("valid action returns 200 immediately", r.status_code == 200, r.get_data(as_text=True))
    job_id = r.get_json().get("jobId")
    jobs.wait_for_idle()
    job = jobs.get(job_id)
    check("action job completed", job and job["status"] == "done",
          (job or {}).get("error") or "")
    produced = pathlib.Path(job["result"]["file"]) if job and job["result"] else None
    check("document written to disk", bool(produced and produced.exists()),
          str(produced))

    # the item id can also arrive via inboundFieldValues, as an object
    r = client.post(path, headers={"Authorization": integration_jwt(path)}, json={"payload": {
        "inboundFieldValues": {"itemId": {"value": "777"}},
        "inputFields": {"template": "quote", "outputFormat": "pdf",
                        "filesColumn": "files"}}})
    jobs.wait_for_idle()
    job = jobs.get(r.get_json()["jobId"])
    check("alternate payload shape + PDF + upload",
          job and job["status"] == "done" and job["result"]["format"] == "pdf"
          and job["result"].get("uploaded", {}).get("column_id") == "files",
          (job or {}).get("error") or "")
    pdf = pathlib.Path(job["result"]["file"]) if job and job["result"] else None
    check("PDF is a real PDF",
          bool(pdf and pdf.exists() and pdf.open("rb").read(5) == b"%PDF-"), str(pdf))

    r = client.post(path, json={"payload": {"inputFields": {}}},
                    headers={"Authorization": integration_jwt(path)})
    check("payload with no item id answers 200, not a retry storm",
          r.status_code == 200 and r.get_json().get("ignored") is True)

    # ---- remote options --------------------------------------------------------
    opts_path = "/monday/fields/templates"
    r = client.post(opts_path, headers={"Authorization": integration_jwt(opts_path)})
    body = r.get_json()
    check("remote options lists templates",
          r.status_code == 200 and body["options"][0]["value"] == "quote.docx",
          json.dumps(body))

    # ---- item view API ---------------------------------------------------------
    session = {"Authorization": session_jwt()}
    r = client.get("/api/templates", headers=session)
    check("item view can list templates", r.status_code == 200)

    r = client.post("/api/generate", json={"itemId": "555", "template": "quote.docx"},
                    headers=session)
    check("item view generate accepted", r.status_code == 202, r.get_data(as_text=True))
    view_job = r.get_json()["jobId"]
    jobs.wait_for_idle()
    r = client.get(f"/api/jobs/{view_job}", headers=session)
    check("job status readable", r.status_code == 200 and r.get_json()["status"] == "done",
          r.get_data(as_text=True)[:120])

    r = client.get(f"/api/jobs/{view_job}/download", headers=session)
    check("generated file downloadable", r.status_code == 200 and len(r.data) > 5000,
          f"{r.status_code}, {len(r.data)} bytes")

    r = client.get("/api/jobs/does-not-exist", headers=session)
    check("unknown job is a 404", r.status_code == 404)

    # ---- bad template ----------------------------------------------------------
    r = client.post("/api/generate", headers=session,
                    json={"itemId": "555", "template": "../../../etc/passwd"})
    jobs.wait_for_idle()
    job = jobs.get(r.get_json()["jobId"])
    check("path traversal in a template name is refused",
          job["status"] == "error" and "not found" in (job["error"] or "").lower(),
          job.get("error") or "")

    # ---- views -----------------------------------------------------------------
    r = client.get("/health")
    body = r.get_json()
    check("health reports PDF support", r.status_code == 200 and body["pdf_supported"] is True,
          json.dumps(body))
    r = client.get("/")
    check("item view HTML served",
          r.status_code == 200 and b"mondaySdk" in r.data)

    failed = [n for n, ok, _ in checks if not ok]
    print(f"\n{len(checks) - len(failed)}/{len(checks)} checks passed")
    if failed:
        print("failed: " + ", ".join(failed))
    print(f"artifacts: {WORK}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
