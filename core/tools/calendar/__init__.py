"""Calendar tools package exports"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .events import add_calendar_event
from .events import delete_calendar_event
from .events import get_calendar_events
from .io import MSK_TZ
from .schemas import CRITICAL_EVENT_MATCHING_STRATEGY
from .schemas import RELATIVE_TIME_DESCRIPTION
from .schemas import TARGET_DATE_DESCRIPTION
from .schemas import add_calendar_event_tool_schema
from .schemas import delete_calendar_event_tool_schema
from .schemas import get_calendar_events_tool_schema

if TYPE_CHECKING:
    from .. import ToolRegistry


def register_calendar_tools(registry: ToolRegistry) -> None:
    """Register calendar tools in registry"""
    registry.register(
        name="get_calendar_events",
        description="Возвращает список событий календаря на указанную дату",
        parameters=get_calendar_events_tool_schema(),
        handler=get_calendar_events,
    )
    registry.register(
        name="add_calendar_event",
        description="Добавляет событие в календарь",
        parameters=add_calendar_event_tool_schema(),
        handler=add_calendar_event,
    )
    registry.register(
        name="delete_calendar_event",
        description=(
            "Удаляет событие из календаря по ID. "
            + CRITICAL_EVENT_MATCHING_STRATEGY
        ),
        parameters=delete_calendar_event_tool_schema(),
        handler=delete_calendar_event,
    )


__all__ = [
    "MSK_TZ",
    "RELATIVE_TIME_DESCRIPTION",
    "TARGET_DATE_DESCRIPTION",
    "CRITICAL_EVENT_MATCHING_STRATEGY",
    "get_calendar_events",
    "add_calendar_event",
    "delete_calendar_event",
    "get_calendar_events_tool_schema",
    "add_calendar_event_tool_schema",
    "delete_calendar_event_tool_schema",
    "register_calendar_tools",
]
