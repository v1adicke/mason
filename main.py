"""Application entry point for MVP smoke test"""

from __future__ import annotations

import asyncio
import json
from datetime import date
import re
from typing import Any

from core.llm_client import LLMClient
from core.logger import setup_logger
from core.tools import ToolRegistry, register_calendar_tools, register_obsidian_daily_tools, register_obsidian_vault_tools
from core.ui import get_quick_filler


ChatMessage = dict[str, Any]
EXIT_COMMANDS = {"exit", "quit", "выход"}
CLEAR_COMMANDS = {"/clear"}


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


def _extract_iso_date(text: str) -> str | None:
    """Extract first valid ISO date from message text"""
    match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text)
    if match is None:
        return None

    date_text = match.group(1)
    try:
        date.fromisoformat(date_text)
    except ValueError:
        return None
    return date_text


def _extract_latest_tool_target_date(executed_tools: list[dict[str, Any]]) -> str | None:
    """Return latest valid target_date from executed Obsidian tools"""
    obsidian_tools = {
        "add_daily_task",
        "get_daily_tasks",
        "complete_daily_task",
        "delete_daily_task",
    }

    for event in reversed(executed_tools):
        name = event.get("name")
        if name not in obsidian_tools:
            continue

        arguments = event.get("arguments")
        if not isinstance(arguments, dict):
            continue

        target_date = arguments.get("target_date")
        if isinstance(target_date, str) and _extract_iso_date(target_date) == target_date:
            return target_date

    return None


def _normalize_response_dates(text: str, executed_tools: list[dict[str, Any]]) -> str:
    """Replace any ISO date in assistant text with factual date from tool call"""
    factual_date = _extract_latest_tool_target_date(executed_tools)
    if factual_date is None:
        return text

    return re.sub(r"\b\d{4}-\d{2}-\d{2}\b", factual_date, text)


def _has_successful_task_action(executed_tools: list[dict[str, Any]]) -> bool:
    """Return True when at least one mutation tool finished successfully"""
    for event in executed_tools:
        name = event.get("name")
        result = event.get("result")
        if not isinstance(result, str):
            continue

        if name == "add_daily_task" and result.startswith("Задача успешно добавлена"):
            return True
        if name == "complete_daily_task" and result.startswith("Задача отмечена как выполненная"):
            return True
        if name == "delete_daily_task" and result.startswith("Задача удалена"):
            return True
        if name == "add_calendar_event" and result.startswith("Событие добавлено"):
            return True
        if name == "delete_calendar_event" and result.startswith("Событие удалено"):
            return True

    return False


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
    executed_tools: list[dict[str, Any]] = []

    for _ in range(max_tool_rounds):
        assistant_message = await client.ask(message_history=history, tools=tools)
        tool_calls_raw = assistant_message.get("tool_calls")
        tool_calls = tool_calls_raw if isinstance(tool_calls_raw, list) else []

        if not tool_calls:
            content = assistant_message.get("content")
            text = content if isinstance(content, str) else ""
            text = _normalize_response_dates(text, executed_tools)
            if not text.strip() and _has_successful_task_action(executed_tools):
                text = "Готово, сделал."
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

            logger.info("Вызов инструмента: %s(%s)", tool_name, arguments)
            if not tool_name:
                result = "Ошибка вызова инструмента: пустое имя инструмента"
            else:
                try:
                    result = registry.execute(tool_name, arguments)
                except KeyError as error:
                    result = f"Ошибка вызова инструмента: {error}"
            logger.info("Результат инструмента %s: %s", tool_name, result)
            executed_tools.append({"name": tool_name, "arguments": dict(arguments), "result": result})

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
    register_obsidian_vault_tools(registry)
    register_calendar_tools(registry)
    client = LLMClient()
    tools = registry.list_schemas()
    history = client.history

    logger.info("CLI запущен. Для выхода отправьте: exit | quit | выход. Очистка памяти: /clear")
    try:
        while True:
            try:
                user_input = input("\n❯ ").strip()
            except EOFError:
                break

            if user_input.lower() in EXIT_COMMANDS:
                break
            if user_input.lower() in CLEAR_COMMANDS:
                client.clear_history()
                history.clear()
                print("Память очищена")
                continue
            if not user_input:
                continue

            print(f"Mason: {get_quick_filler(user_input)}")
            history.append({"role": "user", "content": user_input})
            try:
                response_text = await _resolve_assistant_turn(
                    client=client,
                    registry=registry,
                    history=history,
                    tools=tools,
                    logger_name="mason",
                )
            except Exception as error:
                logger.exception("Ошибка во время обработки запроса")
                response_text = f"Ошибка во время обработки запроса: {error}"
                history.append({"role": "assistant", "content": response_text})

            client.save_history(history)
            
            voice_match = re.search(r"<voice>(.*?)</voice>", response_text, re.DOTALL)
            chat_match = re.search(r"<chat>(.*?)</chat>", response_text, re.DOTALL)
            
            if voice_match or chat_match:
                if voice_match:
                    print(f"Mason [Voice]: {voice_match.group(1).strip()}")
                if chat_match:
                    print(f"Mason [Chat]: {chat_match.group(1).strip()}")
            else:
                print(f"Mason: {response_text}")
    finally:
        client.save_history(history)
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(_main())
