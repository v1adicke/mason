"""Async wrapper for OpenAI compatible API"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI

from .config import get_settings


SYSTEM_PROMPT = (
    "Ты ядро локального ассистента. Отвечай кратко. "
    "ВАЖНО: Если ты вызываешь инструмент (tool), ты ОБЯЗАН передать ему все требуемые "
    "аргументы в формате JSON. НИКОГДА не отправляй пустые аргументы {} для "
    "инструментов add_daily_task, delete_daily_task и complete_daily_task. "
    "Обязательно извлекай текст задачи из запроса пользователя. "
    "When asked to interact with daily tasks (complete/delete), always act as a "
    "defensive system: verify the exact task name by reading the task list first if "
    "you are unsure."
)
ChatMessage = dict[str, Any]
PERSISTED_ROLES = {"user", "assistant", "tool"}
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_HISTORY_PATH = PROJECT_ROOT / "data" / "chat_history.json"
MAX_HISTORY_MESSAGES = 50


class LLMClient:
    """Client for text prompts via chat completions"""

    def __init__(
        self,
        history_path: Path = DEFAULT_HISTORY_PATH,
        max_history_messages: int = MAX_HISTORY_MESSAGES,
    ) -> None:
        """Initialize async API client from project settings"""
        settings = get_settings()
        self._logger = logging.getLogger("mason")
        self._client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )
        self._history_path = history_path
        self._max_history_messages = max(1, max_history_messages)
        self._history: list[ChatMessage] = self._load_history()

    @property
    def history(self) -> list[ChatMessage]:
        """Return mutable in-memory chat history"""
        return self._history

    def save_history(self, history: list[ChatMessage] | None = None) -> None:
        """Persist chat history to JSON file with trimming and sanitization"""
        source = history if history is not None else self._history
        sanitized = self._sanitize_and_trim(source)

        self._history.clear()
        self._history.extend(sanitized)

        try:
            self._history_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._history_path, "w", encoding="utf-8") as file:
                json.dump(sanitized, file, ensure_ascii=False, indent=2)
        except OSError as error:
            self._logger.warning("Не удалось сохранить историю чата: %s", error)

    def clear_history(self) -> None:
        """Clear in-memory history and truncate persisted history file"""
        self._history.clear()
        try:
            self._history_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._history_path, "w", encoding="utf-8") as file:
                json.dump([], file, ensure_ascii=False, indent=2)
        except OSError as error:
            self._logger.warning("Не удалось очистить файл истории чата: %s", error)

    def _load_history(self) -> list[ChatMessage]:
        """Load chat history from JSON file if it exists"""
        try:
            self._history_path.parent.mkdir(parents=True, exist_ok=True)
            if not self._history_path.exists():
                return []

            with open(self._history_path, "r", encoding="utf-8") as file:
                payload = json.load(file)
        except json.JSONDecodeError as error:
            self._logger.warning("Файл истории поврежден, история сброшена: %s", error)
            return []
        except OSError as error:
            self._logger.warning("Не удалось загрузить историю чата: %s", error)
            return []

        if not isinstance(payload, list):
            self._logger.warning("Неверный формат истории чата, ожидался JSON-массив")
            return []

        return self._sanitize_and_trim(payload)

    def _sanitize_and_trim(self, messages: list[Any]) -> list[ChatMessage]:
        """Filter unsupported payload and keep only recent valid messages"""
        sanitized: list[ChatMessage] = []
        for raw_message in messages:
            if not isinstance(raw_message, dict):
                continue

            role = raw_message.get("role")
            if role not in PERSISTED_ROLES:
                continue

            content = raw_message.get("content", "")
            if not isinstance(content, str):
                content = str(content)

            message: ChatMessage = {
                "role": role,
                "content": content,
            }

            if role == "assistant":
                tool_calls = raw_message.get("tool_calls")
                if isinstance(tool_calls, list):
                    message["tool_calls"] = tool_calls

            if role == "tool":
                tool_call_id = raw_message.get("tool_call_id")
                name = raw_message.get("name")
                if not isinstance(tool_call_id, str) or not isinstance(name, str):
                    continue
                message["tool_call_id"] = tool_call_id
                message["name"] = name

            sanitized.append(message)

        if len(sanitized) > self._max_history_messages:
            return sanitized[-self._max_history_messages :]
        return sanitized

    async def ask(
        self,
        message_history: list[ChatMessage],
        model: str = "xiaomi/mimo-v2-flash",
        tools: list[dict[str, Any]] | None = None,
    ) -> ChatMessage:
        """Send message history and return assistant message payload"""
        trimmed_history = self._sanitize_and_trim(message_history)
        messages: list[ChatMessage] = [{"role": "system", "content": SYSTEM_PROMPT}, *trimmed_history]

        completion_payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
        }
        if tools:
            completion_payload["tools"] = tools
            completion_payload["tool_choice"] = "auto"

        completion = await self._client.chat.completions.create(**completion_payload)
        message = completion.choices[0].message

        assistant_message: ChatMessage = {
            "role": "assistant",
            "content": self._extract_text(message.content),
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

    @staticmethod
    def _extract_text(content: Any) -> str:
        """Extract text content from OpenAI message payload"""
        if isinstance(content, str):
            return content.strip()
        if content is None:
            return ""

        parts: list[str] = []
        for item in content:
            text = getattr(item, "text", None)
            if isinstance(text, str):
                parts.append(text)
        return "\n".join(parts).strip()

    async def aclose(self) -> None:
        """Close underlying HTTP resources"""
        await self._client.close()
