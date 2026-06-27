"""Tests for GitHub webhook signature verification."""

from __future__ import annotations

import hashlib
import hmac

import pytest

from app.config import get_settings
from app.github.webhook import verify_signature

SECRET = "test-secret"


@pytest.fixture(autouse=True)
def webhook_secret():
    settings = get_settings()
    original = settings.github_webhook_secret
    settings.github_webhook_secret = SECRET
    yield
    settings.github_webhook_secret = original


def _sign(body: bytes) -> str:
    return "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()


def test_valid_signature_passes():
    body = b'{"action":"opened"}'
    assert verify_signature(body, _sign(body)) is True


def test_tampered_body_fails():
    body = b'{"action":"opened"}'
    assert verify_signature(b'{"action":"closed"}', _sign(body)) is False


def test_missing_signature_fails():
    assert verify_signature(b"{}", None) is False
