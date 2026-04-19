"""Async wrapper for OpenAI-compatible API"""

from __future__ import annotations

import json
import logging
from typing import Any

from openai import AsyncOpenAI

from .config import get_settings
from .tools import ToolRegistry


class LLMClient:
    """Client for text prompts via chat completions"""

    def __init__(self, tool_registry: ToolRegistry | None = None) -> None:
        """Initialize async API client from project settings"""
        settings = get_settings()
        self._client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )
        self._tool_registry = tool_registry
        self._logger = logging.getLogger("mason")

    async def ask(
        self,
        prompt: str,
        model: str = "gpt-5.3-codex",
        tools: list[dict[str, Any]] | None = None,
    ) -> str:
        """Send a prompt and return the assistant response text"""
        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": "Ты ядро локального ассистента. Отвечай кратко.",
            },
            {"role": "user", "content": prompt},
        ]

        completion_payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
        }
        if tools:
            completion_payload["tools"] = tools
            completion_payload["tool_choice"] = "auto"

        completion = await self._client.chat.completions.create(**completion_payload)
        message = completion.choices[0].message

        if message.tool_calls and self._tool_registry is not None:
            messages.append(
                {
                    "role": "assistant",
                    "content": message.content or "",
                    "tool_calls": [
                        {
                            "id": call.id,
                            "type": call.type,
                            "function": {
                                "name": call.function.name,
                                "arguments": call.function.arguments,
                            },
                        }
                        for call in message.tool_calls
                    ],
                }
            )

            for call in message.tool_calls:
                arguments = self._parse_arguments(call.function.arguments)
                self._logger.info("Вызов инструмента: %s(%s)", call.function.name, arguments)
                result = self._tool_registry.execute(call.function.name, arguments)
                self._logger.info("Результат инструмента %s: %s", call.function.name, result)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "name": call.function.name,
                        "content": result,
                    }
                )

            follow_up_payload: dict[str, Any] = {
                "model": model,
                "messages": messages,
            }
            if tools:
                follow_up_payload["tools"] = tools

            follow_up = await self._client.chat.completions.create(**follow_up_payload)
            return self._extract_text(follow_up.choices[0].message.content)

        return self._extract_text(message.content)

    @staticmethod
    def _parse_arguments(raw_arguments: str | None) -> dict[str, Any]:
        """Parse JSON arguments from tool calls"""
        if not raw_arguments:
            return {}

        try:
            payload = json.loads(raw_arguments)
        except json.JSONDecodeError:
            return {}

        if isinstance(payload, dict):
            return payload
        return {}

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
