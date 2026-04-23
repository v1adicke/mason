"""Backward-compatible facade for calendar event tools"""

from __future__ import annotations

from .mutations import add_calendar_event
from .mutations import delete_calendar_event
from .query import get_calendar_events


__all__ = [
    "get_calendar_events",
    "add_calendar_event",
    "delete_calendar_event",
]
