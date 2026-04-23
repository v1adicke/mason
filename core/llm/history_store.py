"""Persistent chat history helpers"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .messages import ChatMessage
from .messages import sanitize_and_trim


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_HISTORY_PATH = PROJECT_ROOT / "data" / "chat_history.json"


def load_history_from_file(
    history_path: Path,
    max_history_messages: int,
    logger: logging.Logger,
) -> list[ChatMessage]:
    """Load chat history from JSON file if it exists"""
    try:
        history_path.parent.mkdir(parents=True, exist_ok=True)
        if not history_path.exists():
            return []

        with open(history_path, "r", encoding="utf-8") as file:
            payload = json.load(file)
    except json.JSONDecodeError as error:
        logger.warning("Файл истории поврежден, история сброшена: %s", error)
        return []
    except OSError as error:
        logger.warning("Не удалось загрузить историю чата: %s", error)
        return []

    if not isinstance(payload, list):
        logger.warning("Неверный формат истории чата, ожидался JSON-массив")
        return []

    return sanitize_and_trim(payload, max_history_messages)


def save_history_to_file(
    history_path: Path,
    history: list[ChatMessage],
    max_history_messages: int,
    logger: logging.Logger,
) -> list[ChatMessage]:
    """Persist sanitized history and return the saved message list"""
    sanitized = sanitize_and_trim(history, max_history_messages)

    try:
        history_path.parent.mkdir(parents=True, exist_ok=True)
        with open(history_path, "w", encoding="utf-8") as file:
            json.dump(sanitized, file, ensure_ascii=False, indent=2)
    except OSError as error:
        logger.warning("Не удалось сохранить историю чата: %s", error)

    return sanitized


def clear_history_file(history_path: Path, logger: logging.Logger) -> None:
    """Truncate persisted history file"""
    try:
        history_path.parent.mkdir(parents=True, exist_ok=True)
        with open(history_path, "w", encoding="utf-8") as file:
            json.dump([], file, ensure_ascii=False, indent=2)
    except OSError as error:
        logger.warning("Не удалось очистить файл истории чата: %s", error)
