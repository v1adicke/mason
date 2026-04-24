"""UI helpers: local heuristic fillers for immediate feedback before LLM responds"""

from __future__ import annotations

import random


_FILLER_PHRASES: dict[str, list[str]] = {
    "read": [
        "Так, смотрю...",
        "Сейчас гляну...",
        "Лезем в данные...",
        "Дай-ка проверю...",
    ],
    "write": [
        "Записываю...",
        "Добавляю...",
        "Сек, фиксирую...",
        "Принято, пишу...",
    ],
    "delete": [
        "Сношу...",
        "Удаляю...",
        "Минутку, вычеркиваю...",
        "Сделаем...",
    ],
    "fallback": [
        "Секунду...",
        "Принято, думаю...",
        "Обрабатываю...",
        "Минутку...",
    ],
}

_INTENT_KEYWORDS: dict[str, list[str]] = {
    "read":   ["планы", "календарь", "что", "задачи", "покажи"],
    "write":  ["добавь", "создай", "запиши", "напомни"],
    "delete": ["удали", "сотри", "убери", "выполнил"],
}


def get_quick_filler(user_text: str) -> str:
    """Return a random contextual filler phrase based on user input keywords"""
    lowered = user_text.lower()
    for intent, keywords in _INTENT_KEYWORDS.items():
        if any(kw in lowered for kw in keywords):
            return random.choice(_FILLER_PHRASES[intent])
    return random.choice(_FILLER_PHRASES["fallback"])
