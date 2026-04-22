"""System utility tools"""

from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from ..config import get_settings


JSONSchema = dict[str, Any]

if TYPE_CHECKING:
    from . import ToolRegistry


def get_system_time() -> str:
    """Return current local time"""
    settings = get_settings()
    try:
        tz_value = ZoneInfo(settings.mason_timezone)
    except Exception:
        tz_value = timezone(timedelta(hours=3))
    return datetime.now(tz_value).isoformat(timespec="seconds")


def system_time_tool_schema() -> JSONSchema:
    """Build JSON schema for get_system_time tool"""
    return {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    }


def register_system_tools(registry: ToolRegistry) -> None:
    """Register system level tools in registry"""
    registry.register(
        name="get_system_time",
        description="Возвращает текущее локальное время",
        parameters=system_time_tool_schema(),
        handler=get_system_time,
    )
