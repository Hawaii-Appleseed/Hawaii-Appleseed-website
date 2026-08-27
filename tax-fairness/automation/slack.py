#!/usr/bin/env python3
"""Slack helper for the tax-fairness-notes skill.

Reads and posts to the coalition's Slack channel using Devin's existing xoxp
user token (the same one ~/.openclaw/workspace/scripts/slack-automation.sh uses).

Token lookup order:
  1. $SLACK_USER_TOKEN in the environment
  2. SLACK_USER_TOKEN=... in ~/.openclaw/secrets.env   (madison's canonical location)
  3. bare token in ~/.slack_user_token                 (laptop-local fallback)

Subcommands:
  whoami                      verify the token and show the authed user/team
  find-channel [name]         resolve a channel name to an id (default: tax-fairness)
  read [--channel N] [--limit N] [--since TS]
                              print recent messages as JSON
  post --text "..." [--channel N]
                              post a message  -- REQUIRES --i-have-approval
"""
import argparse
import json
import os
import sys
import urllib.parse
import urllib.request

API = "https://slack.com/api/"
DEFAULT_CHANNEL = "tax-fairness"
DEVIN_USER_ID = "UV95RTFC5"


def load_token():
    tok = os.environ.get("SLACK_USER_TOKEN", "").strip()
    if tok:
        return tok, "$SLACK_USER_TOKEN"

    secrets = os.path.expanduser("~/.openclaw/secrets.env")
    if os.path.exists(secrets):
        for line in open(secrets, encoding="utf8", errors="ignore"):
            line = line.strip()
            if line.startswith("SLACK_USER_TOKEN="):
                v = line.split("=", 1)[1].strip().strip('"').strip("'")
                if v:
                    return v, secrets

    fallback = os.path.expanduser("~/.slack_user_token")
    if os.path.exists(fallback):
        v = open(fallback, encoding="utf8").read().strip()
        if v:
            return v, fallback

    sys.exit(
        "No Slack token found.\n"
        "Looked in: $SLACK_USER_TOKEN, ~/.openclaw/secrets.env, ~/.slack_user_token\n"
        "The canonical copy lives on madison, which is currently offline.\n"
        "Grab the token from https://api.slack.com/apps (OAuth & Permissions ->\n"
        "User OAuth Token, starts with xoxp-) and write it to ~/.slack_user_token."
    )


def call(method, params=None, post=False, soft=False):
    token, _ = load_token()
    params = params or {}
    headers = {"Authorization": f"Bearer {token}"}
    if post:
        data = json.dumps(params).encode()
        headers["Content-Type"] = "application/json; charset=utf-8"
        req = urllib.request.Request(API + method, data=data, headers=headers)
    else:
        url = API + method + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        out = json.loads(r.read().decode())
    if not out.get("ok") and soft:
        return out
    if not out.get("ok"):
        err = out.get("error", "unknown")
        hint = ""
        if err == "missing_scope":
            hint = f"  (needed scope: {out.get('needed')})"
        elif err in ("invalid_auth", "token_revoked", "account_inactive"):
            hint = "  (token is dead -- regenerate at https://api.slack.com/apps)"
        elif err == "not_in_channel":
            hint = "  (the token's user must be a member of the channel)"
        sys.exit(f"Slack API error on {method}: {err}{hint}")
    return out


