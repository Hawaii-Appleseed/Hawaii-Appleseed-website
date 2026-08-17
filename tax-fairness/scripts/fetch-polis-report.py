#!/usr/bin/env python3
"""polis-fetch — pull a Pol.is conversation's full vote data as one JSON file.

A pol.is /report/<report_id> page carries no data itself: it's a client-side
bundle that calls four public, unauthenticated GET endpoints and renders the
response. Reverse-engineered from network traffic against
https://pol.is/report/r3v45armukntdykxcyucd (Tax Fairness Coalition's 2027
priorities poll) — verified with plain `curl`, no session or cookies needed:

  reports        report_id -> conversation_id (+ any custom axis/group labels)
  conversations  topic, description, participant_count, created
  comments       every submitted idea, with its own agree/disagree/pass tally
  math/pca2      the opinion-group clustering: which participants cluster
                 together, each group's most-representative comments
                 (repness — what pol.is's own report page uses to write "this
                 group agreed on X"), and each group's agree/disagree/seen
                 counts on every idea (group-votes)

Usage:
  python3 fetch-polis-report.py <report-id-or-url-or-conversation-id> [-o FILE]

  python3 fetch-polis-report.py r3v45armukntdykxcyucd
  python3 fetch-polis-report.py https://pol.is/report/r3v45armukntdykxcyucd -o tfc.json
  python3 fetch-polis-report.py 7bvwfhpf8x --conversation -o tfc.json

The input is a report id/URL by default (what pol.is calls "Share this
report" — a `pol.is/report/<id>` link). Pass --conversation if you only have
the bare conversation id (the `pol.is/<id>` link participants voted at
instead) — group data still works, since group-votes/repness are computed
per conversation, but you lose the report row's own metadata (custom axis
labels, if the report author set any).

What this does NOT give you: how many people were INVITED to vote.
participant_count is voters, not the coalition's full mailing list — pol.is
has no idea how many people got the link. That number, and any editorial
read of the results (which ideas are "settled" vs "liked but not understood",
which family an idea belongs to, the prose gloss under each one) stays a
human step. This script's job stops at getting the numbers right — worth
having as its own step, since re-deriving them by hand is exactly how the
Tax Fairness Coalition report first went to print citing 102 votes cast when
the comments actually sum to 101.
"""
import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

API = "https://pol.is/api/v3"
UA = "polis-fetch/1.0 (+https://github.com/Hawaii-Appleseed)"


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{url} -> HTTP {e.code}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"{url} -> {e.reason}") from e


def extract_id(s):
    m = re.search(r"pol\.is/(?:report/)?([a-zA-Z0-9]+)", s)
    return m.group(1) if m else s.strip()


def fetch(id_or_url, is_conversation_id=False):
    raw_id = extract_id(id_or_url)
    report_id = None
    conversation_id = None
    report_meta = None

    if is_conversation_id:
        conversation_id = raw_id
    else:
        reports = get_json(f"{API}/reports?report_id={urllib.parse.quote(raw_id)}")
        if not reports:
            raise RuntimeError(
                f"no report found for '{raw_id}' — if this is a bare "
                "conversation id (a pol.is/<id> voting link, not a "
                "pol.is/report/<id> link), pass --conversation"
            )
        report_meta = reports[0]
        report_id = report_meta["report_id"]
        conversation_id = report_meta["conversation_id"]

    conv = get_json(f"{API}/conversations?conversation_id={conversation_id}")
    comments_url = (
        f"{API}/comments?conversation_id={conversation_id}"
        + (f"&report_id={report_id}" if report_id else "")
        + "&moderation=true&mod_gt=-2&include_voting_patterns=true"
    )
    comments = get_json(comments_url)
    pca = get_json(f"{API}/math/pca2?lastVoteTimestamp=0&conversation_id={conversation_id}")

    ideas = [
        {
            "tid": c["tid"],
            "text": c["txt"],
            "agree": c["agree_count"],
            "disagree": c["disagree_count"],
            "pass": c["pass_count"],
            "votes": c["count"],
            "is_seed": c["is_seed"],
            "author_pid": c["pid"],
        }
        for c in sorted(comments, key=lambda c: c["tid"])
    ]
    authors = sorted({c["pid"] for c in comments})
    votes_cast = sum(c["count"] for c in comments)
    agree = sum(c["agree_count"] for c in comments)
    disagree = sum(c["disagree_count"] for c in comments)
    passed = sum(c["pass_count"] for c in comments)

    repness = pca.get("repness", {})
    group_votes = pca.get("group-votes", {})
    groups = []
    for gc in pca.get("group-clusters", []):
        gid = str(gc["id"])
        votes_by_idea = {
            int(tid): {"agree": v["A"], "disagree": v["D"], "seen": v["S"],
                       "pass": v["S"] - v["A"] - v["D"]}
            for tid, v in group_votes.get(gid, {}).get("votes", {}).items()
        }
        groups.append({
            "id": gc["id"],
            "size": len(gc["members"]),
            "member_ids": gc["members"],
            "representative_comments": repness.get(gid, []),
            "votes_by_idea": votes_by_idea,
        })

    labels = None
    if report_meta:
        label_fields = {k: v for k, v in report_meta.items()
                         if k.startswith("label_") and v is not None}
        if label_fields:
            labels = label_fields

    return {
        "source": f"https://pol.is/report/{report_id}" if report_id
                   else f"https://pol.is/{conversation_id}",
        "report_id": report_id,
        "conversation_id": conversation_id,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "topic": conv.get("topic"),
        "description": conv.get("description"),
        "participant_count": conv.get("participant_count"),
        "conversation_created": conv.get("created"),
        "labels": labels,
        "stats": {
            "ideas": len(ideas),
            "authors": len(authors),
            "votes_cast": votes_cast,
            "agree": agree,
            "disagree": disagree,
            "pass": passed,
        },
        "ideas": ideas,
        "groups": groups,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("id_or_url", help="report id, report URL, or (with --conversation) a conversation id")
    p.add_argument("--conversation", action="store_true",
                    help="id_or_url is a bare conversation id, not a report id")
    p.add_argument("-o", "--out", help="write JSON here instead of stdout")
    p.add_argument("--pretty", action="store_true", default=True,
                    help="pretty-print (default)")
    p.add_argument("--compact", dest="pretty", action="store_false",
                    help="single-line JSON")
    args = p.parse_args()

    try:
        data = fetch(args.id_or_url, is_conversation_id=args.conversation)
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)

    text = json.dumps(data, indent=2 if args.pretty else None, ensure_ascii=False)
    if args.out:
        with open(args.out, "w") as f:
            f.write(text + "\n")
        print(f"wrote {args.out} "
              f"({data['stats']['ideas']} ideas, {data['stats']['votes_cast']} votes, "
              f"{len(data['groups'])} groups)", file=sys.stderr)
    else:
        print(text)


if __name__ == "__main__":
    main()
