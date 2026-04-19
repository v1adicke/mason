"""Application entry point for MVP smoke test"""

from __future__ import annotations

import asyncio

from core.llm_client import LLMClient
from core.logger import setup_logger


async def _main() -> None:
    """Run a minimal request to the configured LLM"""
    logger = setup_logger()
    client = LLMClient()

    logger.info("Отправка тестового запроса...")
    try:
        answer = await client.ask("Системы в норме?")
    finally:
        await client.aclose()

    logger.info("Ответ: %s", answer)


if __name__ == "__main__":
    asyncio.run(_main())
