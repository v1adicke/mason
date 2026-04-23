"""Public Obsidian task command handlers"""

from __future__ import annotations

import os

from .io import _candidate_dates
from .io import _daily_note_path
from .io import _ensure_daily_note
from .io import _note_path_by_date
from .repository import _find_best_task_match


def add_daily_task(task_text: str = "", target_date: str | None = None) -> str:
    """Append an unchecked task to target Obsidian daily note"""
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
    """Return unchecked tasks from target Obsidian daily note"""
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


def delete_daily_task(task_text: str = "", target_date: str | None = None) -> str:
    """Delete matching task from target note"""
    clean_text = task_text.strip()
    if not clean_text:
        return "Не удалось удалить задачу: пустой текст задачи"

    try:
        match_result = _find_best_task_match(clean_text, target_date)
        if isinstance(match_result, str):
            return match_result

        note_path, task_index, lines = match_result
        lines.pop(task_index)

        with open(note_path, "w", encoding="utf-8") as file:
            file.writelines(lines)
    except OSError as error:
        return f"Ошибка файловой системы: {error}"

    return "Задача удалена"


def complete_daily_task(task_text: str = "", target_date: str | None = None) -> str:
    """Mark matching task as completed in target note"""
    clean_text = task_text.strip()
    if not clean_text:
        return "Не удалось завершить задачу: пустой текст задачи"

    try:
        match_result = _find_best_task_match(clean_text, target_date)
        if isinstance(match_result, str):
            return match_result

        note_path, task_index, lines = match_result

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
