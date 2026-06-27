"""GitHub App authentication.

Mint a short-lived App JWT from the App's private key, then exchange it for an
installation access token scoped to the org/repo where the App is installed.
"""

from __future__ import annotations

import base64
import time

import httpx
import jwt

from app.config import get_settings

GITHUB_API = "https://api.github.com"


def _private_key_pem() -> str:
    raw = get_settings().github_app_private_key_b64 or ""
    return base64.b64decode(raw).decode("utf-8")


def app_jwt() -> str:
    """A 10-minute App JWT (RS256), signed with the App private key."""
    now = int(time.time())
    payload = {"iat": now - 60, "exp": now + 540, "iss": get_settings().github_app_id}
    return jwt.encode(payload, _private_key_pem(), algorithm="RS256")


def installation_token(installation_id: int) -> str:
    """Exchange the App JWT for an installation access token."""
    headers = {
        "Authorization": f"Bearer {app_jwt()}",
        "Accept": "application/vnd.github+json",
    }
    with httpx.Client(timeout=30) as client:
        resp = client.post(
            f"{GITHUB_API}/app/installations/{installation_id}/access_tokens",
            headers=headers,
        )
        resp.raise_for_status()
        return resp.json()["token"]
