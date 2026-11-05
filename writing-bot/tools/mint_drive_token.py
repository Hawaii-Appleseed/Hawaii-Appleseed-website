#!/usr/bin/env python3
"""Make the read-only Drive credential refresh-testimony.yml uses, and print it for `gh secret set`.

    python writing-bot/tools/mint_drive_token.py | gh secret set GOOGLE_DRIVE_TOKEN --repo Hawaii-Appleseed/Hawaii-Appleseed-website

A browser opens on Google's consent page for the appleseed-drive-pipeline OAuth client (an Internal app in the
hiappleseed.org Workspace): sign in as someone who can see the testimony folders in the shared Drive and allow
"See and download all your Google Drive files". Read-only on purpose: the workflow only lists and downloads, and
a secret in a public repository's Actions should not be able to change anything in Drive.

The credential is printed to stdout only, for the pipe; nothing is written to disk. Revoke it at
myaccount.google.com -> Security -> Third-party access, and mint a new one the same way.

Needs google-auth-oauthlib, and the client JSON (Desktop client "laptop CLI - dtomkatsu" in the
appleseed-drive-pipeline project) at --client-secret.
"""
import argparse
import json
import sys
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--client-secret", type=Path,
                    default=Path.home() / ".config" / "appleseed-drive" / "client_secret.json")
    args = ap.parse_args()
    if sys.stdout.isatty():
        raise SystemExit("Pipe this into `gh secret set GOOGLE_DRIVE_TOKEN`; it will not print a credential to a terminal.")
    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_secrets_file(str(args.client_secret), SCOPES)
    print("Approve read-only Drive access in the browser window that opens.", file=sys.stderr)
    # The library prints its prompt to stdout, which is the secret's pipe: keep it quiet.
    creds = flow.run_local_server(port=0, prompt="consent", open_browser=True, authorization_prompt_message="",
                                  success_message="Done. You can close this tab.")
    if not creds.refresh_token:
        raise SystemExit("Google returned no refresh token; revoke the app's access and try again.")
    sys.stdout.write(json.dumps({
        "type": "authorized_user", "client_id": creds.client_id, "client_secret": creds.client_secret,
        "refresh_token": creds.refresh_token, "token_uri": creds.token_uri, "scopes": SCOPES,
    }))
    print("read-only Drive credential made", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
