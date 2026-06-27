"""Application configuration.

Settings load from environment / .env. With no GROQ_API_KEY the app falls back to
deterministic MOCK mode so the full pipeline runs offline with zero LLM cost.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    groq_api_key: str | None = None
    force_mock: bool = False

    # GitHub App (webhook → Check Run flow). Empty in mock/local mode.
    github_app_id: str | None = None
    github_app_private_key_b64: str | None = None  # base64-encoded PEM
    github_webhook_secret: str | None = None

    # Model routing: cheap/fast models for triage-style work, a stronger model for fixes.
    model_triage: str = "llama-3.1-8b-instant"
    model_security: str = "llama-3.1-8b-instant"
    model_fix: str = "llama-3.3-70b-versatile"
    model_summary: str = "llama-3.1-8b-instant"

    # Gate policy: open issues at these severities block the merge.
    blocking_severities: tuple[str, ...] = ("BLOCKER", "CRITICAL")

    # How many top issues the fix-suggestion agent will draft patches for.
    max_fix_suggestions: int = 3

    @property
    def use_mock(self) -> bool:
        """True when we should skip real LLM calls (no key, or explicitly forced)."""
        return self.force_mock or not self.groq_api_key


@lru_cache
def get_settings() -> Settings:
    return Settings()
