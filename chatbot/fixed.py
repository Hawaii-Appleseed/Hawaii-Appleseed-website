"""The words the page or the Worker always uses, however a question is phrased: the legal-help reply, the replies when the
model declines or the assistant is down, the welcome line, the note under the chat box, the "ask a person" and chart-sharing
wording. There is no fallback for these (no model to hand a question to), so they are approved as a set: a public build
refuses to run until every one is approved, and approval is of the exact words (approval.py).

`items()` is the one place that knows where each lives (JavaScript constants in the Worker, JSON and text in index.html), so the
sign-off review and the public build always look at the same words. It needs `node`, which the Worker's own tooling needs anyway.
Statuses live in content/fixed.json.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import approval

HERE = Path(__file__).resolve().parent
STATUS_FILE = HERE / "content" / "fixed.json"
ORDER = ["legal-help", "cannot-answer", "unavailable", "ask-a-person", "share-chart", "welcome", "privacy-note"]


def _node(expr: str):
    base = (HERE / "worker" / "src").as_posix()
    code = f"import('{base}/legal.js').then(async L => {{ const H = await import('{base}/handler.js'); console.log(JSON.stringify({expr})); }})"
    try:
        return json.loads(subprocess.run(["node", "-e", code], capture_output=True, text=True, check=True).stdout)
    except (OSError, subprocess.CalledProcessError) as err:
        raise SystemExit(f"fixed replies live in the Worker's JavaScript, so this needs node ({err})")


def items(root: Path | None = None) -> dict[str, dict]:
    """id -> {title, why, parts} where `parts` are the exact strings (in a fixed order) that a reviewer approves."""
    page = ((root or HERE) / "index.html").read_text(encoding="utf-8")
    js = _node("({legal: L.LEGAL_REPLY, declined: H.FRIENDLY.declined, unavailable: H.FRIENDLY.unavailable})")
    person = json.loads(re.search(r"var PERSON = (\{.*?\});", page).group(1))
    share = json.loads(re.search(r"var SHARE = (\{.*?\});", page).group(1))
    note = re.search(r'<p class="ha-ask__note">(.*?)</p>', page, re.S).group(1)
    import html as _html
    privacy = _html.unescape(re.sub(r"<[^>]+>", "", note)).strip()
    welcome = re.search(r"add\('bot', '(Hello\..*?)'\);", page).group(1)
    return {
        "legal-help": {"title": "Reply to any request for legal help", "parts": [js["legal"]],
                       "why": "Always this exact text, never model-written. Triggered by a clear request for legal advice, a lawyer, or help with a personal case."},
        "cannot-answer": {"title": "Reply when the model declines", "parts": [js["declined"]], "why": ""},
        "unavailable": {"title": "Reply when the assistant is down or out of budget", "parts": [js["unavailable"]], "why": ""},
        "ask-a-person": {"title": "“Ask a person” button and prefilled email", "parts": [person[k] for k in sorted(person)],
                         "why": "Shown under an answer when the assistant could not answer (it says it lacks the information, or the question is about the visitor’s own situation, or only staff could decide), and under the no-position reply. Never shown on a legal-help reply. The assistant never contacts anyone; the visitor sends the email from their own mail app."},
        "share-chart": {"title": "Copy-a-chart buttons and the picture's footer", "parts": [share[k] for k in sorted(share)],
                        "why": "Under every chart, so reporters, legislative staff and partners can reuse it with its source attached."},
        "welcome": {"title": "First message on the page", "parts": [welcome], "why": ""},
        "privacy-note": {"title": "Note under the chat box", "parts": [privacy],
                         "why": "What visitors are told about AI, accuracy, legal advice, and privacy. Someone with authority over the organization’s public statements should approve this one."},
    }


def statuses() -> dict[str, dict]:
    return json.loads(STATUS_FILE.read_text(encoding="utf-8"))["items"] if STATUS_FILE.exists() else {}


def hash_of(item: dict) -> str:
    return approval.fixed_hash(item["parts"])


def problems(root: Path | None = None) -> list[str]:
    """What stops a public build: every fixed item that is not approved, or whose words changed since it was."""
    st = statuses()
    out = []
    for iid, item in items(root).items():
        rec = st.get(iid, {})
        ok, why = approval.judge(rec.get("status"), rec.get("reviewed"), hash_of(item))
        if not ok:
            out.append(f"{iid} ({item['title']}): {why}")
    return out
