"""Async wrapper for OpenAI-compatible API"""

from __future__ import annotations

from typing import Any

from openai import AsyncOpenAI

from .config import get_settings


class LLMClient:
    """Client for text prompts via chat completions"""

    def __init__(self) -> None:
        """Initialize async API client from project settings"""
        settings = get_settings()
        self._client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )

    async def ask(self, prompt: str, model: str = "gpt-5.3-codex") -> str:
        """Send a prompt and return the assistant response text"""
        completion = await self._client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "Ты ядро локального ассистента. Отвечай кратко.",
                },
                {"role": "user", "content": prompt},
            ],
        )

        content: Any = completion.choices[0].message.content
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
