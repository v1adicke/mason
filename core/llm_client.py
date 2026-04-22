"""Async wrapper for OpenAI compatible API"""

from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from datetime import timezone
import json
import logging
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from openai import AsyncOpenAI

from .config import get_settings

WEEKDAY_NAMES_RU = (
    "понедельник",
    "вторник",
    "среда",
    "четверг",
    "пятница",
    "суббота",
    "воскресенье",
)


def _resolve_timezone(timezone_name: str) -> Any:
    """Resolve timezone by name with UTC fallback"""
    try:
        return ZoneInfo(timezone_name)
    except Exception:
        return timezone.utc


def _resolve_current_time_context(timezone_name: str, cutoff_hour: int) -> tuple[datetime, datetime]:
    """Resolve physical now and logical date-time with night-owl offset."""
    timezone_value = _resolve_timezone(timezone_name)
    now = datetime.now(timezone_value)
    logical_now = now - timedelta(days=1) if now.hour < cutoff_hour else now
    return now, logical_now


def _build_date_inference_rule(now: datetime, logical_now: datetime) -> str:
    """Build strict date-inference rule for tool-calling date resolution."""
    return (
        "DATE INFERENCE RULE:\n"
        f"Current logical date: {logical_now.date().isoformat()} (YYYY-MM-DD)\n"
        f"Current physical time: {now.isoformat(sep=' ', timespec='minutes')}\n"
        "Your task is to natively resolve all relative timeframes ('завтра', 'послезавтра', 'в среду') "
        "based on the Current logical date. When calling tools, you MUST pass the resolved date "
        "in strict YYYY-MM-DD format."
    )
ChatMessage = dict[str, Any]
PERSISTED_ROLES = {"user", "assistant", "tool"}
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_HISTORY_PATH = PROJECT_ROOT / "data" / "chat_history.json"


def _build_system_time_context(now: datetime, logical_now: datetime) -> str:
    """Build dynamic server-time context for relative date grounding."""
    weekday_name = WEEKDAY_NAMES_RU[logical_now.weekday()]
    return (
        "[SYSTEM TIME CONTEXT] "
        f"Физическое время: {now.isoformat(sep=' ', timespec='minutes')}. "
        f"Логическое 'сегодня' для пользователя: {logical_now.isoformat(sep=' ', timespec='minutes')} "
        f"({weekday_name}). "
        "Если пользователь просит планы на 'сегодня' или 'завтра', делай расчеты строго от логической даты."
    )


def _build_system_prompt(system_prompt: str, timezone_name: str, cutoff_hour: int) -> str:
    """Compose full system prompt with dynamic server-time context"""
    now, logical_now = _resolve_current_time_context(timezone_name, cutoff_hour)
    time_context = _build_system_time_context(now, logical_now)
    date_inference_rule = _build_date_inference_rule(now, logical_now)
    return f"{time_context}\n\n{date_inference_rule}\n\n{system_prompt}"


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
        model: str | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> ChatMessage:
        """Send message history and return assistant message payload"""
        trimmed_history = self._sanitize_and_trim(message_history)
        messages: list[ChatMessage] = [
            {
                "role": "system",
                "content": _build_system_prompt(
                    system_prompt=self._settings.mason_system_prompt,
                    timezone_name=self._settings.mason_timezone,
                    cutoff_hour=self._settings.mason_night_owl_cutoff_hour,
                ),
            },
            *trimmed_history,
        ]

        selected_model = model or self._settings.openai_model

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