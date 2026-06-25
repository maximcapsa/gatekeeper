"""Thin Groq client wrapper.

Callers must guard real calls behind ``get_settings().use_mock`` — this module
assumes a key is present when invoked.
"""

from __future__ import annotations

import json
from typing import Any

from groq import Groq

from app.config import get_settings

_client: Groq | None = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=get_settings().groq_api_key)
    return _client


def chat_json(system: str, user: str, model: str) -> dict[str, Any]:
    """Call Groq with JSON-object response format and parse the result.

    Returns an empty dict if the model returns unparseable content, so callers
    can fall back to their deterministic defaults.
    """
    resp = _get_client().chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    content = resp.choices[0].message.content or "{}"
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {}
