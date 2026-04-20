"""Async wrapper for OpenAI compatible API"""

from __future__ import annotations

from typing import Any

from openai import AsyncOpenAI

from .config import get_settings


SYSTEM_PROMPT = (
    "Ты ядро локального ассистента. Отвечай кратко. "
    "ВАЖНО: Если ты вызываешь инструмент (tool), ты ОБЯЗАН передать ему все требуемые "
    "аргументы в формате JSON. НИКОГДА не отправляй пустые аргументы {} для "
    "инструментов add_daily_task, delete_daily_task и complete_daily_task. "
    "Обязательно извлекай текст задачи из запроса пользователя."
)
ChatMessage = dict[str, Any]


class LLMClient:
    """Client for text prompts via chat completions"""

    def __init__(self) -> None:
        """Initialize async API client from project settings"""
        settings = get_settings()
        self._client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )

    async def ask(
        self,
        message_history: list[ChatMessage],
        model: str = "xiaomi/mimo-v2-flash",
        tools: list[dict[str, Any]] | None = None,
    ) -> ChatMessage:
        """Send message history and return assistant message payload"""
        messages: list[ChatMessage] = [{"role": "system", "content": SYSTEM_PROMPT}, *message_history]

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
