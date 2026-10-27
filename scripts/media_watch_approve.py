#!/usr/bin/env python3
"""Approve a media-watch digest for Slack by replying to its email.

media-watch.yml opens a GitHub issue with each digest and does NOT post to Slack.
Replying "post" to the notification email (or commenting on the issue) comments
on that issue as the replier; media-watch-approve.yml runs this script on the
comment and, when it is an approval from the allowed person, posts the stories
to #communications.

    post          every story in the digest
    post 2 3      only stories 2 and 3 (numbered in the order the digest lists them)

Only the first line of the reply counts, so a quoted email below it is ignored.
A story already posted (recorded by a hidden marker in the workflow's own reply)
is not posted twice.

Usage: media_watch_approve.py --issue-body F --comment-body F --posted F --out SLACK_JSON
  --posted is a file with one JSON string per line: the bodies of earlier bot comments.
Prints one JSON line: {"posted": [numbers just sent], "reply": "text for the issue comment"}.
Writes --out only when there is something to post.
"""
import argparse
import json
import re
import sys

MARKER = re.compile(r"<!-- posted:([\d,]*) -->")
ITEM = re.compile(r"^- \[(.+?)\]\((https?://\S+?)\)\s+—\s+(.*?)\s*$")


def parse_command(comment):
    """None (not an approval), "all", or a sorted list of story numbers."""
    first = next((l.strip() for l in (comment or "").splitlines() if l.strip()), "")
    m = re.match(r"(?i)^post\b[\s:]*([\d\s,]*)$", first)
    if not m:
        return None
    nums = sorted({int(n) for n in re.findall(r"\d+", m.group(1))})
    return nums or "all"


def digest_items(issue_body):
    """[(title, url, tail)] in the order the digest lists them."""
    out = []
    for line in (issue_body or "").splitlines():
        m = ITEM.match(line)
        if m:
            out.append(m.groups())
    return out


def already_posted(bodies):
    done = set()
    for b in bodies:
        for m in MARKER.finditer(b or ""):
            done |= {int(n) for n in m.group(1).split(",") if n}
    return done


def slack_escape(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build(issue_body, comment, posted_bodies):
    """(payload or None, numbers posted now, reply text)."""
    cmd = parse_command(comment)
    if cmd is None:
        return None, [], ""
    items = digest_items(issue_body)
    if not items:
        return None, [], "I could not find any stories in this issue, so nothing was posted."
    want = list(range(1, len(items) + 1)) if cmd == "all" else cmd
    bad = [n for n in want if not 1 <= n <= len(items)]
    if bad:
        return None, [], f"There is no story {', '.join(map(str, bad))}; this digest has {len(items)}. Nothing was posted."
    done = already_posted(posted_bodies)
    fresh = [n for n in want if n not in done]
    if not fresh:
        return None, [], "Those stories were already posted to Slack."
    rows = [f"• <{items[n - 1][1]}|{slack_escape(items[n - 1][0])}> — {slack_escape(items[n - 1][2])}" for n in fresh]
    head = f":newspaper: *{len(fresh)} new media mention{'s' if len(fresh) != 1 else ''}* not on In the News yet"
    return {"text": head + "\n" + "\n".join(rows)}, fresh, ""


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--issue-body", required=True)
    ap.add_argument("--comment-body", required=True)
    ap.add_argument("--posted", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    def read(path):
        with open(path, encoding="utf-8") as f:
            return f.read()
    posted = [json.loads(l) for l in read(a.posted).splitlines() if l.strip()]
    payload, nums, reply = build(read(a.issue_body), read(a.comment_body), posted)
    if payload:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
    print(json.dumps({"posted": nums, "reply": reply}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
