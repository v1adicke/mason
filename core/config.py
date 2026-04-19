"""Configuration loading from environment variables"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True, slots=True)
class Settings:
    """Application settings"""

    openai_api_key: str
    openai_base_url: str


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load and validate settings from .env and environment"""
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    base_url = os.getenv("OPENAI_BASE_URL", "").strip()

    if not api_key:
        raise ValueError("OPENAI_API_KEY is not set")
    if not base_url:
        raise ValueError("OPENAI_BASE_URL is not set")

    return Settings(openai_api_key=api_key, openai_base_url=base_url)
