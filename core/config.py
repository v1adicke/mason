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
    openai_model: str
    openai_heavy_model: str
    obsidian_vault_root: str
    obsidian_daily_path: str
    caldav_server_url: str
    yandex_email: str
    yandex_app_password: str
    yandex_uni_email: str
    yandex_uni_app_password: str
    mason_system_prompt: str
    mason_timezone: str
    mason_night_owl_cutoff_hour: int
    mason_max_history_length: int


def _required_env(name: str) -> str:
    """Read required environment variable"""
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"{name} is not set")
    return value


def _optional_env(name: str) -> str:
    """Read optional environment variable"""
    return os.getenv(name, "").strip()


def _parse_int_env(name: str, default_value: int) -> int:
    """Read integer value from environment variable"""
    raw_value = _optional_env(name)
    if not raw_value:
        return default_value

    try:
        return int(raw_value)
    except ValueError as error:
        raise ValueError(f"{name} must be an integer") from error


def _normalize_prompt(prompt_text: str) -> str:
    """Support escaped newlines in .env prompt value"""
    return prompt_text.replace("\\n", "\n").strip()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load and validate settings from .env and environment"""
    prompt = _normalize_prompt(_required_env("MASON_SYSTEM_PROMPT"))
    if not prompt:
        raise ValueError("MASON_SYSTEM_PROMPT is not set")

    night_owl_cutoff = _parse_int_env("MASON_NIGHT_OWL_CUTOFF_HOUR", 4)
    if night_owl_cutoff < 0 or night_owl_cutoff > 23:
        night_owl_cutoff = 4

    return Settings(
        openai_api_key=_required_env("OPENAI_API_KEY"),
        openai_base_url=_required_env("OPENAI_BASE_URL"),
        openai_model=_required_env("OPENAI_MODEL"),
        openai_heavy_model=_optional_env("OPENAI_HEAVY_MODEL"),
        obsidian_vault_root=_required_env("OBSIDIAN_VAULT_ROOT"),
        obsidian_daily_path=_required_env("OBSIDIAN_DAILY_PATH"),
        caldav_server_url=_optional_env("CALDAV_SERVER_URL"),
        yandex_email=_optional_env("YANDEX_EMAIL"),
        yandex_app_password=_optional_env("YANDEX_APP_PASSWORD"),
        yandex_uni_email=_optional_env("YANDEX_UNI_EMAIL"),
        yandex_uni_app_password=_optional_env("YANDEX_UNI_APP_PASSWORD"),
        mason_system_prompt=prompt,
        mason_timezone=_optional_env("MASON_TIMEZONE") or "Europe/Moscow",
        mason_night_owl_cutoff_hour=night_owl_cutoff,
        mason_max_history_length=_parse_int_env("MASON_MAX_HISTORY_LENGTH", 50),
    )
