"""Repository-like task lookup helpers for Obsidian notes"""

from __future__ import annotations

import os

from .io import _candidate_dates
from .io import _ensure_daily_note
from .io import _note_path_by_date
from .matching import _find_task_matches


def _find_best_task_match(task_text: str, target_date: str | None) -> tuple[str, int, list[str]] | str:
    """Find best matching task and return note path, line index and file lines"""
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
