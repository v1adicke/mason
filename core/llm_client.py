"""Async wrapper for OpenAI compatible API"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI

from .config import get_settings
from .llm.history_store import DEFAULT_HISTORY_PATH
from .llm.history_store import clear_history_file
from .llm.history_store import load_history_from_file
from .llm.history_store import save_history_to_file
from .llm.messages import ChatMessage
from .llm.messages import extract_text
from .llm.messages import sanitize_and_trim
from .llm.prompt_context import build_system_prompt


_HEAVY_KEYWORDS: frozenset[str] = frozenset({
    "проанализируй",
    "составь сводку",
    "сделай ресерч",
    "изучи",
    "сравни",
    "исследуй",
    "подготовь отчёт",
    "подготовь отчет",
    "синтезируй",
    "обобщи",
})

_HEAVY_TOOL_CONTENT_THRESHOLD = 15_000


def _requires_heavy_model(user_message: str, current_history: list[dict[str, Any]]) -> bool:
    """Return True when the request warrants the heavy model"""
    lowered = user_message.lower()
    if any(kw in lowered for kw in _HEAVY_KEYWORDS):
        return True

    total_tool_chars = sum(
        len(msg.get("content") or "")
        for msg in current_history
        if msg.get("role") == "tool"
    )
    return total_tool_chars > _HEAVY_TOOL_CONTENT_THRESHOLD


class LLMClient:
    """Client for text prompts via chat completions"""

    def __init__(
        self,
        history_path: Path = DEFAULT_HISTORY_PATH,
        max_history_messages: int | None = None,
    ) -> None:
        """Initialize async API client from project settings"""
        settings = get_settings()
        self._settings = settings
        self._logger = logging.getLogger("mason")
        self._client = AsyncOpenAI(
            api_key=self._settings.openai_api_key,
            base_url=self._settings.openai_base_url,
        )
        self._history_path = history_path
        effective_history_limit = max_history_messages
        if effective_history_limit is None:
            effective_history_limit = self._settings.mason_max_history_length
        self._max_history_messages = max(1, effective_history_limit)
        self._history: list[ChatMessage] = load_history_from_file(
            history_path=self._history_path,
            max_history_messages=self._max_history_messages,
            logger=self._logger,
        )

    @property
    def history(self) -> list[ChatMessage]:
        """Return mutable in-memory chat history"""
        return self._history

    def save_history(self, history: list[ChatMessage] | None = None) -> None:
        """Persist chat history to JSON file with trimming and sanitization"""
        source = history if history is not None else self._history
        sanitized = save_history_to_file(
            history_path=self._history_path,
            history=source,
            max_history_messages=self._max_history_messages,
            logger=self._logger,
        )

        self._history.clear()
        self._history.extend(sanitized)

    def clear_history(self) -> None:
        """Clear in-memory history and truncate persisted history file"""
        self._history.clear()
        clear_history_file(history_path=self._history_path, logger=self._logger)

    async def ask(
        self,
        message_history: list[ChatMessage],
        model: str | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> ChatMessage:
        """Send message history and return assistant message payload"""
        trimmed_history = sanitize_and_trim(message_history, self._max_history_messages)
        messages: list[ChatMessage] = [
            {
                "role": "system",
                "content": build_system_prompt(
                    system_prompt=self._settings.mason_system_prompt,
                    timezone_name=self._settings.mason_timezone,
                    cutoff_hour=self._settings.mason_night_owl_cutoff_hour,
                ),
            },
            *trimmed_history,
        ]

        if model:
            selected_model = model
        elif (
            self._settings.openai_heavy_model
            and _requires_heavy_model(
                trimmed_history[-1].get("content") or "" if trimmed_history else "",
                trimmed_history,
            )
        ):
            selected_model = self._settings.openai_heavy_model
            self._logger.info("Переключаюсь на тяжёлую модель: %s", selected_model)
        else:
            selected_model = self._settings.openai_model

        completion_payload: dict[str, Any] = {
            "model": selected_model,
            "messages": messages,
        }
        if tools:
            completion_payload["tools"] = tools
            completion_payload["tool_choice"] = "auto"

        completion = await self._client.chat.completions.create(**completion_payload)
        message = completion.choices[0].message

        assistant_message: ChatMessage = {
            "role": "assistant",
            "content": extract_text(message.content),
        }
        if message.tool_calls:
            assistant_message["tool_calls"] = [
                {
                    "id": call.id,
                    "type": call.type,
                    "function": {
                        "name": call.function.name,
                        "arguments": call.function.arguments,
                    },
                }
                for call in message.tool_calls
            ]

        return assistant_message

    async def aclose(self) -> None:
        """Close underlying HTTP resources"""
        await self._client.close()