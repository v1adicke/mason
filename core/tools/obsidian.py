"""Obsidian daily task tools"""

from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from difflib import SequenceMatcher
import os
import re
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

CRITICAL_TASK_MATCHING_STRATEGY = (
    "CRITICAL STRATEGY: DO NOT guess the exact task text. If you do not have the exact "
    "text of the task in your immediate short-term memory, you MUST call `get_daily_tasks` "
    "FIRST to read the current tasks for the target date. Then, find the semantically "
    "matching task from that list and use its EXACT text."
)

DEFAULT_FORWARD_SCAN_DAYS = 14


def _resolve_date_str(target_date: str | None = None) -> tuple[str | None, str | None]:
    """Resolve target date or return validation error"""
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
    """Build daily note paths for target date"""
    settings = get_settings()
    date_str, date_error = _resolve_date_str(target_date)
    if date_error is not None or date_str is None:
        return settings.obsidian_daily_path, None, None, date_error

    note_path = os.path.join(settings.obsidian_daily_path, f"{date_str}.md")
    return settings.obsidian_daily_path, date_str, note_path, None


def _candidate_dates(target_date: str | None = None, days_forward: int = DEFAULT_FORWARD_SCAN_DAYS) -> tuple[list[str] | None, str | None]:
    """Build candidate date list for task scanning"""
    if target_date is not None and target_date.strip():
        date_str, date_error = _resolve_date_str(target_date)
        if date_error is not None or date_str is None:
            return None, date_error
        return [date_str], None

    today = datetime.now().date()
    dates = [(today + timedelta(days=offset)).isoformat() for offset in range(days_forward + 1)]
    return dates, None


def _note_path_by_date(date_str: str) -> tuple[str, str]:
    """Build note path for known valid date string"""
    settings = get_settings()
    return settings.obsidian_daily_path, os.path.join(settings.obsidian_daily_path, f"{date_str}.md")


def _ensure_daily_note(daily_dir: str, date_str: str, note_path: str) -> None:
    """Create daily note file with base template if it does not exist"""
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
        if target_date is not None and target_date.strip():
            daily_dir, date_str, note_path, date_error = _daily_note_path(target_date)
            if date_error is not None:
                return date_error
            if daily_dir is None or date_str is None or note_path is None:
                return "Не удалось получить задачи: не удалось определить путь заметки"

            _ensure_daily_note(daily_dir, date_str, note_path)

            with open(note_path, "r", encoding="utf-8") as file:
                task_lines = [line.strip() for line in file if "- [ ]" in line]
            if not task_lines:
                return "На сегодня задач пока нет"
            return "\n".join(task_lines)

        dates, date_error = _candidate_dates(target_date)
        if date_error is not None:
            return date_error
        if dates is None:
            return "Не удалось получить задачи: не удалось определить диапазон дат"

        aggregated_tasks: list[str] = []
        for candidate_date in dates:
            _, note_path = _note_path_by_date(candidate_date)
            if not os.path.exists(note_path):
                continue

            with open(note_path, "r", encoding="utf-8") as file:
                for line in file:
                    if "- [ ]" in line:
                        aggregated_tasks.append(f"[{candidate_date}] {line.strip()}")

        if not aggregated_tasks:
            return "На сегодня и ближайшие дни задач пока нет"

        return "\n".join(aggregated_tasks)
    except OSError as error:
        return f"Ошибка файловой системы: {error}"


def _extract_task_text(line: str) -> str:
    """Extract pure task text from markdown checkbox line"""
    clean_line = line.strip()
    if clean_line.startswith("- [ ] ") or clean_line.startswith("- [x] "):
        return clean_line[6:].strip()
    return clean_line


def _normalize_text(value: str) -> str:
    """Normalize text for fuzzy task matching"""
    lowered = value.lower().strip()
    return re.sub(r"[^a-zа-я0-9\s]", " ", lowered, flags=re.IGNORECASE)


def _task_match_score(query: str, candidate: str) -> float:
    """Calculate similarity score between query and candidate task"""
    query_norm = _normalize_text(query)
    candidate_norm = _normalize_text(candidate)
    if not query_norm or not candidate_norm:
        return 0.0

    if query_norm in candidate_norm or candidate_norm in query_norm:
        return 1.0

    return SequenceMatcher(a=query_norm, b=candidate_norm).ratio()


def _find_task_matches(lines: list[str], task_text: str) -> list[tuple[int, str, float]]:
    """Find matching checkbox tasks by substring and fuzzy similarity"""
    matches: list[tuple[int, str, float]] = []
    for index, line in enumerate(lines):
        line_lower = line.lower()
        if "- [ ]" not in line_lower and "- [x]" not in line_lower:
            continue

        candidate = _extract_task_text(line)
        score = _task_match_score(task_text, candidate)
        if score >= 0.6:
            matches.append((index, candidate, score))

    matches.sort(key=lambda item: item[2], reverse=True)
    return matches


