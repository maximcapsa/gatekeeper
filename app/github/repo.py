"""Read files from a repo via the GitHub contents API (installation-scoped)."""

from __future__ import annotations

import base64

import httpx

from app.github.auth import GITHUB_API


def get_file(owner: str, repo: str, path: str, ref: str, token: str) -> str | None:
    """Return a text file's contents at `ref`, or None if it doesn't exist."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    with httpx.Client(timeout=30) as client:
        resp = client.get(
            f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}",
            headers=headers,
            params={"ref": ref},
        )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    data = resp.json()
    if data.get("encoding") == "base64":
        return base64.b64decode(data["content"]).decode("utf-8")
    return data.get("content")
