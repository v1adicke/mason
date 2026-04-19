"""Tool registration and execution primitives"""

from __future__ import annotations

from datetime import datetime
import os
from typing import Any, Callable

from .config import get_settings


JSONSchema = dict[str, Any]
ToolHandler = Callable[..., str]


def get_system_time() -> str:
    """Return current local time"""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _today_note_path() -> tuple[str, str, str]:
    """Build daily note paths for today"""
    settings = get_settings()
    date_str = datetime.now().date().isoformat()
    note_path = os.path.join(settings.obsidian_daily_path, f"{date_str}.md")
    return settings.obsidian_daily_path, date_str, note_path


def add_daily_task(task_text: str = "") -> str:
    """Append an unchecked task to today Obsidian daily note"""
    clean_text = task_text.strip()
    if not clean_text:
        return "Не удалось добавить задачу: пустой текст задачи"

    try:
        daily_dir, date_str, note_path = _today_note_path()
        os.makedirs(daily_dir, exist_ok=True)
        file_exists = os.path.exists(note_path)

        with open(note_path, "a", encoding="utf-8") as file:
            if not file_exists:
                file.write(f"# Задачи на {date_str}\n\n")
            file.write(f"- [ ] {clean_text}\n")
    except OSError as error:
        return f"Ошибка файловой системы: {error}"

    return "Задача успешно добавлена"


def get_daily_tasks() -> str:
    """Return unchecked tasks from today Obsidian daily note"""
    try:
        _, _, note_path = _today_note_path()
        if not os.path.exists(note_path):
            return "На сегодня задач пока нет"

        with open(note_path, "r", encoding="utf-8") as file:
            task_lines = [line.strip() for line in file if "- [ ]" in line]
    except OSError as error:
        return f"Ошибка файловой системы: {error}"

    if not task_lines:
        return "На сегодня задач пока нет"

    return "\n".join(task_lines)


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
        try:
            result = self._handlers[name](**kwargs)
        except TypeError as error:
            return f"Ошибка аргументов инструмента: {error}"
        return str(result)


def system_time_tool_schema() -> JSONSchema:
    """Build JSON schema for get_system_time tool"""
    return {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    }


def add_daily_task_tool_schema() -> JSONSchema:
    """Build JSON schema for add_daily_task tool"""
    return {
        "type": "object",
        "properties": {
            "task_text": {
                "type": "string",
                "description": "Текст задачи для добавления в ежедневную заметку",
            }
        },
        "required": ["task_text"],
        "additionalProperties": False,
    }


def get_daily_tasks_tool_schema() -> JSONSchema:
    """Build JSON schema for get_daily_tasks tool"""
    return {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    }


def register_obsidian_daily_tools(registry: ToolRegistry) -> None:
    """Register Obsidian daily task tools in registry"""
    registry.register(
        name="add_daily_task",
        description="Добавляет задачу на сегодня в Obsidian daily note",
        parameters=add_daily_task_tool_schema(),
        handler=add_daily_task,
    )
    registry.register(
        name="get_daily_tasks",
        description="Возвращает незавершенные задачи на сегодня из Obsidian daily note без аргументов",
        parameters=get_daily_tasks_tool_schema(),
        handler=get_daily_tasks,
    )
