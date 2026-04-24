"""JSON schemas for Obsidian tools"""

from __future__ import annotations

from typing import Any


JSONSchema = dict[str, Any]
ISO_DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"

TARGET_DATE_DESCRIPTION = (
    "The target date in strict YYYY-MM-DD format. If the user specifies a relative "
    "date like 'tomorrow', 'next Saturday', or 'on the 15th', you MUST calculate the "
    "exact YYYY-MM-DD date based on the current logical date and pass it here."
)

CRITICAL_TASK_MATCHING_STRATEGY = (
    "CRITICAL STRATEGY: DO NOT guess the exact task text. If you do not have the exact "
    "text of the task in your immediate short-term memory, you MUST call `get_daily_tasks` "
    "FIRST to read the current tasks for the target date. Then, find the semantically "
    "matching task from that list and use its EXACT text."
)


def add_daily_task_tool_schema() -> JSONSchema:
    """Build JSON schema for add_daily_task tool"""
    return {
        "type": "object",
        "properties": {
            "task_text": {
                "type": "string",
                "description": "Текст задачи, которую нужно добавить",
            },
            "target_date": {
                "type": "string",
                "description": TARGET_DATE_DESCRIPTION,
                "pattern": ISO_DATE_PATTERN,
            }
        },
        "required": ["task_text", "target_date"],
        "additionalProperties": False,
    }


def get_daily_tasks_tool_schema() -> JSONSchema:
    """Build JSON schema for get_daily_tasks tool"""
    return {
        "type": "object",
        "properties": {
            "target_date": {
                "type": "string",
                "description": TARGET_DATE_DESCRIPTION,
                "pattern": ISO_DATE_PATTERN,
            }
        },
        "required": ["target_date"],
        "additionalProperties": False,
    }


def complete_daily_task_tool_schema() -> JSONSchema:
    """Build JSON schema for complete_daily_task tool"""
    return {
        "type": "object",
        "description": CRITICAL_TASK_MATCHING_STRATEGY,
        "properties": {
            "task_text": {
                "type": "string",
                "description": (
                    "Текст задачи, которую нужно отметить "
                    + CRITICAL_TASK_MATCHING_STRATEGY
                ),
            },
            "target_date": {
                "type": "string",
                "description": TARGET_DATE_DESCRIPTION,
                "pattern": ISO_DATE_PATTERN,
            }
        },
        "required": ["task_text", "target_date"],
        "additionalProperties": False,
    }


def delete_daily_task_tool_schema() -> JSONSchema:
    """Build JSON schema for delete_daily_task tool"""
    return {
        "type": "object",
        "description": CRITICAL_TASK_MATCHING_STRATEGY,
        "properties": {
            "task_text": {
                "type": "string",
                "description": (
                    "Текст задачи, которую нужно удалить "
                    + CRITICAL_TASK_MATCHING_STRATEGY
                ),
            },
            "target_date": {
                "type": "string",
                "description": TARGET_DATE_DESCRIPTION,
                "pattern": ISO_DATE_PATTERN,
            }
        },
        "required": ["task_text", "target_date"],
        "additionalProperties": False,
    }


def search_vault_tool_schema() -> JSONSchema:
    """Build JSON schema for search_vault tool"""
    return {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "Поисковый запрос. Ищет совпадения (без учёта регистра) "
                    "в именах файлов и содержимом всех .md заметок в Vault. "
                    "Возвращает до 10 результатов с цитатой из контекста."
                ),
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    }


def read_note_tool_schema() -> JSONSchema:
    """Build JSON schema for read_note tool"""
    return {
        "type": "object",
        "properties": {
            "filepath": {
                "type": "string",
                "description": (
                    "Путь к .md файлу относительно корня Vault "
                    "(например, 'Projects/idea.md'). "
                    "Получи его из результатов search_vault. "
                    "Разрешены только .md файлы внутри Vault."
                ),
            },
        },
        "required": ["filepath"],
        "additionalProperties": False,
    }


def replace_in_note_tool_schema() -> JSONSchema:
    """Build JSON schema for replace_in_note tool"""
    return {
        "type": "object",
        "properties": {
            "filepath": {
                "type": "string",
                "description": (
                    "Путь к .md файлу относительно корня Vault "
                    "(например, 'Projects/idea.md'). "
                    "Разрешены только .md файлы внутри Vault."
                ),
            },
            "old_text": {
                "type": "string",
                "description": (
                    "ТОЧНАЯ подстрока, которую нужно заменить. "
                    "Должна дословно совпадать с текстом в файле — "
                    "с учётом регистра, пробелов и переносов строк. "
                    "Если не уверен в точном тексте — сначала вызови read_note."
                ),
            },
            "new_text": {
                "type": "string",
                "description": (
                    "Текст, которым нужно заменить первое вхождение old_text. "
                    "Может быть пустой строкой для удаления фрагмента."
                ),
            },
        },
        "required": ["filepath", "old_text", "new_text"],
        "additionalProperties": False,
    }
