"""JSON schemas for calendar tools"""

from __future__ import annotations

from typing import Any


JSONSchema = dict[str, Any]

RELATIVE_TIME_DESCRIPTION = (
    "If the user says 'tomorrow at 2 PM', calculate the exact ISO timestamp "
    "based on the current system time and pass it here."
)

TARGET_DATE_DESCRIPTION = (
    "Target date in YYYY-MM-DD format. " + RELATIVE_TIME_DESCRIPTION
)

ISO_DATETIME_DESCRIPTION = (
    "ISO 8601 datetime value. " + RELATIVE_TIME_DESCRIPTION
)

CRITICAL_EVENT_MATCHING_STRATEGY = (
    "CRITICAL STRATEGY: DO NOT guess event_id. If event_id is unknown or missing, "
    "you MUST call `get_calendar_events` first and then use the exact ID from results."
)


def get_calendar_events_tool_schema() -> JSONSchema:
    """Build JSON schema for get_calendar_events tool"""
    return {
        "type": "object",
        "properties": {
            "target_date": {
                "type": "string",
                "description": TARGET_DATE_DESCRIPTION,
            }
        },
        "required": ["target_date"],
        "additionalProperties": False,
    }


def add_calendar_event_tool_schema() -> JSONSchema:
    """Build JSON schema for add_calendar_event tool"""
    return {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "Event title",
            },
            "start_dt": {
                "type": "string",
                "description": ISO_DATETIME_DESCRIPTION,
            },
            "end_dt": {
                "type": "string",
                "description": ISO_DATETIME_DESCRIPTION,
            },
            "description": {
                "type": "string",
                "description": "Optional event description",
            },
        },
        "required": ["summary", "start_dt", "end_dt"],
        "additionalProperties": False,
    }


def delete_calendar_event_tool_schema() -> JSONSchema:
    """Build JSON schema for delete_calendar_event tool"""
    return {
        "type": "object",
        "description": CRITICAL_EVENT_MATCHING_STRATEGY,
        "properties": {
            "event_id": {
                "type": "string",
                "description": (
                    "Unique event ID to delete. " + CRITICAL_EVENT_MATCHING_STRATEGY
                ),
            }
        },
        "required": ["event_id"],
        "additionalProperties": False,
    }
