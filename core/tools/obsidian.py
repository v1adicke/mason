"""Obsidian daily task tools"""

from __future__ import annotations

from datetime import datetime
import os
from typing import TYPE_CHECKING, Any

from ..config import get_settings


JSONSchema = dict[str, Any]

if TYPE_CHECKING:
    from . import ToolRegistry


TARGET_DATE_DESCRIPTION = (
    "The target date in YYYY-MM-DD format. If the user specifies a relative date "
    "like 'tomorrow', 'next Saturday', or 'on the 15th', you MUST calculate the "
    "exact YYYY-MM-DD date based on the current system time and pass it here. "
    "If no date is specified, omit this parameter."
)


def _resolve_date_str(target_date: str | None = None) -> tuple[str | None, str | None]:
    """Resolve target date or return validation error."""
    if target_date is None:
        return datetime.now().date().isoformat(), None

    clean_date = target_date.strip()
    if not clean_date:
        return datetime.now().date().isoformat(), None

    try:
        parsed = datetime.strptime(clean_date, "%Y-%m-%d").date()
    except ValueError:
        return None, "Неверный формат даты. Используйте YYYY-MM-DD"

    return parsed.isoformat(), None


def _daily_note_path(target_date: str | None = None) -> tuple[str | None, str | None, str | None, str | None]:
    """Build daily note paths for target date."""
    settings = get_settings()
    date_str, date_error = _resolve_date_str(target_date)
    if date_error is not None or date_str is None:
        return settings.obsidian_daily_path, None, None, date_error

    note_path = os.path.join(settings.obsidian_daily_path, f"{date_str}.md")
    return settings.obsidian_daily_path, date_str, note_path, None


def _ensure_daily_note(daily_dir: str, date_str: str, note_path: str) -> None:
    """Create daily note file with base template if it does not exist."""
    os.makedirs(daily_dir, exist_ok=True)
    if not os.path.exists(note_path):
        with open(note_path, "w", encoding="utf-8") as file:
            file.write(f"# Задачи на {date_str}\n\n")


def add_daily_task(task_text: str = "", target_date: str | None = None) -> str:
    """Append an unchecked task to today Obsidian daily note"""
    clean_text = task_text.strip()
    if not clean_text:
        return "Не удалось добавить задачу: пустой текст задачи"

    try:
        daily_dir, date_str, note_path, date_error = _daily_note_path(target_date)
        if date_error is not None:
            return date_error
        if daily_dir is None or date_str is None or note_path is None:
            return "Не удалось добавить задачу: не удалось определить путь заметки"

        _ensure_daily_note(daily_dir, date_str, note_path)

        with open(note_path, "a", encoding="utf-8") as file:
            file.write(f"- [ ] {clean_text}\n")
    except OSError as error:
        return f"Ошибка файловой системы: {error}"

    return "Задача успешно добавлена"


def get_daily_tasks(target_date: str | None = None) -> str:
    """Return unchecked tasks from today Obsidian daily note"""
    try:
        daily_dir, date_str, note_path, date_error = _daily_note_path(target_date)
        if date_error is not None:
            return date_error
        if daily_dir is None or date_str is None or note_path is None:
            return "Не удалось получить задачи: не удалось определить путь заметки"

        _ensure_daily_note(daily_dir, date_str, note_path)

        with open(note_path, "r", encoding="utf-8") as file:
            task_lines = [line.strip() for line in file if "- [ ]" in line]
    except OSError as error:
        return f"Ошибка файловой системы: {error}"

    if not task_lines:
        return "На сегодня задач пока нет"

    return "\n".join(task_lines)


def _find_task_line_index(lines: list[str], task_text: str) -> int | None:
    """Find first checkbox task line that contains task text"""
    lookup = task_text.lower()
    for index, line in enumerate(lines):
        line_lower = line.lower()
        if "- [ ]" not in line_lower and "- [x]" not in line_lower:
            continue
        if lookup in line_lower:
            return index
    return None


