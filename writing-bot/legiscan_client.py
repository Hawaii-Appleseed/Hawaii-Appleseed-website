"""
Minimal LegiScan API client for the Hawaiʻi Appleseed bill watcher.

Why this file: LegiScan rotates `session_id` each legislative session, so any
hardcoded value (e.g. 2089 for 2026 HI) breaks every January. This client
resolves the active HI session dynamically per run.

API key from env `LEGISCAN_API_KEY`. Free tier = 30K queries/month.

Public surface:
    get_active_hi_session_id() -> int
    get_master_list(session_id) -> dict[bill_number, dict]   # includes change_hash, bill_id
    get_bill(bill_id) -> dict                                 # full payload (cached by change_hash)
    invalidate_cache()

Cache: ~/.openclaw/state/legiscan-cache.json — keyed by bill_id; we skip the
fetch when the cached change_hash matches the master-list change_hash.
"""

from __future__ import annotations

import json
import os
import time
from datetime import date
from pathlib import Path

import requests

API_BASE = "https://api.legiscan.com/"
CACHE_PATH = Path.home() / ".openclaw" / "state" / "legiscan-cache.json"
REQUEST_TIMEOUT = 30


class LegiScanError(Exception):
    pass


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

def _load_cache() -> dict:
    if CACHE_PATH.exists():
        try:
            return json.loads(CACHE_PATH.read_text())
        except Exception:
            return {}
    return {}


def _save_cache(cache: dict):
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2))


def invalidate_cache():
    try:
        CACHE_PATH.unlink()
    except FileNotFoundError:
        pass


# ---------------------------------------------------------------------------
# Raw API
# ---------------------------------------------------------------------------

def _request(op: str, **params):
    key = os.environ.get("LEGISCAN_API_KEY")
    if not key:
        raise LegiScanError("LEGISCAN_API_KEY not set in environment")
    params = {"key": key, "op": op, **params}
    r = requests.get(API_BASE, params=params, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    data = r.json()
    if data.get("status") != "OK":
        raise LegiScanError(f"{op} failed: {data.get('alert', data)}")
    return data


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def get_active_hi_session_id() -> int:
    """Return the session_id of the current HI session (sine_die==0; if multiple,
    return the one whose year_start..year_end contains today; else the latest)."""
    data = _request("getSessionList", state="HI")
    sessions = data.get("sessions", [])
    if not sessions:
        raise LegiScanError("no HI sessions returned")
    today = date.today()
    today_year = today.year

    # Prefer active (sine_die == 0) sessions whose year range includes today.
    def in_range(s):
        ys, ye = s.get("year_start"), s.get("year_end")
        return ys is not None and ye is not None and ys <= today_year <= ye

    candidates = [s for s in sessions if s.get("sine_die") == 0 and in_range(s)]
    if not candidates:
        candidates = [s for s in sessions if in_range(s)]
    if not candidates:
        candidates = sorted(sessions, key=lambda s: s.get("year_start", 0), reverse=True)
    return int(candidates[0]["session_id"])


def get_master_list(session_id: int) -> dict[str, dict]:
    """Return {bill_number_upper: {bill_id, number, change_hash, title, ...}}."""
    data = _request("getMasterListRaw", id=session_id)
    raw = data.get("masterlist", {})
    out = {}
    for k, v in raw.items():
        if k == "session":
            continue
        num = (v.get("number") or "").upper().replace(" ", "")
        if num:
            out[num] = v
    return out


def get_bill(bill_id: int, *, change_hash: str | None = None, cache: dict | None = None) -> dict:
    """Return the full bill payload. Skips the network call if change_hash matches the cached one."""
    cache = cache if cache is not None else _load_cache()
    key = str(bill_id)
    cached = cache.get(key)
    if cached and change_hash and cached.get("change_hash") == change_hash:
        return cached["payload"]
    data = _request("getBill", id=bill_id)
    payload = data.get("bill", {})
    cache[key] = {
        "change_hash": change_hash or payload.get("change_hash"),
        "payload": payload,
        "cached_at": int(time.time()),
    }
    _save_cache(cache)
    return payload


def upcoming_hearings(bill: dict, *, window_days: int = 7) -> list[dict]:
    """Return calendar entries that are hearings in the next `window_days` days."""
    today = date.today()
    out = []
    for entry in bill.get("calendar", []) or []:
        type_label = (entry.get("type") or "").lower()
        if "hearing" not in type_label:
            continue
        try:
            d = date.fromisoformat(entry["date"])
        except Exception:
            continue
        delta = (d - today).days
        if 0 <= delta <= window_days:
            out.append(entry)
    return out
