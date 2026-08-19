"""Verification of the two different tokens monday.com sends an app.

1. Integration endpoints (custom action Run URL, remote-options URL) receive an
   `Authorization` JWT signed with the app's **signing secret**. Its claims are
   {accountId, userId, aud, exp, iat, shortLivedToken} — `aud` is the exact endpoint
   URL monday called, and `shortLivedToken` is an API token you can use immediately
   to act on behalf of the account.

2. A frontend view (item view iframe) calls `monday.get('sessionToken')`; that token is
   signed with the app's **client secret** and is NOT interchangeable with the above.

Never trust decoded-but-unverified claims — a forged JWT decodes just fine.
"""

from __future__ import annotations

import os

import jwt

SIGNING_SECRET_ENV = "MONDAY_SIGNING_SECRET"
CLIENT_SECRET_ENV = "MONDAY_CLIENT_SECRET"
BASE_URL_ENV = "PUBLIC_BASE_URL"


class AuthError(Exception):
    """Raised when a monday-issued token is missing, forged, or expired."""

    status = 401


def bearer(header: str | None) -> str:
    if not header:
        raise AuthError("Missing Authorization header")
    return header.strip()[7:].strip() if header.lower().startswith("bearer ") else header.strip()


def expected_audience(path: str) -> str | None:
    """The `aud` monday will send: our public URL for this endpoint.

    Returns None when PUBLIC_BASE_URL is unset (local development), which disables the
    audience check — acceptable while tunnelling, never in production.
    """
    base = os.environ.get(BASE_URL_ENV, "").rstrip("/")
    return f"{base}{path}" if base else None


def _secret(env_name: str) -> str:
    secret = os.environ.get(env_name)
    if not secret:
        raise AuthError(f"{env_name} is not set — cannot verify monday tokens")
    return secret


def verify_integration_request(auth_header: str | None, path: str) -> dict:
    """Verify a JWT on a custom action / remote options request. Returns its claims."""
    token = bearer(auth_header)
    audience = expected_audience(path)
    try:
        return jwt.decode(
            token,
            _secret(SIGNING_SECRET_ENV),
            algorithms=["HS256"],
            audience=audience,
            options={"verify_aud": audience is not None, "require": ["exp"]},
        )
    except jwt.InvalidTokenError as exc:
        raise AuthError(f"Invalid monday integration token: {exc}") from exc


def verify_session_token(auth_header: str | None) -> dict:
    """Verify a sessionToken minted for our iframe by the monday JS SDK."""
    token = bearer(auth_header)
    try:
        return jwt.decode(
            token,
            _secret(CLIENT_SECRET_ENV),
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
    except jwt.InvalidTokenError as exc:
        raise AuthError(f"Invalid monday session token: {exc}") from exc


def api_token(claims: dict) -> str:
    """The token to call the monday API with, preferring the request's short-lived one."""
    token = claims.get("shortLivedToken") or (claims.get("dat") or {}).get("shortLivedToken")
    if token:
        return token
    fallback = os.environ.get("MONDAY_API_TOKEN")
    if fallback:
        return fallback
    raise AuthError(
        "No shortLivedToken in the request and no MONDAY_API_TOKEN fallback configured. "
        "Session tokens from an item view do not carry API access — have the frontend "
        "call the monday API itself via monday.api(), or configure OAuth."
    )
