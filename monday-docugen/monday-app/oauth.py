"""OAuth for the monday app — authorization code + PKCE, with rotating refresh tokens.

monday's current ("new") flow is OAuth 2.1:

    authorize  GET  https://auth.monday.com/oauth2/authorize      (PKCE S256 required)
    token      POST https://auth.monday.com/oauth_ms/oauth/token  (code exchange + refresh)
    revoke     POST https://auth.monday.com/oauth_ms/oauth/revoke

The token response carries no `expires_in` — the access token is itself a JWT, so its `exp`
claim is the authority on when to refresh. Refresh tokens rotate: every refresh returns a
new one and invalidates the old, so persisting the new pair is mandatory, not an
optimization.

Set MONDAY_OAUTH_LEGACY=1 for the older non-expiring flow (no PKCE, token at
/oauth2/token), which some existing apps are still on.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import pathlib
import secrets
import threading
import time

import jwt
import requests

AUTHORIZE_URL = "https://auth.monday.com/oauth2/authorize"
TOKEN_URL = "https://auth.monday.com/oauth_ms/oauth/token"
REVOKE_URL = "https://auth.monday.com/oauth_ms/oauth/revoke"
LEGACY_TOKEN_URL = "https://auth.monday.com/oauth2/token"
API_URL = "https://api.monday.com/v2"

DEFAULT_SCOPES = "me:read boards:read boards:write assets:read"
REFRESH_SKEW_SECONDS = 120
PENDING_TTL_SECONDS = 600


class OAuthError(RuntimeError):
    status = 400


class NeedsAuthError(RuntimeError):
    """No usable credentials for this account — the user has to connect it first."""

    status = 428

    def __init__(self, account_id: str | None, install_url: str):
        super().__init__("This monday account has not connected the app yet.")
        self.account_id = account_id
        self.install_url = install_url


def legacy() -> bool:
    return os.environ.get("MONDAY_OAUTH_LEGACY") == "1"


def _config(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise OAuthError(f"{name} is not set — OAuth is not configured")
    return value


def redirect_uri() -> str:
    explicit = os.environ.get("MONDAY_REDIRECT_URI")
    if explicit:
        return explicit
    base = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
    if not base:
        raise OAuthError("Set MONDAY_REDIRECT_URI or PUBLIC_BASE_URL")
    return f"{base}/oauth/callback"


def install_url() -> str:
    base = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
    return f"{base}/oauth/install" if base else "/oauth/install"


# ------------------------------------------------------------------ PKCE + state


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def challenge_for(verifier: str) -> str:
    return _b64url(hashlib.sha256(verifier.encode()).digest())


_pending: dict[str, dict] = {}
_pending_lock = threading.Lock()


def _new_pending() -> tuple[str, str]:
    """Mint a single-use state and its PKCE verifier."""
    state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(64)
    now = time.time()
    with _pending_lock:
        for key, entry in list(_pending.items()):  # expire stale attempts
            if now - entry["created_at"] > PENDING_TTL_SECONDS:
                _pending.pop(key, None)
        _pending[state] = {"verifier": verifier, "created_at": now}
    return state, verifier


def _claim_pending(state: str) -> dict:
    """Consume a state exactly once. Unknown, reused, or stale states are rejected."""
    with _pending_lock:
        entry = _pending.pop(state, None)
    if not entry:
        raise OAuthError("Unknown or already-used state — restart the connection")
    if time.time() - entry["created_at"] > PENDING_TTL_SECONDS:
        raise OAuthError("Authorization request expired — restart the connection")
    return entry


def authorize_url(*, subdomain: str | None = None) -> str:
    from urllib.parse import urlencode

    state, verifier = _new_pending()
    params = {
        "client_id": _config("MONDAY_CLIENT_ID"),
        "redirect_uri": redirect_uri(),
        "scope": os.environ.get("MONDAY_SCOPES", DEFAULT_SCOPES),
        "state": state,
    }
    if not legacy():
        params["code_challenge"] = challenge_for(verifier)
        params["code_challenge_method"] = "S256"
    if subdomain:
        params["subdomain"] = subdomain
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


# ----------------------------------------------------------------- token exchange


def _post_token(body: dict) -> dict:
    url = LEGACY_TOKEN_URL if legacy() else TOKEN_URL
    response = requests.post(url, json=body, timeout=30,
                             headers={"Content-Type": "application/json"})
    if response.status_code != 200:
        raise OAuthError(f"Token endpoint returned {response.status_code}: "
                         f"{response.text[:300]}")
    payload = response.json()
    if "access_token" not in payload:
        raise OAuthError(f"No access_token in token response: {json.dumps(payload)[:300]}")
    return payload


def exchange_code(code: str, verifier: str) -> dict:
    body = {
        "grant_type": "authorization_code",
        "client_id": _config("MONDAY_CLIENT_ID"),
        "client_secret": _config("MONDAY_CLIENT_SECRET"),
        "code": code,
        "redirect_uri": redirect_uri(),
    }
    if not legacy():
        body["code_verifier"] = verifier
    return _post_token(body)


def refresh_tokens(refresh_token: str) -> dict:
    if legacy():
        raise OAuthError("The legacy flow issues non-expiring tokens; nothing to refresh")
    return _post_token({
        "grant_type": "refresh_token",
        "client_id": _config("MONDAY_CLIENT_ID"),
        "client_secret": _config("MONDAY_CLIENT_SECRET"),
        "refresh_token": refresh_token,
    })


def revoke(token: str) -> bool:
    response = requests.post(REVOKE_URL, timeout=30, json={
        "token": token,
        "client_id": _config("MONDAY_CLIENT_ID"),
        "client_secret": _config("MONDAY_CLIENT_SECRET"),
    })
    return response.status_code in (200, 204)


def token_expiry(access_token: str) -> int | None:
    """Read `exp` out of the access token; monday sends no expires_in."""
    try:
        claims = jwt.decode(access_token, options={"verify_signature": False})
    except jwt.InvalidTokenError:
        return None  # legacy opaque/non-expiring token
    return claims.get("exp")


def identify(access_token: str) -> dict:
    """Ask the API who this token belongs to, so we can key storage by account."""
    response = requests.post(
        API_URL,
        json={"query": "query { me { id name account { id name } } }"},
        headers={"Authorization": access_token, "API-Version": "2024-10"},
        timeout=30,
    )
    if response.status_code != 200:
        raise OAuthError(f"Could not identify the token holder: HTTP {response.status_code}")
    data = (response.json() or {}).get("data") or {}
    me = data.get("me") or {}
    account = me.get("account") or {}
    if not account.get("id"):
        raise OAuthError("Token response had no account — is the me:read scope granted?")
    return {"account_id": str(account["id"]), "account_name": account.get("name"),
            "user_id": str(me.get("id") or ""), "user_name": me.get("name")}


# ------------------------------------------------------------------- token store


class TokenStore:
    """Per-account credentials on disk.

    A 0600 JSON file is enough for a single-tenant deployment. For a distributed app use
    monday code's secure storage or a KMS-backed secret store — these are live credentials
    to someone else's account.
    """

    def __init__(self, path: pathlib.Path | None = None):
        self.path = pathlib.Path(
            path or os.environ.get("DOCUGEN_TOKEN_STORE",
                                   pathlib.Path(__file__).parent / ".tokens.json")
        )
        self._lock = threading.Lock()

    def _read(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text())
        except (ValueError, OSError):
            return {}

    def _write(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2))
        tmp.chmod(0o600)
        tmp.replace(self.path)
        self.path.chmod(0o600)

    def save(self, account_id: str, tokens: dict, meta: dict | None = None) -> dict:
        record = {
            "access_token": tokens["access_token"],
            "refresh_token": tokens.get("refresh_token"),
            "scope": tokens.get("scope"),
            "obtained_at": int(time.time()),
            "expires_at": token_expiry(tokens["access_token"]),
            **(meta or {}),
        }
        with self._lock:
            data = self._read()
            data[str(account_id)] = record
            self._write(data)
        return record

    def get(self, account_id: str) -> dict | None:
        with self._lock:
            return self._read().get(str(account_id))

    def forget(self, account_id: str) -> bool:
        with self._lock:
            data = self._read()
            existed = data.pop(str(account_id), None) is not None
            if existed:
                self._write(data)
        return existed

    def accounts(self) -> list[str]:
        with self._lock:
            return sorted(self._read())


store = TokenStore()


def access_token_for(account_id: str) -> str | None:
    """A currently-valid access token for the account, refreshing if it's about to expire."""
    record = store.get(account_id)
    if not record:
        return None

    expires_at = record.get("expires_at")
    if not expires_at or expires_at - time.time() > REFRESH_SKEW_SECONDS:
        return record["access_token"]

    refresh_token = record.get("refresh_token")
    if not refresh_token:
        return None  # expired with no way to renew — the user must reconnect
    tokens = refresh_tokens(refresh_token)
    # The rotated refresh token replaces the old one; losing it means reconnecting.
    saved = store.save(account_id, tokens, {k: record[k] for k in
                                            ("account_name", "user_id", "user_name")
                                            if k in record})
    return saved["access_token"]


