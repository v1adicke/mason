"""Application entry point for MVP smoke test"""

from __future__ import annotations

import asyncio

from core.llm_client import LLMClient
from core.logger import setup_logger
from core.tools import ToolRegistry, register_obsidian_daily_tools


async def _main() -> None:
    """Run a minimal request to the configured LLM"""
    logger = setup_logger()
    registry = ToolRegistry()
    register_obsidian_daily_tools(registry)
    client = LLMClient(tool_registry=registry)

    logger.info("Отправка тестового запроса с tool calling...")
    try:
        answer = await client.ask(
            prompt="Добавь задачу 'Проверить интеграцию с Обсидиан' на сегодня, а затем скажи, какие у меня вообще планы на день.",
            tools=registry.list_schemas(),
        )
    finally:
        await client.aclose()

    logger.info("Финальный ответ: %s", answer)


if __name__ == "__main__":
    asyncio.run(_main())
