"""Application configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    openai_api_key: str | None
    openai_model: str
    openai_timeout_seconds: float



def load_settings() -> Settings:
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY") or None
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    timeout = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "30"))
    return Settings(
        openai_api_key=api_key,
        openai_model=model,
        openai_timeout_seconds=timeout,
    )
