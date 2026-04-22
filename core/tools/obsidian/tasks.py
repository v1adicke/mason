"""Task operations for Obsidian daily notes"""

from __future__ import annotations

from difflib import SequenceMatcher
import os
import re

from .io import _candidate_dates
from .io import _daily_note_path
from .io import _ensure_daily_note
from .io import _note_path_by_date


MIN_MATCH_SCORE = 0.6


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
        if score >= MIN_MATCH_SCORE:
            matches.append((index, candidate, score))

    matches.sort(key=lambda item: item[2], reverse=True)
    return matches


def _find_best_task_match(task_text: str, target_date: str | None) -> tuple[str, int, list[str]] | str:
    """Find best matching task and return note path, line index and file lines."""
    dates, date_error = _candidate_dates(target_date)
    if date_error is not None:
        return date_error
    if dates is None:
        return "Не удалось определить дату для поиска задачи"

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

        for index, candidate_text, score in _find_task_matches(lines, task_text):
            all_matches.append((candidate_date, candidate_text, index, score))

    if not all_matches:
        return "Задача не найдена"

    all_matches.sort(key=lambda item: item[3], reverse=True)
    best_score = all_matches[0][3]
    best_matches = [item for item in all_matches if abs(item[3] - best_score) < 1e-9]

    if len(best_matches) > 1:
        task_options = [
            f"[{match_date}] {task_text_candidate}"
            for match_date, task_text_candidate, _, _ in best_matches
        ]
        return f"Нашел несколько похожих задач, уточни какую именно: {task_options}"

    match_date, _, task_index, _ = best_matches[0]
    return note_path_by_date[match_date], task_index, file_lines_by_date[match_date]


def delete_daily_task(task_text: str = "", target_date: str | None = None) -> str:
    """Delete matching task from today note"""
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
    """Mark matching task as completed in today note"""
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
