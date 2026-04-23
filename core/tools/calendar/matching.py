"""Event matching helpers for deletion flows"""

from __future__ import annotations

from typing import Any

from .parsing import _event_identifiers
from .parsing import _safe_event_load


def _find_event_by_id(calendar: Any, event_id: str) -> tuple[Any | None, str | None]:
    """Find event by identifier using direct and protected search"""
    try:
        direct_event = calendar.event(event_id)
        _safe_event_load(direct_event)
        return direct_event, None
    except Exception:
        pass

    try:
        events = list(calendar.events())
    except Exception as error:
        return None, f"Ошибка получения списка событий: {error}"

    matches: list[Any] = []
    for event in events:
        ids = _event_identifiers(event)
        if event_id in ids:
            matches.append(event)

    if not matches:
        return None, "Событие не найдено. Сначала вызови get_calendar_events и используй точный ID."

    if len(matches) > 1:
        options = [_event_identifiers(event)[0] for event in matches if _event_identifiers(event)]
        return None, f"Найдено несколько событий, уточни точный ID: {options}"

    return matches[0], None
