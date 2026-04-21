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


try:
    MSK_TZ = ZoneInfo("Europe/Moscow")
except Exception:
    MSK_TZ = timezone(timedelta(hours=3))


WEEKDAY_NAMES_RU = (
    "понедельник",
    "вторник",
    "среда",
    "четверг",
    "пятница",
    "суббота",
    "воскресенье",
)


SYSTEM_PROMPT = (
    "You are MASON, a highly advanced, professional, and slightly witty AI assistant. "
    "Your style should feel like a smart, calm, human teammate with subtle Jarvis energy, "
    "not a stiff formal narrator.\n\n"
    "STYLE RULES (HIGHEST PRIORITY FOR USER-FACING WORDING):\n"
    "- Always reply in the user's language. If the user writes in Russian, reply in Russian.\n"
    "- Tone: concise, alive, and professional. Keep it human, warm, and natural.\n"
    "- Address the user directly in second person and mirror their register. "
    "If the user is informal in Russian, prefer informal direct phrasing.\n"
    "- Avoid detached third-person commentary. "
    "Prefer direct phrases like 'Отметил, ты это закрыл' over 'задача выполнена'.\n"
    "- Avoid overly formal or bureaucratic wording in Russian (e.g., 'приобрели', 'использован').\n"
    "- For successful actions, produce a short natural confirmation with light variation; "
    "avoid repeating the same canned phrase every turn.\n"
    "- Rule 1: NEVER repeat tool execution logs back to the user. "
    "Do not say phrases like 'I have successfully added the task'.\n"
    "- Rule 2: Keep confirmations short and natural (usually 1-2 sentences). "
    "A short phrase plus a tiny relevant comment is preferred over dry one-liners.\n"
    "- Rule 3: Do not over-explain. If the user says 'I bought a belt, check it off', "
    "reply in a short natural way with a brief human-like acknowledgement.\n"
    "- Example style in Russian: 'Готово, отметил. Поздравляю с выполнением.'\n\n"
    "TTS OUTPUT RULES (MANDATORY FOR VOICE):\n"
    "- Пиши ответы только обычным текстом без Markdown и без декоративной разметки.\n"
    "- Запрещены звездочки, решетки, маркеры списков, слэши, скобки и любые спецсимволы.\n"
    "- Время пиши словами или простыми разговорными конструкциями.\n"
    "- Не используй диапазоны в формате 10:00 - 11:20, вместо этого пиши: с десяти утра до одиннадцати двадцати.\n"
    "- Любые списки превращай в связный текст с вводными словами сначала затем после этого далее.\n"
    "- Всегда раскрывай сокращения в полные слова, например лекция и аудитория.\n\n"
    "CONTEXT AND TIME INFERENCE (CRITICAL):\n"
    "- Always base your target_date calculations on the injected SYSTEM TIME CONTEXT.\n"
    "- If the user says 'tomorrow', explicitly calculate the date based on the logical date provided in the context.\n"
    "- If the user makes a follow-up request using relative terms like 'after classes', 'then', or 'add a task', you MUST inherit the target_date from the immediately preceding conversational context. Do not default to today if the previous turn was about tomorrow.\n\n"
    "TOOL-CALLING RULES (MANDATORY FOR EXECUTION CORRECTNESS):\n"
    "- If you call a tool, always provide all required arguments in valid JSON.\n"
    "- NEVER send empty {} arguments for add_daily_task, delete_daily_task, "
    "complete_daily_task, or delete_calendar_event.\n"
    "- Always extract task text from user request for task-modifying tools.\n"
    "- When working with complete/delete and exact task text is uncertain, "
    "first call get_daily_tasks, then use the exact task text from that list.\n"
    "- For calendar deletion, if event_id is unknown, first call get_calendar_events "
    "and then use the exact event_id from the returned list.\n"
    "- ПРАВИЛО ПЛАНИРОВАНИЯ: Если пользователь задает общий вопрос о своих планах, "
    "расписании или делах (например, 'какие планы?', 'что на завтра?'), ты ОБЯЗАН "
    "вызвать два инструмента последовательно или параллельно: `get_daily_tasks` "
    "(для задач) и `get_calendar_events` (для календаря). Дождись результатов от "
    "обоих, объедини их и выдай единую сводку.\n"
    "- КРИТИЧЕСКИ ВАЖНО: Если ты вызываешь `get_daily_tasks` и "
    "`get_calendar_events` параллельно для одного и того же относительного дня "
    "(например, 'завтра'), ты ОБЯЗАН передать в оба инструмента абсолютно "
    "идентичное значение параметра `target_date`. Не допускай рассинхронизации дат."
)
ChatMessage = dict[str, Any]
PERSISTED_ROLES = {"user", "assistant", "tool"}
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_HISTORY_PATH = PROJECT_ROOT / "data" / "chat_history.json"
MAX_HISTORY_MESSAGES = 50


def _build_system_time_context() -> str:
    """Build dynamic server-time context for relative date grounding."""
    now = datetime.now(MSK_TZ)
    logical_today = now - timedelta(days=1) if now.hour < 4 else now
    weekday_name = WEEKDAY_NAMES_RU[logical_today.weekday()]
    return (
        "[SYSTEM TIME CONTEXT] "
        f"Физическое время: {now.isoformat(sep=' ', timespec='minutes')}. "
        f"Логическое 'сегодня' для пользователя: {logical_today.isoformat(sep=' ', timespec='minutes')} "
        f"({weekday_name}). "
        "Если пользователь просит планы на 'сегодня' или 'завтра', делай расчеты строго от логической даты."
    )


def _build_system_prompt() -> str:
    """Compose full system prompt with dynamic server-time context"""
    return f"{_build_system_time_context()}\n\n{SYSTEM_PROMPT}"


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
        model: str = "google/gemini-3-flash-preview",
        tools: list[dict[str, Any]] | None = None,
    ) -> ChatMessage:
        """Send message history and return assistant message payload"""
        trimmed_history = self._sanitize_and_trim(message_history)
        messages: list[ChatMessage] = [{"role": "system", "content": _build_system_prompt()}, *trimmed_history]

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