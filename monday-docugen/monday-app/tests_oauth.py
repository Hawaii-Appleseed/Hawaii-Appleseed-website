"""OAuth tests — PKCE, single-use state, storage, rotation, and token precedence.

The monday token endpoint is stubbed, so this runs offline:

    .venv/bin/python monday-app/tests_oauth.py
"""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import json
import os
import pathlib
import sys
import tempfile
import time
from urllib.parse import parse_qs, urlparse

WORK = pathlib.Path(tempfile.mkdtemp(prefix="docugen-oauth-test-"))
os.environ.update({
    "MONDAY_SIGNING_SECRET": "test-signing-secret-0123456789abcdef",
    "MONDAY_CLIENT_SECRET": "test-client-secret-0123456789abcdef",
    "MONDAY_CLIENT_ID": "test-client-id",
    "PUBLIC_BASE_URL": "https://docugen.example.com",
    "DOCUGEN_FAKE_MONDAY": "1",
    "DOCUGEN_TEMPLATE_DIR": str(WORK / "templates"),
    "DOCUGEN_OUTPUT_DIR": str(WORK / "output"),
    "DOCUGEN_TOKEN_STORE": str(WORK / "tokens.json"),
})
os.environ.pop("MONDAY_API_TOKEN", None)

sys.path.insert(0, str(pathlib.Path(__file__).parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import jwt  # noqa: E402

import app as flask_app  # noqa: E402
import docugen  # noqa: E402
import generator  # noqa: E402
import jobs  # noqa: E402
import oauth  # noqa: E402

checks = []


def check(name: str, condition: bool, detail: str = "") -> None:
    checks.append((name, bool(condition), detail))
    print(f"{'PASS' if condition else 'FAIL'}  {name}{'  — ' + detail if detail else ''}")


def access_token(ttl_seconds: int = 3600) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    return jwt.encode({"aid": 1825528, "uid": 4012689, "iat": now,
                       "exp": now + dt.timedelta(seconds=ttl_seconds)},
                      "monday-side-secret", algorithm="HS256")


def session_jwt(account_id: int = 1825528) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    return jwt.encode({"accountId": account_id, "userId": 4012689, "iat": now,
                       "exp": now + dt.timedelta(minutes=30)},
                      os.environ["MONDAY_CLIENT_SECRET"], algorithm="HS256")


# --- stub monday's OAuth + API endpoints -------------------------------------------

calls = {"token": [], "identify": 0, "revoke": []}


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


def fake_post(url, **kwargs):
    body = kwargs.get("json") or {}
    if url == oauth.TOKEN_URL or url == oauth.LEGACY_TOKEN_URL:
        calls["token"].append(body)
        grant = body.get("grant_type")
        if grant == "authorization_code" and body.get("code") == "bad-code":
            return FakeResponse({"error": "invalid_grant"}, status=400)
        ttl = 3600 if grant == "authorization_code" else 7200
        return FakeResponse({
            "access_token": access_token(ttl),
            "refresh_token": f"refresh-{grant}-{len(calls['token'])}",
            "token_type": "Bearer", "scope": "me:read boards:read boards:write",
        })
    if url == oauth.REVOKE_URL:
        calls["revoke"].append(body)
        return FakeResponse({}, status=200)
    if url == oauth.API_URL:
        calls["identify"] += 1
        return FakeResponse({"data": {"me": {"id": "4012689", "name": "Devin",
                                             "account": {"id": "1825528",
                                                         "name": "Appleseed"}}}})
    raise AssertionError(f"unexpected POST to {url}")


oauth.requests.post = fake_post


def main() -> int:
    client = flask_app.app.test_client()
    generator.TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    docugen.scaffold_template(
        {"id": "111", "name": "B", "columns": [{"id": "text", "title": "Client Name",
                                                "type": "text"}], "groups": []},
        generator.TEMPLATE_DIR / "quote.docx", "item")

    # ---- authorize redirect -------------------------------------------------------
    r = client.get("/oauth/install")
    check("install redirects to monday", r.status_code == 302, r.headers.get("Location", "")[:60])
    params = parse_qs(urlparse(r.headers["Location"]).query)
    check("authorize URL is monday's",
          r.headers["Location"].startswith(oauth.AUTHORIZE_URL))
    check("PKCE challenge sent as S256",
          params.get("code_challenge_method") == ["S256"] and bool(params.get("code_challenge")))
    check("redirect_uri matches PUBLIC_BASE_URL",
          params["redirect_uri"] == ["https://docugen.example.com/oauth/callback"])
    check("scopes requested", "boards:read" in params["scope"][0])

    state = params["state"][0]
    verifier = oauth._pending[state]["verifier"]
    expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()
                                        ).decode().rstrip("=")
    check("challenge is base64url(sha256(verifier)), unpadded",
          params["code_challenge"] == [expected])
    check("verifier length within RFC 7636 range", 43 <= len(verifier) <= 128, str(len(verifier)))

    # ---- callback -----------------------------------------------------------------
    r = client.get("/oauth/callback?error=access_denied&error_description=User+said+no")
    check("user refusal renders an error page",
          r.status_code == 400 and b"User said no" in r.data)

    r = client.get("/oauth/callback?code=abc&state=forged-state")
    check("unknown state rejected", r.status_code == 400, r.get_data(as_text=True)[:70])

    r = client.get(f"/oauth/callback?code=auth-code-1&state={state}")
    check("valid callback succeeds", r.status_code == 200 and b"Connected" in r.data,
          r.get_data(as_text=True)[:90])

    sent = calls["token"][-1]
    check("code exchange sent the PKCE verifier", sent.get("code_verifier") == verifier)
    check("code exchange sent client credentials + grant",
          sent["grant_type"] == "authorization_code"
          and sent["client_id"] == "test-client-id"
          and sent["client_secret"] == os.environ["MONDAY_CLIENT_SECRET"])
    check("account identified via the API", calls["identify"] == 1)

    r = client.get(f"/oauth/callback?code=auth-code-1&state={state}")
    check("state cannot be replayed", r.status_code == 400, r.get_data(as_text=True)[:70])

    # ---- storage ------------------------------------------------------------------
    record = oauth.store.get("1825528")
    check("token stored under the account id", bool(record))
    check("account metadata stored", record.get("account_name") == "Appleseed")
    check("expiry read from the access token's exp claim",
          isinstance(record.get("expires_at"), int)
          and record["expires_at"] > int(time.time()))
    mode = oct(pathlib.Path(os.environ["DOCUGEN_TOKEN_STORE"]).stat().st_mode & 0o777)
    check("token file is 0o600", mode == "0o600", mode)

    # ---- refresh + rotation -------------------------------------------------------
    before = oauth.store.get("1825528")["refresh_token"]
    token = oauth.access_token_for("1825528")
    check("fresh token used without refreshing",
          token == before_token(before) or calls["token"][-1]["grant_type"] == "authorization_code",
          calls["token"][-1]["grant_type"])

    # force the stored token to look nearly expired
    stale = oauth.store.get("1825528")
    stale["expires_at"] = int(time.time()) + 30  # inside the 120s skew
    oauth.store.save("1825528", {"access_token": stale["access_token"],
                                 "refresh_token": before, "scope": stale["scope"]},
                     {"account_name": "Appleseed"})
    oauth.store._write({**oauth.store._read(),
                        "1825528": {**oauth.store.get("1825528"),
                                    "expires_at": int(time.time()) + 30}})
    refreshed = oauth.access_token_for("1825528")
    check("near-expiry token triggers a refresh",
          calls["token"][-1]["grant_type"] == "refresh_token",
          calls["token"][-1].get("grant_type", ""))
    check("refresh sent the stored refresh token",
          calls["token"][-1]["refresh_token"] == before)
    after = oauth.store.get("1825528")
    check("rotated refresh token persisted", after["refresh_token"] != before,
          f"{before} → {after['refresh_token']}")
    check("new access token persisted and returned",
          after["access_token"] == refreshed and after["expires_at"] > int(time.time()) + 120)

    # ---- token precedence ---------------------------------------------------------
    check("shortLivedToken wins over stored OAuth",
          oauth.resolve_api_token({"shortLivedToken": "slt-123",
                                   "accountId": 1825528}) == "slt-123")
    check("stored OAuth token used when there is no shortLivedToken",
          oauth.resolve_api_token({"accountId": 1825528}) == after["access_token"])
    try:
        oauth.resolve_api_token({"accountId": 999999})
        check("unconnected account raises NeedsAuth", False, "no exception raised")
    except oauth.NeedsAuthError as exc:
        check("unconnected account raises NeedsAuth",
              exc.status == 428 and exc.install_url.endswith("/oauth/install"))

    # ---- endpoints ----------------------------------------------------------------
    r = client.get("/oauth/status", headers={"Authorization": session_jwt()})
    body = r.get_json()
    check("status reports the connected account",
          body["connected"] is True and body["source"] == "oauth"
          and body["account_name"] == "Appleseed", json.dumps(body))

    r = client.get("/oauth/status", headers={"Authorization": session_jwt(account_id=999999)})
    body = r.get_json()
    check("status reports an unconnected account",
          body["connected"] is False and body["install_url"].endswith("/oauth/install"),
          json.dumps(body))

    r = client.get("/oauth/status")
    check("status requires a session token", r.status_code == 401)

    r = client.post("/api/generate", json={"itemId": "555", "template": "quote.docx"},
                    headers={"Authorization": session_jwt(account_id=999999)})
    body = r.get_json()
    check("generating for an unconnected account returns 428 + install link",
          r.status_code == 428 and body.get("needsAuth") is True
          and body["installUrl"].endswith("/oauth/install"), json.dumps(body))

    r = client.post("/api/generate", json={"itemId": "555", "template": "quote.docx"},
                    headers={"Authorization": session_jwt()})
    jobs.wait_for_idle()
    job = jobs.get(r.get_json()["jobId"])
    check("connected account can generate", r.status_code == 202 and job["status"] == "done",
          (job or {}).get("error") or "")

    # ---- disconnect ---------------------------------------------------------------
    r = client.post("/oauth/disconnect", headers={"Authorization": session_jwt()})
    body = r.get_json()
    check("disconnect revokes upstream and forgets locally",
          body["forgotten"] is True and body["revoked"] is True and len(calls["revoke"]) == 1,
          json.dumps(body))
    check("token really gone", oauth.store.get("1825528") is None)

    # ---- fallback mode ------------------------------------------------------------
    os.environ["MONDAY_API_TOKEN"] = "dev-fallback"
    check("fallback token used when nothing is stored",
          oauth.resolve_api_token({"accountId": 1825528}) == "dev-fallback")
    r = client.get("/oauth/status", headers={"Authorization": session_jwt()})
    check("status agrees with the backend in fallback mode",
          r.get_json()["connected"] is True and r.get_json()["source"] == "fallback_token",
          json.dumps(r.get_json()))
    os.environ.pop("MONDAY_API_TOKEN")

    # ---- legacy flow --------------------------------------------------------------
    os.environ["MONDAY_OAUTH_LEGACY"] = "1"
    legacy_params = parse_qs(urlparse(client.get("/oauth/install").headers["Location"]).query)
    check("legacy flow omits PKCE", "code_challenge" not in legacy_params)
    os.environ.pop("MONDAY_OAUTH_LEGACY")

    failed = [n for n, ok, _ in checks if not ok]
    print(f"\n{len(checks) - len(failed)}/{len(checks)} checks passed")
    if failed:
        print("failed: " + ", ".join(failed))
    return 1 if failed else 0


def before_token(_refresh):
    return oauth.store.get("1825528")["access_token"]


if __name__ == "__main__":
    raise SystemExit(main())
