"""Calendar event query handlers"""

from __future__ import annotations

import json
from typing import Any

from .io import close_client_safely
from .io import get_caldav_clients
from .io import resolve_day_bounds
from .parsing import _event_payload


def _calendar_events_by_day(calendar: Any, start: Any, end: Any) -> list[Any]:
    """Fetch events in [start, end) using CalDAV date search"""
    events = calendar.date_search(start=start, end=end, expand=True)
    return list(events)


def get_calendar_events(target_date: str = "") -> str:
    """Return calendar events for target date (YYYY-MM-DD)"""
    start_dt, end_dt, date_error = resolve_day_bounds(target_date)
    if date_error is not None:
        return date_error
    if start_dt is None or end_dt is None:
        return "Не удалось получить события: не удалось определить диапазон даты"

    clients: list[Any] = []
    try:
        clients = get_caldav_clients()
        all_events: list[Any] = []
        debug_errors: list[str] = []
        for client in clients:
            try:
                calendars = client.principal().calendars()
            except Exception:
                continue

            for cal in calendars:
                try:
                    calendar_events = _calendar_events_by_day(cal, start_dt, end_dt)
                except Exception as error:
                    debug_errors.append(f"{cal}: {error}")
                    continue
                all_events.extend(calendar_events)

        payload: list[dict[str, str]] = []
        seen_ids = set()
        for event in all_events:
            event_payload = _event_payload(event)
            if event_payload is not None:
                event_id = str(event_payload.get("id", ""))
                if event_id not in seen_ids:
                    seen_ids.add(event_id)
                    payload.append(event_payload)

        if not payload:
            if debug_errors:
                return f"События на {target_date} не найдены. Ошибки: {debug_errors}"
            return f"События на {target_date} не найдены"

        return json.dumps(payload, ensure_ascii=False, indent=2)
    except Exception as error:
        return f"Ошибка подключения к CalDAV: {error}"
    finally:
        for client in clients:
            close_client_safely(client)
