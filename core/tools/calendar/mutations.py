"""Calendar event mutation handlers"""

from __future__ import annotations

from typing import Any

from .io import close_client_safely
from .io import get_caldav_clients
from .io import get_primary_calendar
from .io import parse_iso_datetime
from .matching import _find_event_by_id
from .parsing import _event_identifiers


def add_calendar_event(
    summary: str = "",
    start_dt: str = "",
    end_dt: str = "",
    description: str | None = None,
) -> str:
    """Add calendar event with ISO start/end datetime"""
    clean_summary = summary.strip()
    if not clean_summary:
        return "Не удалось добавить событие: пустой summary"

    start_value, start_error = parse_iso_datetime(start_dt)
    if start_error is not None:
        return start_error
    end_value, end_error = parse_iso_datetime(end_dt)
    if end_error is not None:
        return end_error
    if start_value is None or end_value is None:
        return "Не удалось добавить событие: не удалось обработать время"
    if end_value <= start_value:
        return "Не удалось добавить событие: end_dt должен быть позже start_dt"

    clients: list[Any] = []
    try:
        clients = get_caldav_clients()
        calendar = get_primary_calendar(clients[0])

        event_kwargs: dict[str, Any] = {
            "summary": clean_summary,
            "dtstart": start_value,
            "dtend": end_value,
        }
        if description is not None and description.strip():
            event_kwargs["description"] = description.strip()

        event = calendar.add_event(**event_kwargs)
        identifiers = _event_identifiers(event)
        event_id = identifiers[0] if identifiers else ""
        if event_id:
            return f"Событие добавлено. ID: {event_id}"
        return "Событие добавлено"
    except Exception as error:
        return f"Ошибка подключения к CalDAV: {error}"
    finally:
        for client in clients:
            close_client_safely(client)


def delete_calendar_event(event_id: str = "") -> str:
    """Delete calendar event by unique identifier"""
    clean_event_id = event_id.strip()
    if not clean_event_id:
        return (
            "Не удалось удалить событие: пустой event_id. "
            "Сначала вызови get_calendar_events и выбери нужный ID."
        )

    clients: list[Any] = []
    try:
        clients = get_caldav_clients()
        for client in clients:
            try:
                calendars = client.principal().calendars()
            except Exception:
                continue

            for cal in calendars:
                event, _ = _find_event_by_id(cal, clean_event_id)
                if event is None:
                    continue

                try:
                    event.delete()
                    return "Событие удалено"
                except Exception:
                    continue

        return "Событие не найдено ни в одном из календарей (или нет прав на удаление)"
    except Exception as error:
        return f"Ошибка подключения к CalDAV: {error}"
    finally:
        for client in clients:
            close_client_safely(client)
