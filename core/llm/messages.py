"""Message sanitization and extraction helpers for LLM client"""

from __future__ import annotations

from typing import Any


ChatMessage = dict[str, Any]
PERSISTED_ROLES = {"user", "assistant", "tool"}


def sanitize_and_trim(messages: list[Any], max_history_messages: int) -> list[ChatMessage]:
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

    if len(sanitized) > max_history_messages:
        return sanitized[-max_history_messages:]
    return sanitized


def extract_text(content: Any) -> str:
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
