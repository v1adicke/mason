"""Application entry point for MVP smoke test"""

from __future__ import annotations

import asyncio

from core.llm_client import LLMClient
from core.logger import setup_logger
from core.tools import ToolRegistry, get_system_time, system_time_tool_schema


async def _main() -> None:
    """Run a minimal request to the configured LLM"""
    logger = setup_logger()
    registry = ToolRegistry()
    registry.register(
        name="get_system_time",
        description="Возвращает текущее локальное время",
        parameters=system_time_tool_schema(),
        handler=get_system_time,
    )
    client = LLMClient(tool_registry=registry)

    logger.info("Отправка тестового запроса с tool calling...")
    try:
        answer = await client.ask(
            prompt="Мейсон, какое сейчас точное время?",
            tools=registry.list_schemas(),
        )
    finally:
        await client.aclose()

    logger.info("Финальный ответ: %s", answer)


if __name__ == "__main__":
    asyncio.run(_main())
