"""Smoke test for the Lambda entrypoint — catches a broken Mangum/import wiring."""

from __future__ import annotations


def test_lambda_handler_importable():
    from app.lambda_handler import handler

    assert callable(handler)
