#!/usr/bin/env python3
"""Turn a failed Actions run into a readable triage packet.

Why: every workflow failure here has followed the same manual path — an email
or a red X, then a session opened just to paste the symptom in and ask what
broke. The first hop is mechanical. This runs on the failure itself and puts
the diagnosis in the notification, so the alert already answers "why".

Deliberately deterministic: no model, no credentials, always runs. A narrated
summary is layered on top by the workflow only when CLAUDE_CODE_OAUTH_TOKEN is
configured, exactly as the Council on Revenues monitor does.

Reads `gh run view --log-failed` text on stdin.

Usage:
  gh run view <id> --log-failed | triage_failure.py --workflow NAME --url URL \
      [--commit SHA] [--branch REF] [--event EVENT] [-o packet.md]
"""

import argparse
import re
import sys
from collections import OrderedDict

# gh prefixes every log line with "<job>\t<step>\t<timestamp> ".
LINE_RE = re.compile(r"^(?P<job>[^\t]*)\t(?P<step>[^\t]*)\t(?P<rest>.*)$")
TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T[\d:.]+Z\s?")
ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]|\[\d+(;\d+)*m")
# Actions echoes the whole step script back inside a ##[group]; that is the
# code we already have in the repo, not evidence about the failure.
ECHO_RE = re.compile(r"^(##\[(group|endgroup)\]|shell: |env:|\s*$)")


def clean(line):
    return ANSI_RE.sub("", line).replace("\ufeff", "").rstrip()

# Ordered by how strongly each signals the actual cause.
SIGNALS = [
    (re.compile(r"^##\[error\]", re.I), 100),
    (re.compile(r"\bTraceback \(most recent call last\)", re.I), 95),
    (re.compile(r"^\s*(\w*Error|Exception)\b.*:", re.I), 90),
    (re.compile(r"\b(fatal|FAILED|failure):", re.I), 80),
    (re.compile(r"\b(command not found|No such file or directory|Permission denied)\b"), 80),
    (re.compile(r"\bHTTP (4\d\d|5\d\d)\b"), 75),
    (re.compile(r"\b(npm ERR!|pip .*error|ModuleNotFoundError)\b", re.I), 75),
    (re.compile(r"\b(timed? ?out|ETIMEDOUT|ECONNRESET|ENOTFOUND)\b", re.I), 70),
    (re.compile(r"\b(rate limit|429|403 Forbidden|401 Unauthorized)\b", re.I), 70),
    (re.compile(r"\berror\b", re.I), 40),
]


# Needles that must not match inside a longer token. Each of these shipped as a
# bare substring and mislabelled real failures:
#
#   "429"       matched the RAW gh output, where every line still carries its
#               "<job>\t<step>\t<timestamp>" prefix and a timestamp's fractional
#               seconds supply the digits (2026-09-18T02:35:00.4295703Z). Every
#               line has a timestamp, so "Looks like rate limiting." could head
#               almost any failure — it headed the first site-drift one.
#   "enotfound" matches inside "ModulENOTFOUNDError", and the timeout family is
#               checked first, so every ModuleNotFoundError read as a DNS
#               failure rather than a missing dependency.
#   "rejected"  matches the word anywhere, not just a push rejection.
#
# classify() also reads the cleaned body text now, never `raw`.
RATE_LIMIT_RE = re.compile(
    r"rate limit|secondary rate|too many requests"
    r"|(?:http|https|error|status|code)\D{0,10}\b429\b", re.I)
TIMEOUT_RE = re.compile(
    r"\b(?:etimedout|econnreset|enotfound|timed out|timeout"
    r"|connection refused)\b", re.I)
PUSH_RACE_RE = re.compile(
    r"non-fast-forward|updates were rejected|fetch first|!\s*\[rejected\]", re.I)


def classify(text):
    """A one-line best guess at the failure family, for the alert title.

    Pass the CLEANED log text (timestamps and job/step prefixes stripped), not
    raw gh output — see RATE_LIMIT_RE."""
    t = text.lower()
    checks = [
        ("authentication or permissions", ("401 unauthorized", "403 forbidden",
                                           "permission denied", "bad credentials",
                                           "not logged in", "authentication failed")),
        ("rate limiting", RATE_LIMIT_RE),
        ("an upstream server error (5xx)", ("http error 5", "500 internal",
                                            "502 bad gateway", "503 service",
                                            "504 gateway")),
        # Checked before the timeout family: "ModuleNotFoundError" is a missing
        # dependency, and used to be read as one only by accident of ordering.
        ("a missing dependency or binary", ("command not found", "modulenotfounderror",
                                            "no module named", "cannot find module")),
        ("network or upstream timeout", TIMEOUT_RE),
        ("a git push race", PUSH_RACE_RE),
        ("upstream markup or schema change", ("keyerror", "indexerror", "nonetype",
                                              "parsed nothing", "no such element")),
        ("a failing test", ("assertionerror", "tests failed", "failed tests",
                            "pytest", "test suite")),
    ]
    for label, needles in checks:
        if hasattr(needles, "search"):
            if needles.search(t):
                return label
        elif any(n in t for n in needles):
            return label
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workflow", default="(unknown workflow)")
    ap.add_argument("--url", default="")
    ap.add_argument("--commit", default="")
    ap.add_argument("--branch", default="")
    ap.add_argument("--event", default="")
    ap.add_argument("--max-lines", type=int, default=45)
    ap.add_argument("-o", "--output")
    a = ap.parse_args()

    raw = sys.stdin.read()

    # Group lines by (job, step), preserving order.
    steps = OrderedDict()
    bodies = []
    for line in raw.splitlines():
        m = LINE_RE.match(line)
        if m:
            key = (m.group("job").strip(), m.group("step").strip())
            body = clean(TS_RE.sub("", m.group("rest")))
        else:
            key = ("", "")
            body = clean(line)
        steps.setdefault(key, []).append(body)
        bodies.append(body)
    # What the failure actually said, with the job/step/timestamp prefixes gone.
    # classify() reads this, never `raw` — see RATE_LIMIT_RE.
    cleaned = "\n".join(bodies)

    # Score every line; the highest-scoring ones are the likely cause.
    scored = []
    for (job, step), lines in steps.items():
        for i, ln in enumerate(lines):
            s = ln.strip()
            if not s:
                continue
            for rx, weight in SIGNALS:
                if rx.search(s):
                    scored.append((weight, job, step, i, s))
                    break
    scored.sort(key=lambda t: (-t[0], t[3]))

    out = [f"## Failure: {a.workflow}", ""]
    guess = classify(cleaned)
    if guess:
        out.append(f"**Looks like {guess}.**")
        out.append("")

    meta = []
    if a.url:
        meta.append(f"- Run: {a.url}")
    if a.branch:
        meta.append(f"- Branch: `{a.branch}`")
    if a.event:
        meta.append(f"- Triggered by: `{a.event}`")
    if a.commit:
        meta.append(f"- Commit: `{a.commit[:12]}`")
    # gh reports "UNKNOWN STEP" when it cannot map a log section back to a
    # step (older runs, or a job that died before the step was registered).
    # Listing it adds nothing, so show just the job in that case.
    failed_steps = []
    for j, st in steps:
        if not (j or st):
            continue
        failed_steps.append(f"`{j}` / `{st}`" if st and st != "UNKNOWN STEP"
                            else f"`{j}`")
    if failed_steps:
        meta.append("- Failed step(s): " + ", ".join(dict.fromkeys(failed_steps)))
    if meta:
        out += meta + [""]

    if scored:
        out += ["### Most likely cause", "", "```"]
        seen = set()
        for _, job, step, _, s in scored:
            if s in seen:
                continue
            seen.add(s)
            out.append(s[:300])
            if len(seen) >= 12:
                break
        out += ["```", ""]

    # Tail of the failing step: the lines immediately before the failure are
    # usually what the error refers to.
    if steps:
        (job, step), lines = list(steps.items())[-1]
        body_lines = [l for l in lines if l.strip() and not ECHO_RE.match(l)]
        # Everything up to the group header is the echoed step script; the
        # interesting output starts after it.
        tail = body_lines[-a.max_lines:]
        if tail:
            label = f"{job} / {step}".strip(" /") or "log"
            out += [f"### Tail of `{label}`", "", "```"]
            out += [l[:300] for l in tail]
            out += ["```", ""]

    if not scored and not steps:
        out += ["_No failed-step log was returned. The run may have been "
                "cancelled, or the job died before producing output._", ""]

    text = "\n".join(out)
    if a.output:
        with open(a.output, "w") as fh:
            fh.write(text)
        print(a.output)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