def delete_daily_task(task_text: str = "", target_date: str | None = None) -> str:
    """Delete matching task from today note"""
    clean_text = task_text.strip()
    if not clean_text:
        return "Не удалось удалить задачу: пустой текст задачи"

    try:
        dates, date_error = _candidate_dates(target_date)
        if date_error is not None:
            return date_error
        if dates is None:
            return "Не удалось удалить задачу: не удалось определить диапазон дат"

        all_matches: list[tuple[str, str, int, float]] = []
        file_lines_by_date: dict[str, list[str]] = {}
        note_path_by_date: dict[str, str] = {}

        for candidate_date in dates:
            daily_dir, note_path = _note_path_by_date(candidate_date)
            if target_date is not None and target_date.strip():
                _ensure_daily_note(daily_dir, candidate_date, note_path)
            if not os.path.exists(note_path):
                continue

            with open(note_path, "r", encoding="utf-8") as file:
                lines = file.readlines()

            file_lines_by_date[candidate_date] = lines
            note_path_by_date[candidate_date] = note_path

            for index, candidate_text, score in _find_task_matches(lines, clean_text):
                all_matches.append((candidate_date, candidate_text, index, score))

        if not all_matches:
            return "Задача не найдена"

        all_matches.sort(key=lambda item: item[3], reverse=True)
        best_score = all_matches[0][3]
        best_matches = [item for item in all_matches if abs(item[3] - best_score) < 1e-9]

        if len(best_matches) > 1:
            task_options = [f"[{match_date}] {task_text_candidate}" for match_date, task_text_candidate, _, _ in best_matches]
            return f"Error: Multiple matching tasks found. Please specify. {task_options}"

        match_date, _, task_index, _ = best_matches[0]
        lines = file_lines_by_date[match_date]
        lines.pop(task_index)

        with open(note_path_by_date[match_date], "w", encoding="utf-8") as file:
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
        dates, date_error = _candidate_dates(target_date)
        if date_error is not None:
            return date_error
        if dates is None:
            return "Не удалось завершить задачу: не удалось определить диапазон дат"

        all_matches: list[tuple[str, str, int, float]] = []
        file_lines_by_date: dict[str, list[str]] = {}
        note_path_by_date: dict[str, str] = {}

        for candidate_date in dates:
            daily_dir, note_path = _note_path_by_date(candidate_date)
            if target_date is not None and target_date.strip():
                _ensure_daily_note(daily_dir, candidate_date, note_path)
            if not os.path.exists(note_path):
                continue

            with open(note_path, "r", encoding="utf-8") as file:
                lines = file.readlines()

            file_lines_by_date[candidate_date] = lines
            note_path_by_date[candidate_date] = note_path

            for index, candidate_text, score in _find_task_matches(lines, clean_text):
                all_matches.append((candidate_date, candidate_text, index, score))

        if not all_matches:
            return "Задача не найдена"

        all_matches.sort(key=lambda item: item[3], reverse=True)
        best_score = all_matches[0][3]
        best_matches = [item for item in all_matches if abs(item[3] - best_score) < 1e-9]

        if len(best_matches) > 1:
            task_options = [f"[{match_date}] {task_text_candidate}" for match_date, task_text_candidate, _, _ in best_matches]
            return f"Error: Multiple matching tasks found. Please specify. {task_options}"

        match_date, _, task_index, _ = best_matches[0]
        lines = file_lines_by_date[match_date]

        line = lines[task_index]
        if "- [x]" in line.lower():
            return "Задача уже завершена"
        if "- [ ]" not in line:
            return "Задача не найдена"

        lines[task_index] = line.replace("- [ ]", "- [x]", 1)

        with open(note_path_by_date[match_date], "w", encoding="utf-8") as file:
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
        "description": CRITICAL_TASK_MATCHING_STRATEGY,
        "properties": {
            "task_text": {
                "type": "string",
                "description": (
                    "Текст задачи, которую нужно отметить "
                    + CRITICAL_TASK_MATCHING_STRATEGY
                ),
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
        "description": CRITICAL_TASK_MATCHING_STRATEGY,
        "properties": {
            "task_text": {
                "type": "string",
                "description": (
                    "Текст задачи, которую нужно удалить "
                    + CRITICAL_TASK_MATCHING_STRATEGY
                ),
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
        description=(
            "Отмечает задачу как выполненную " + CRITICAL_TASK_MATCHING_STRATEGY
        ),
        parameters=complete_daily_task_tool_schema(),
        handler=complete_daily_task,
    )
    registry.register(
        name="delete_daily_task",
        description=(
            "Удаляет задачу из списка на сегодня " + CRITICAL_TASK_MATCHING_STRATEGY
        ),
        parameters=delete_daily_task_tool_schema(),
        handler=delete_daily_task,
    )
