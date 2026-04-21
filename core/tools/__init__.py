"""Tool registry and tool module exports"""

from __future__ import annotations

from typing import Any, Callable


JSONSchema = dict[str, Any]
ToolHandler = Callable[..., str]


class ToolRegistry:
    """In memory registry for function tools"""

    def __init__(self) -> None:
        """Initialize empty registry"""
        self._handlers: dict[str, ToolHandler] = {}
        self._schemas: dict[str, JSONSchema] = {}

    def register(
        self,
        *,
        name: str,
        description: str,
        parameters: JSONSchema,
        handler: ToolHandler,
    ) -> None:
        """Register a callable tool and its JSON schema"""
        if name in self._handlers:
            raise ValueError(f"Tool '{name}' is already registered")

        normalized_parameters = dict(parameters)
        normalized_parameters["additionalProperties"] = False

        self._handlers[name] = handler
        self._schemas[name] = {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "strict": True,
                "parameters": normalized_parameters,
            },
        }

    def register_schema(self, schema: JSONSchema, handler: ToolHandler) -> None:
        """Register tool from full OpenAI tool schema"""
        function_payload = schema.get("function")
        if not isinstance(function_payload, dict):
            raise ValueError("Schema must contain function object")

        name = function_payload.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError("Function name is required in schema")
        if name in self._handlers:
            raise ValueError(f"Tool '{name}' is already registered")

        normalized_function_payload = dict(function_payload)
        normalized_function_payload["strict"] = True

        parameters = normalized_function_payload.get("parameters")
        if isinstance(parameters, dict):
            normalized_parameters = dict(parameters)
            normalized_parameters["additionalProperties"] = False
            normalized_function_payload["parameters"] = normalized_parameters

        normalized_schema: JSONSchema = {
            "type": "function",
            "function": normalized_function_payload,
        }

        self._handlers[name] = handler
        self._schemas[name] = normalized_schema

    def list_schemas(self) -> list[JSONSchema]:
        """Return OpenAI compatible tool schemas"""
        return list(self._schemas.values())

    def execute(self, name: str, arguments: dict[str, Any] | None = None) -> str:
        """Execute a registered tool by name with keyword arguments"""
        if name not in self._handlers:
            raise KeyError(f"Tool '{name}' is not registered")

        kwargs = arguments or {}
        try:
            result = self._handlers[name](**kwargs)
        except TypeError as error:
            return f"Ошибка аргументов инструмента: {error}"
        return str(result)


from .obsidian import (
    add_daily_task,
    add_daily_task_tool_schema,
    complete_daily_task,
    complete_daily_task_tool_schema,
    delete_daily_task,
    delete_daily_task_tool_schema,
    get_daily_tasks,
    get_daily_tasks_tool_schema,
    register_obsidian_daily_tools,
)
from .calendar import (
    add_calendar_event,
    add_calendar_event_tool_schema,
    delete_calendar_event,
    delete_calendar_event_tool_schema,
    get_calendar_events,
    get_calendar_events_tool_schema,
    register_calendar_tools,
)
from .system import get_system_time, register_system_tools, system_time_tool_schema


__all__ = [
    "JSONSchema",
    "ToolHandler",
    "ToolRegistry",
    "get_system_time",
    "system_time_tool_schema",
    "register_system_tools",
    "add_daily_task",
    "get_daily_tasks",
    "complete_daily_task",
    "delete_daily_task",
    "add_daily_task_tool_schema",
    "get_daily_tasks_tool_schema",
    "complete_daily_task_tool_schema",
    "delete_daily_task_tool_schema",
    "register_obsidian_daily_tools",
    "get_calendar_events",
    "add_calendar_event",
    "delete_calendar_event",
    "get_calendar_events_tool_schema",
    "add_calendar_event_tool_schema",
    "delete_calendar_event_tool_schema",
    "register_calendar_tools",
]
