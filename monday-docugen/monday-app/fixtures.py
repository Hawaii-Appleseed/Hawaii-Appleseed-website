"""Fake monday API responses so the whole app can be exercised without an account.

Enabled with DOCUGEN_FAKE_MONDAY=1. Used by tests_app.py and handy for demoing the
item view locally before the app exists in a monday Developer Center.
"""

import json


def _cv(cid, title, ctype, text, value=None, display=None):
    col = {"id": cid, "type": ctype, "text": text,
           "value": json.dumps(value) if value is not None else None,
           "column": {"id": cid, "title": title, "type": ctype}}
    if display is not None:
        col["display_value"] = display
    return col


def fake_item(item_id: str) -> dict:
    return {
        "id": str(item_id),
        "name": "Acme Rebrand",
        "url": f"https://example.monday.com/boards/111/pulses/{item_id}",
        "state": "active",
        "created_at": "2026-01-05T10:00:00Z",
        "updated_at": "2026-02-01T10:00:00Z",
        "group": {"id": "topics", "title": "Q3"},
        "board": {"id": "111", "name": "Client Projects"},
        "column_values": [
            _cv("text", "Client Name", "text", "Acme Corp"),
            _cv("status", "Status", "status", "Working on it", {"index": 0}),
            _cv("numbers", "Amount", "numbers", "12500.5"),
            _cv("date4", "Due Date", "date", "2026-09-30", {"date": "2026-09-30"}),
            _cv("person", "Owner", "people", "Dana Lee"),
            _cv("dropdown", "Services", "dropdown", "Design, Copywriting"),
            _cv("check", "Signed?", "checkbox", "v", {"checked": "true"}),
        ],
        "subitems": [
            {"id": "1", "name": "Logo", "column_values": [
                _cv("status", "Status", "status", "Done")]},
            {"id": "2", "name": "Website", "column_values": [
                _cv("status", "Status", "status", "Stuck")]},
        ],
    }
