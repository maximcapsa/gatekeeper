"""GitHub webhook signature verification."""

from __future__ import annotations

import hashlib
import hmac

from app.config import get_settings


def verify_signature(body: bytes, signature_header: str | None) -> bool:
    """Verify the X-Hub-Signature-256 HMAC against the configured webhook secret."""
    secret = get_settings().github_webhook_secret
    if not secret or not signature_header:
        return False
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)
