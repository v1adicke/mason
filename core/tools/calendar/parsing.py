"""Event parsing helpers for CalDAV payloads"""

from __future__ import annotations

from typing import Any

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