def find_channel(name):
    """Resolve a channel name to its id, paging through public + private."""
    name = name.lstrip("#")
    cursor = ""
    scanned = 0
    types = "public_channel,private_channel"
    degraded = False
    while True:
        params = {"types": types, "limit": 200, "exclude_archived": "true"}
        if cursor:
            params["cursor"] = cursor
        out = call("conversations.list", params, soft=True)
        if not out.get("ok"):
            # The bot token may lack groups:read; retry public-only, as
            # openclaw's slack-automation.sh does.
            if out.get("error") == "missing_scope" and not degraded:
                types, degraded = "public_channel", True
                print("note: no groups:read -- private channels not searched",
                      file=sys.stderr)
                continue
            sys.exit(f"Slack API error on conversations.list: {out.get('error')}")
        for c in out.get("channels", []):
            scanned += 1
            if c.get("name") == name:
                return c
        cursor = out.get("response_metadata", {}).get("next_cursor", "")
        if not cursor:
            break
    extra = ""
    if degraded:
        extra = ("\nPrivate channels were NOT searched (token lacks groups:read).\n"
                 "If #%s is private, add groups:read + groups:history at\n"
                 "https://api.slack.com/apps and reinstall the app." % name)
    sys.exit(
        f"Channel #{name} not found among {scanned} channels visible to this token."
        + extra +
        "\nIf it is a Slack Connect channel shared from another workspace, this token\n"
        "may not see it -- check which workspace owns it."
    )


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("whoami")

    p_find = sub.add_parser("find-channel")
    p_find.add_argument("name", nargs="?", default=DEFAULT_CHANNEL)

    p_read = sub.add_parser("read")
    p_read.add_argument("--channel", default=DEFAULT_CHANNEL)
    p_read.add_argument("--limit", type=int, default=30)
    p_read.add_argument("--since", default="0", help="oldest ts, e.g. 1756300000")

    p_prev = sub.add_parser(
        "preview", help="Show the post to Devin only, via an ephemeral message. "
                        "Nothing is saved to channel history and no one else sees it.")
    p_prev.add_argument("--channel", default=DEFAULT_CHANNEL)
    p_prev.add_argument("--text", required=True)
    p_prev.add_argument("--user", default=DEVIN_USER_ID)

    p_post = sub.add_parser("post")
    p_post.add_argument("--channel", default=DEFAULT_CHANNEL)
    p_post.add_argument("--text", required=True)
    p_post.add_argument(
        "--i-have-approval",
        action="store_true",
        help="Required. Devin must approve the exact text in chat first.",
    )

    a = ap.parse_args()

    if a.cmd == "whoami":
        _, src = load_token()
        out = call("auth.test")
        print(json.dumps({
            "token_source": src,
            "user": out.get("user"),
            "user_id": out.get("user_id"),
            "team": out.get("team"),
            "team_id": out.get("team_id"),
        }, indent=2))

    elif a.cmd == "find-channel":
        c = find_channel(a.name)
        print(json.dumps({
            "id": c["id"],
            "name": c["name"],
            "is_private": c.get("is_private"),
            "is_member": c.get("is_member"),
            "is_shared": c.get("is_shared"),
            "num_members": c.get("num_members"),
        }, indent=2))

    elif a.cmd == "read":
        c = find_channel(a.channel)
        out = call("conversations.history", {
            "channel": c["id"], "limit": a.limit, "oldest": a.since,
        })
        # resolve user ids -> display names, cached per run
        names = {}
        msgs = []
        for m in out.get("messages", []):
            uid = m.get("user", "")
            if uid and uid not in names:
                try:
                    u = call("users.info", {"user": uid})
                    prof = u.get("user", {})
                    names[uid] = prof.get("real_name") or prof.get("name") or uid
                except SystemExit:
                    names[uid] = uid
            msgs.append({
                "ts": m.get("ts"),
                "user": names.get(uid, uid),
                "text": m.get("text", ""),
            })
        print(json.dumps({"channel": c["name"], "messages": msgs}, indent=2))

    elif a.cmd == "preview":
        c = find_channel(a.channel)
        out = call("chat.postEphemeral",
                   {"channel": c["id"], "user": a.user, "text": a.text}, post=True)
        print(json.dumps({
            "ok": True,
            "channel": c["name"],
            "visible_to_only": a.user,
            "saved_to_history": False,
            "ts": out.get("message_ts"),
        }, indent=2))

    elif a.cmd == "post":
        if not a.i_have_approval:
            sys.exit(
                "Refusing to post without --i-have-approval.\n"
                "Devin must approve the exact message text in chat first."
            )
        c = find_channel(a.channel)
        out = call("chat.postMessage",
                   {"channel": c["id"], "text": a.text}, post=True)
        print(json.dumps({"ok": True, "channel": c["name"], "ts": out.get("ts")}, indent=2))


if __name__ == "__main__":
    main()
