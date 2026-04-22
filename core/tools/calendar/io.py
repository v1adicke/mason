"""CalDAV client and time helpers"""

from __future__ import annotations

from datetime import date
from datetime import datetime
from datetime import time
from datetime import timedelta
from datetime import timezone
from typing import Any
from zoneinfo import ZoneInfo

import caldav

from ...config import get_settings


SYSTEM_CALENDAR_MARKERS = (
    "birthdays",
    "birthday",
    "holidays",
    "holiday",
    "contacts",
    "tasks",
    "дни рождения",
    "день рождения",
    "праздники",
    "праздник",
    "контакты",
    "задачи",
)


def get_system_timezone() -> ZoneInfo:
    """Return configured system timezone, fallback to UTC."""
    settings = get_settings()
    try:
        return ZoneInfo(settings.mason_timezone)
    except Exception:
        return timezone.utc  # type: ignore[return-value]


def _create_caldav_client(email: str, app_password: str, server_url: str) -> Any:
    """Create a single authorized CalDAV client"""
    client_factory = getattr(caldav, "DAVClient", None)
    if not callable(client_factory):
        raise RuntimeError("Не удалось инициализировать CalDAV клиент")
    return client_factory(url=server_url, username=email, password=app_password)


def get_caldav_clients() -> list[Any]:
    """Create CalDAV clients for primary and optional university accounts"""
    settings = get_settings()

    server_url = settings.caldav_server_url
    if not server_url:
        raise ValueError("CALDAV_SERVER_URL is not set")

    primary_email = settings.yandex_email
    primary_app_password = settings.yandex_app_password
    if not primary_email:
        raise ValueError("YANDEX_EMAIL is not set")
    if not primary_app_password:
        raise ValueError("YANDEX_APP_PASSWORD is not set")

    clients: list[Any] = [
        _create_caldav_client(
            email=primary_email,
            app_password=primary_app_password,
            server_url=server_url,
        )
    ]

    uni_email = settings.yandex_uni_email
    uni_app_password = settings.yandex_uni_app_password
    if uni_email and uni_app_password:
        clients.append(
            _create_caldav_client(
                email=uni_email,
                app_password=uni_app_password,
                server_url=server_url,
            )
        )

    return clients


def get_primary_calendar(client: Any) -> Any:
    """Return primary calendar: named Default when available, otherwise first"""
    principal = client.principal()
    calendars = principal.calendars()
    if not calendars:
        raise RuntimeError("Календари пользователя не найдены")

    def _calendar_names(calendar: Any) -> list[str]:
        names: list[str] = []
        calendar_name = getattr(calendar, "name", None)
        if isinstance(calendar_name, str) and calendar_name.strip():
            names.append(calendar_name.strip())
        try:
            display_name = calendar.get_display_name()
            if isinstance(display_name, str) and display_name.strip():
                names.append(display_name.strip())
        except Exception:
            pass
        return names

    def _is_system_calendar(calendar: Any) -> bool:
        for name in _calendar_names(calendar):
            lowered = name.lower()
            if any(marker in lowered for marker in SYSTEM_CALENDAR_MARKERS):
                return True
        return False

    for calendar in calendars:
        if any(name.lower() == "default" for name in _calendar_names(calendar)):
            return calendar

    for calendar in calendars:
        if not _is_system_calendar(calendar):
            return calendar

    return calendars[0]


def resolve_day_bounds(target_date: str) -> tuple[datetime | None, datetime | None, str | None]:
    """Resolve YYYY-MM-DD into [start, end) day bounds in configured timezone"""
    clean_date = target_date.strip()
    if not clean_date:
        return None, None, "Неверный формат даты. Используйте YYYY-MM-DD"

    try:
        parsed_date = date.fromisoformat(clean_date)
    except ValueError:
        return None, None, "Неверный формат даты. Используйте YYYY-MM-DD"

    system_tz = get_system_timezone()
    start = datetime.combine(parsed_date, time.min, tzinfo=system_tz)
    end = start + timedelta(days=1)
    return start, end, None


def parse_iso_datetime(value: str) -> tuple[datetime | None, str | None]:
    """Parse ISO datetime and normalize to configured timezone"""
    clean_value = value.strip()
    if not clean_value:
        return None, "Неверный формат времени. Используйте ISO 8601"

    try:
        parsed = datetime.fromisoformat(clean_value)
    except ValueError:
        return None, "Неверный формат времени. Используйте ISO 8601"

    system_tz = get_system_timezone()
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=system_tz)
    else:
        parsed = parsed.astimezone(system_tz)
    return parsed, None


def to_iso(value: Any) -> str:
    """Convert datetime or date value to ISO string in configured timezone"""
    if isinstance(value, datetime):
        system_tz = get_system_timezone()
        normalized = value.replace(tzinfo=system_tz) if value.tzinfo is None else value.astimezone(system_tz)
        return normalized.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return ""


def close_client_safely(client: Any) -> None:
    """Close CalDAV client if close method exists"""
    close = getattr(client, "close", None)
    if callable(close):
        try:
            close()
        except Exception:
            pass
