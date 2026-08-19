"""A tiny in-process job queue.

monday times out custom-action requests, so the Run URL must return 200 immediately and
do the real work (API fetch, render, PDF conversion, upload) in the background.

This is deliberately the simplest thing that works: a thread pool and a dict. It loses
jobs on restart and does not span replicas — swap in a real queue (or monday code's
storage API for job state) before this handles anything you care about losing.
"""

from __future__ import annotations

import datetime as dt
import threading
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor

_MAX_JOBS = 500

_lock = threading.Lock()
_jobs: dict[str, dict] = {}
_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="docugen")


def _now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def submit(kind: str, fn, *args, **kwargs) -> str:
    job_id = uuid.uuid4().hex[:12]
    with _lock:
        _jobs[job_id] = {"id": job_id, "kind": kind, "status": "queued",
                         "created_at": _now(), "result": None, "error": None}
        if len(_jobs) > _MAX_JOBS:  # drop the oldest, keep memory bounded
            for stale in sorted(_jobs, key=lambda k: _jobs[k]["created_at"])[:50]:
                _jobs.pop(stale, None)
    _pool.submit(_run, job_id, fn, args, kwargs)
    return job_id


def _run(job_id: str, fn, args, kwargs) -> None:
    _update(job_id, status="running", started_at=_now())
    try:
        result = fn(*args, **kwargs)
        _update(job_id, status="done", result=result, finished_at=_now())
    except Exception as exc:  # noqa: BLE001 — a failed job must not kill the worker
        _update(job_id, status="error", error=f"{type(exc).__name__}: {exc}",
                traceback=traceback.format_exc(), finished_at=_now())


def _update(job_id: str, **fields) -> None:
    with _lock:
        if job_id in _jobs:
            _jobs[job_id].update(fields)


def get(job_id: str) -> dict | None:
    with _lock:
        job = _jobs.get(job_id)
        return dict(job) if job else None


def recent(limit: int = 20) -> list[dict]:
    with _lock:
        return sorted((dict(j) for j in _jobs.values()),
                      key=lambda j: j["created_at"], reverse=True)[:limit]


def wait_for_idle(timeout: float = 60.0) -> None:
    """Test helper: block until queued/running jobs settle."""
    import time
    deadline = time.time() + timeout
    while time.time() < deadline:
        with _lock:
            busy = any(j["status"] in ("queued", "running") for j in _jobs.values())
        if not busy:
            return
        time.sleep(0.05)
    raise TimeoutError("jobs did not finish in time")