def resolve_api_token(claims: dict) -> str:
    """Pick the token to call the monday API with, in order of preference.

    1. `shortLivedToken` from an integration request — scoped to that request, best choice.
    2. The account's stored OAuth token, refreshed if needed.
    3. MONDAY_API_TOKEN, a single-account development fallback.
    """
    short_lived = claims.get("shortLivedToken") or (claims.get("dat") or {}).get("shortLivedToken")
    if short_lived:
        return short_lived

    account_id = str(claims.get("accountId") or "")
    if account_id:
        token = access_token_for(account_id)
        if token:
            return token

    fallback = os.environ.get("MONDAY_API_TOKEN")
    if fallback:
        return fallback

    raise NeedsAuthError(account_id or None, install_url())


def status_for(account_id: str) -> dict:
    """Report what resolve_api_token would actually manage for this account.

    Must agree with resolve_api_token, or the UI blocks work the backend could do (or
    invites the user to generate something that will fail).
    """
    record = store.get(str(account_id))
    if not record:
        if os.environ.get("MONDAY_API_TOKEN"):
            return {"connected": True, "source": "fallback_token",
                    "install_url": install_url()}
        return {"connected": False, "source": None, "install_url": install_url()}
    return {
        "connected": True,
        "source": "oauth",
        "account_name": record.get("account_name"),
        "user_name": record.get("user_name"),
        "scope": record.get("scope"),
        "expires_at": record.get("expires_at"),
        "install_url": install_url(),
    }