def delete_daily_task(task_text: str = "", target_date: str | None = None) -> str:
    """Delete matching task from today note"""
    clean_text = task_text.strip()
    if not clean_text:
        return "Не удалось удалить задачу: пустой текст задачи"

    try:
        daily_dir, date_str, note_path, date_error = _daily_note_path(target_date)
        if date_error is not None:
            return date_error
        if daily_dir is None or date_str is None or note_path is None:
            return "Не удалось удалить задачу: не удалось определить путь заметки"

        _ensure_daily_note(daily_dir, date_str, note_path)

        with open(note_path, "r", encoding="utf-8") as file:
            lines = file.readlines()

        task_index = _find_task_line_index(lines, clean_text)
        if task_index is None:
            return "Задача не найдена"

        lines.pop(task_index)

        with open(note_path, "w", encoding="utf-8") as file:
            file.writelines(lines)
    except OSError as error:
        return f"Ошибка файловой системы: {error}"

    return "Задача удалена"


def complete_daily_task(task_text: str = "", target_date: str | None = None) -> str:
    """Mark matching task as completed in today note"""
    clean_text = task_text.strip()
    if not clean_text:
        return "Не удалось завершить задачу: пустой текст задачи"

    try:
        daily_dir, date_str, note_path, date_error = _daily_note_path(target_date)
        if date_error is not None:
            return date_error
        if daily_dir is None or date_str is None or note_path is None:
            return "Не удалось завершить задачу: не удалось определить путь заметки"

        _ensure_daily_note(daily_dir, date_str, note_path)

        with open(note_path, "r", encoding="utf-8") as file:
            lines = file.readlines()

        task_index = _find_task_line_index(lines, clean_text)
        if task_index is None:
            return "Задача не найдена"

        line = lines[task_index]
        if "- [x]" in line.lower():
            return "Задача уже завершена"
        if "- [ ]" not in line:
            return "Задача не найдена"

        lines[task_index] = line.replace("- [ ]", "- [x]", 1)

        with open(note_path, "w", encoding="utf-8") as file:
            file.writelines(lines)
    except OSError as error:
        return f"Ошибка файловой системы: {error}"

    return "Задача отмечена как выполненная"


def add_daily_task_tool_schema() -> JSONSchema:
    """Build JSON schema for add_daily_task tool"""
    return {
        "type": "object",
        "properties": {
            "task_text": {
                "type": "string",
                "description": "Текст задачи, которую нужно добавить",
            },
            "target_date": {
                "type": "string",
                "description": TARGET_DATE_DESCRIPTION,
            }
        },
        "required": ["task_text"],
        "additionalProperties": False,
    }


def get_daily_tasks_tool_schema() -> JSONSchema:
    """Build JSON schema for get_daily_tasks tool"""
    return {
        "type": "object",
        "properties": {
            "target_date": {
                "type": "string",
                "description": TARGET_DATE_DESCRIPTION,
            }
        },
        "required": [],
        "additionalProperties": False,
    }


def complete_daily_task_tool_schema() -> JSONSchema:
    """Build JSON schema for complete_daily_task tool"""
    return {
        "type": "object",
        "properties": {
            "task_text": {
                "type": "string",
                "description": "Текст задачи, которую нужно отметить",
            },
            "target_date": {
                "type": "string",
                "description": TARGET_DATE_DESCRIPTION,
            }
        },
        "required": ["task_text"],
        "additionalProperties": False,
    }


def delete_daily_task_tool_schema() -> JSONSchema:
    """Build JSON schema for delete_daily_task tool"""
    return {
        "type": "object",
        "properties": {
            "task_text": {
                "type": "string",
                "description": "Текст задачи, которую нужно удалить",
            },
            "target_date": {
                "type": "string",
                "description": TARGET_DATE_DESCRIPTION,
            }
        },
        "required": ["task_text"],
        "additionalProperties": False,
    }


def register_obsidian_daily_tools(registry: ToolRegistry) -> None:
    """Register Obsidian tools in registry"""
    registry.register(
        name="add_daily_task",
        description="Добавляет задачу на сегодня",
        parameters=add_daily_task_tool_schema(),
        handler=add_daily_task,
    )
    registry.register(
        name="get_daily_tasks",
        description="Возвращает незавершенные задачи на сегодня",
        parameters=get_daily_tasks_tool_schema(),
        handler=get_daily_tasks,
    )
    registry.register(
        name="complete_daily_task",
        description="Отмечает задачу как выполненную",
        parameters=complete_daily_task_tool_schema(),
        handler=complete_daily_task,
    )
    registry.register(
        name="delete_daily_task",
        description="Удаляет задачу из списка на сегодня",
        parameters=delete_daily_task_tool_schema(),
        handler=delete_daily_task,
    )
