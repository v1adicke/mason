"""JSON schemas for Obsidian tools"""

from __future__ import annotations

from typing import Any


JSONSchema = dict[str, Any]

TARGET_DATE_DESCRIPTION = (
    "The target date in YYYY-MM-DD format. If the user specifies a relative date "
    "like 'tomorrow', 'next Saturday', or 'on the 15th', you MUST calculate the "
    "exact YYYY-MM-DD date based on the current system time and pass it here. "
    "If no date is specified, omit this parameter."
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
            }
        },
        "required": ["task_text"],
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
            }
        },
        "required": [],
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
            }
        },
        "required": ["task_text"],
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
            }
        },
        "required": ["task_text"],
        "additionalProperties": False,
    }
