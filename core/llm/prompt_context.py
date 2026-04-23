"""System prompt builders with logical date context"""

from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Any
from zoneinfo import ZoneInfo


WEEKDAY_NAMES_RU = (
    "понедельник",
    "вторник",
    "среда",
    "четверг",
    "пятница",
    "суббота",
    "воскресенье",
)


def _resolve_timezone(timezone_name: str) -> Any:
    """Resolve timezone by name with UTC fallback"""
    try:
        return ZoneInfo(timezone_name)
    except Exception:
        return timezone.utc


def _resolve_current_time_context(timezone_name: str, cutoff_hour: int) -> tuple[datetime, datetime]:
    """Resolve physical now and logical date-time with night-owl offset"""
    timezone_value = _resolve_timezone(timezone_name)
    now = datetime.now(timezone_value)
    logical_now = now - timedelta(days=1) if now.hour < cutoff_hour else now
    return now, logical_now


def _build_date_inference_rule(now: datetime, logical_now: datetime) -> str:
    """Build strict date-inference rule for tool-calling date resolution"""
    return (
        "DATE INFERENCE RULE:\n"
        f"Current logical date: {logical_now.date().isoformat()} (YYYY-MM-DD)\n"
        f"Current physical time: {now.isoformat(sep=' ', timespec='minutes')}\n"
        "Your task is to natively resolve all relative timeframes ('завтра', 'послезавтра', 'в среду') "
        "based on the Current logical date. When calling tools, you MUST pass the resolved date "
        "in strict YYYY-MM-DD format."
    )


def _build_system_time_context(now: datetime, logical_now: datetime) -> str:
    """Build dynamic server-time context for relative date grounding"""
    weekday_name = WEEKDAY_NAMES_RU[logical_now.weekday()]
    return (
        "[SYSTEM TIME CONTEXT] "
        f"Физическое время: {now.isoformat(sep=' ', timespec='minutes')}. "
        f"Логическое 'сегодня' для пользователя: {logical_now.isoformat(sep=' ', timespec='minutes')} "
        f"({weekday_name}). "
        "Если пользователь просит планы на 'сегодня' или 'завтра', делай расчеты строго от логической даты."
    )


def build_system_prompt(system_prompt: str, timezone_name: str, cutoff_hour: int) -> str:
    """Compose full system prompt with dynamic server-time context"""
    now, logical_now = _resolve_current_time_context(timezone_name, cutoff_hour)
    time_context = _build_system_time_context(now, logical_now)
    date_inference_rule = _build_date_inference_rule(now, logical_now)
    return f"{time_context}\n\n{date_inference_rule}\n\n{system_prompt}"
