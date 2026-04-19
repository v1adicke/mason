"""Tool registration and execution primitives"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable


JSONSchema = dict[str, Any]
ToolHandler = Callable[..., str]


def get_system_time() -> str:
    """Return current local time"""
    return datetime.now().astimezone().isoformat(timespec="seconds")


class ToolRegistry:
    """In-memory registry for function tools"""

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

        self._handlers[name] = handler
        self._schemas[name] = {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": parameters,
            },
        }

    def list_schemas(self) -> list[JSONSchema]:
        """Return OpenAI-compatible tool schemas"""
        return list(self._schemas.values())

    def execute(self, name: str, arguments: dict[str, Any] | None = None) -> str:
        """Execute a registered tool by name with keyword arguments"""
        if name not in self._handlers:
            raise KeyError(f"Tool '{name}' is not registered")

        kwargs = arguments or {}
        result = self._handlers[name](**kwargs)
        return str(result)


def system_time_tool_schema() -> JSONSchema:
    """Build JSON schema for get_system_time tool"""
    return {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    }
