"""Obsidian daily note filesystem helpers"""

from __future__ import annotations

from datetime import datetime
from datetime import timedelta
import os

from ...config import get_settings


DEFAULT_FORWARD_SCAN_DAYS = 14


def _resolve_date_str(target_date: str | None = None) -> tuple[str | None, str | None]:
    """Resolve target date or return validation error"""
    if target_date is None:
        return datetime.now().date().isoformat(), None

    clean_date = target_date.strip()
    if not clean_date:
        return datetime.now().date().isoformat(), None

    try:
        parsed = datetime.strptime(clean_date, "%Y-%m-%d").date()
    except ValueError:
        return None, "Неверный формат даты. Используйте YYYY-MM-DD"

    return parsed.isoformat(), None


def _daily_note_path(target_date: str | None = None) -> tuple[str | None, str | None, str | None, str | None]:
    """Build daily note paths for target date"""
    settings = get_settings()
    date_str, date_error = _resolve_date_str(target_date)
    if date_error is not None or date_str is None:
        return settings.obsidian_daily_path, None, None, date_error

    note_path = os.path.join(settings.obsidian_daily_path, f"{date_str}.md")
    return settings.obsidian_daily_path, date_str, note_path, None


def _candidate_dates(target_date: str | None = None, days_forward: int = DEFAULT_FORWARD_SCAN_DAYS) -> tuple[list[str] | None, str | None]:
    """Build candidate date list for task scanning"""
    if target_date is not None and target_date.strip():
        date_str, date_error = _resolve_date_str(target_date)
        if date_error is not None or date_str is None:
            return None, date_error
        return [date_str], None

    today = datetime.now().date()
    dates = [(today + timedelta(days=offset)).isoformat() for offset in range(days_forward + 1)]
    return dates, None


def _note_path_by_date(date_str: str) -> tuple[str, str]:
    """Build note path for known valid date string"""
    settings = get_settings()
    return settings.obsidian_daily_path, os.path.join(settings.obsidian_daily_path, f"{date_str}.md")


def _ensure_daily_note(daily_dir: str, date_str: str, note_path: str) -> None:
    """Create daily note file with base template if it does not exist"""
    os.makedirs(daily_dir, exist_ok=True)
    if not os.path.exists(note_path):
        with open(note_path, "w", encoding="utf-8") as file:
            file.write(f"# Задачи на {date_str}\n\n")
