#!/usr/bin/env python3
"""Email an approved media-watch post (the slack.json payload) to staff.

Usage: media_watch_email.py SLACK_JSON
Env: MAIL_TO (comma-separated), MAIL_USER, MAIL_PASS (a Gmail app password).
Sends through Gmail SMTP. Run only after Devin has approved the stories.
"""
import html
import json
import os
import re
import smtplib
import sys
from email.message import EmailMessage


def to_plain(slack_text):
    """Slack mrkdwn -> plain text: <url|title> becomes 'title' + url on the next line."""
    def link(m):
        return f"{html.unescape(m.group(2))}\n    {m.group(1)}"
    text = re.sub(r"<(https?://[^|>]+)\|([^>]*)>", link, slack_text)
    text = html.unescape(text).replace("*", "").replace(":newspaper: ", "")
    return text.replace("• ", "\n• ")


def build_message(slack_text, sender, to):
    first = slack_text.splitlines()[0]
    subject = "Hawaiʻi Appleseed in the news — " + to_plain(first).strip()
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, sender, to
    msg.set_content(to_plain(slack_text).strip() + "\n\nTo post one, add it to the Squarespace /in-the-news collection.\n")
    return msg


def main():
    text = json.load(open(sys.argv[1], encoding="utf-8"))["text"]
    msg = build_message(text, os.environ["MAIL_USER"], os.environ["MAIL_TO"])
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
        smtp.login(os.environ["MAIL_USER"], os.environ["MAIL_PASS"])
        smtp.send_message(msg)
    print("emailed staff")


if __name__ == "__main__":
    main()
