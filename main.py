"""Application entry point for MVP smoke test"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from core.llm_client import LLMClient
from core.logger import setup_logger
from core.tools import ToolRegistry, register_obsidian_daily_tools


ChatMessage = dict[str, Any]
EXIT_COMMANDS = {"exit", "quit", "выход"}


def _parse_tool_arguments(raw_arguments: Any) -> dict[str, Any]:
    """Parse tool arguments from API payload"""
    if isinstance(raw_arguments, dict):
        return raw_arguments
    if isinstance(raw_arguments, str):
        try:
            payload = json.loads(raw_arguments)
        except json.JSONDecodeError:
            return {}
        if isinstance(payload, dict):
            return payload
    return {}


def _extract_last_user_message(history: list[ChatMessage]) -> str:
    """Return content of latest user message"""
    for message in reversed(history):
        role = message.get("role")
        content = message.get("content")
        if role == "user" and isinstance(content, str):
            return content
    return ""


def _extract_quoted_text(text: str) -> str | None:
    """Extract first quoted substring from text"""
    patterns = [r"'([^']+)'", r'"([^"]+)"', r"«([^»]+)»"]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            value = match.group(1).strip()
            if value:
                return value
    return None


def _extract_task_text_from_user_message(text: str) -> str | None:
    """Extract task text from natural language command"""
    quoted = _extract_quoted_text(text)
    if quoted:
        return quoted

    patterns = [
        r"(?i)^\s*добав[ьй]\s+задач[ауи]?\s+(.+?)\s*$",
        r"(?i)^\s*add\s+task\s+(.+?)\s*$",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            task_text = match.group(1).strip(" .!?\"'")
            if task_text:
                return task_text

    return None


async def _resolve_assistant_turn(
    *,
    client: LLMClient,
    registry: ToolRegistry,
    history: list[ChatMessage],
    tools: list[dict[str, Any]],
    logger_name: str,
) -> str:
    """Resolve one user turn including tool-call chain"""
    logger = setup_logger(logger_name)
    max_tool_rounds = 6

    for _ in range(max_tool_rounds):
        assistant_message = await client.ask(message_history=history, tools=tools)
        tool_calls_raw = assistant_message.get("tool_calls")
        tool_calls = tool_calls_raw if isinstance(tool_calls_raw, list) else []

        if not tool_calls:
            content = assistant_message.get("content")
            text = content if isinstance(content, str) else ""
            history.append({"role": "assistant", "content": text})
            return text

        history.append(assistant_message)
        for tool_call in tool_calls:
            if not isinstance(tool_call, dict):
                continue

            call_id = tool_call.get("id")
            function_payload = tool_call.get("function")
            if not isinstance(function_payload, dict):
                continue

            tool_name_raw = function_payload.get("name")
            tool_name = tool_name_raw if isinstance(tool_name_raw, str) else ""
            arguments = _parse_tool_arguments(function_payload.get("arguments"))

            if tool_name == "add_daily_task":
                task_text = arguments.get("task_text")
                if not isinstance(task_text, str) or not task_text.strip():
                    fallback_text = _extract_task_text_from_user_message(_extract_last_user_message(history))
                    if fallback_text:
                        arguments["task_text"] = fallback_text

            logger.info("Вызов инструмента: %s(%s)", tool_name, arguments)
            if not tool_name:
                result = "Ошибка вызова инструмента: пустое имя инструмента"
            else:
                try:
                    result = registry.execute(tool_name, arguments)
                except KeyError as error:
                    result = f"Ошибка вызова инструмента: {error}"
            logger.info("Результат инструмента %s: %s", tool_name, result)

            history.append(
                {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "name": tool_name,
                    "content": result,
                }
            )

    fallback = "Не удалось завершить цепочку инструментов за отведенное число шагов"
    history.append({"role": "assistant", "content": fallback})
    return fallback


async def _main() -> None:
    """Run interactive CLI chat with persistent context"""
    logger = setup_logger()
    registry = ToolRegistry()
    register_obsidian_daily_tools(registry)
    client = LLMClient()
    tools = registry.list_schemas()
    history: list[ChatMessage] = []

    logger.info("CLI запущен. Для выхода отправьте: exit | quit | выход")
    try:
        while True:
            try:
                user_input = input("\n❯ ").strip()
            except EOFError:
                break

            if user_input.lower() in EXIT_COMMANDS:
                break
            if not user_input:
                continue

            history.append({"role": "user", "content": user_input})
            response_text = await _resolve_assistant_turn(
                client=client,
                registry=registry,
                history=history,
                tools=tools,
                logger_name="mason",
            )
            print(f"Mason: {response_text}")
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(_main())
