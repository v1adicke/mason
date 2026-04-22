"""Calendar event tools powered by CalDAV"""

from __future__ import annotations

import json
from typing import Any

from .io import close_client_safely
from .io import get_caldav_clients
from .io import get_primary_calendar
from .io import parse_iso_datetime
from .io import resolve_day_bounds
from .io import to_iso


def _safe_event_load(event: Any) -> None:
    """Load event content if needed"""
    load = getattr(event, "load", None)
    if not callable(load):
        return

    try:
        load(only_if_unloaded=True)
    except TypeError:
        load()


def _event_identifiers(event: Any) -> list[str]:
    """Collect stable identifiers for event matching"""
    identifiers: list[str] = []

    _safe_event_load(event)

    ical = getattr(event, "icalendar_instance", None)
    if ical is not None:
        for component in ical.walk():
            if str(getattr(component, "name", "")).upper() != "VEVENT":
                continue
            uid = component.get("uid")
            if uid is not None:
                uid_text = str(uid).strip()
                if uid_text:
                    identifiers.append(uid_text)
            break

    for attr_name in ("id", "url"):
        attr_value = getattr(event, attr_name, None)
        if attr_value is None:
            continue
        text = str(attr_value).strip()
        if not text:
            continue
        identifiers.append(text)
        tail = text.rsplit("/", 1)[-1]
        if tail and tail != text:
            identifiers.append(tail)

    deduplicated: list[str] = []
    seen: set[str] = set()
    for item in identifiers:
        if item not in seen:
            seen.add(item)
            deduplicated.append(item)
    return deduplicated


def _event_payload(event: Any) -> dict[str, str] | None:
    """Extract event payload for tool response"""
    _safe_event_load(event)

    ical = getattr(event, "icalendar_instance", None)
    if ical is None:
        return None

    vevent = None
    for component in ical.walk():
        if str(getattr(component, "name", "")).upper() == "VEVENT":
            vevent = component
            break

    if vevent is None:
        return None

    summary_raw = vevent.get("summary")
    dtstart_raw = vevent.get("dtstart")
    dtend_raw = vevent.get("dtend")

    summary = str(summary_raw).strip() if summary_raw is not None else "(без названия)"
    dtstart = dtstart_raw.dt if hasattr(dtstart_raw, "dt") else None
    dtend = dtend_raw.dt if hasattr(dtend_raw, "dt") else None

    identifiers = _event_identifiers(event)
    event_id = identifiers[0] if identifiers else str(getattr(event, "url", "unknown_id"))

    return {
        "id": event_id,
        "summary": summary,
        "start": to_iso(dtstart),
        "end": to_iso(dtend),
    }


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
                except Exception as e:
                    debug_errors.append(f"{cal}: {e}")
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
            return f"События на {target_date} не найдены. Ошибки: {debug_errors}" if debug_errors else f"События на {target_date} не найдены"

        return json.dumps(payload, ensure_ascii=False, indent=2)
    except Exception as error:
        return f"Ошибка подключения к CalDAV: {error}"
    finally:
        for client in clients:
            close_client_safely(client)


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
        return None, (
            "Событие не найдено. Сначала вызови get_calendar_events и используй точный ID."
        )

    if len(matches) > 1:
        options = [_event_identifiers(event)[0] for event in matches if _event_identifiers(event)]
        return None, f"Найдено несколько событий, уточни точный ID: {options}"

    return matches[0], None


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
