"""Obsidian tools package exports"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .io import DEFAULT_FORWARD_SCAN_DAYS
from .schemas import CRITICAL_TASK_MATCHING_STRATEGY
from .schemas import TARGET_DATE_DESCRIPTION
from .schemas import add_daily_task_tool_schema
from .schemas import complete_daily_task_tool_schema
from .schemas import delete_daily_task_tool_schema
from .schemas import get_daily_tasks_tool_schema
from .tasks import add_daily_task
from .tasks import complete_daily_task
from .tasks import delete_daily_task
from .tasks import get_daily_tasks

if TYPE_CHECKING:
    from .. import ToolRegistry


def register_obsidian_daily_tools(registry: ToolRegistry) -> None:
    """Register Obsidian tools in registry"""
    registry.register(
        name="add_daily_task",
        description="Добавляет задачу на сегодня",
        parameters=add_daily_task_tool_schema(),
        handler=add_daily_task,
    )
    registry.register(
        name="get_daily_tasks",
        description="Возвращает незавершенные задачи на сегодня",
        parameters=get_daily_tasks_tool_schema(),
        handler=get_daily_tasks,
    )
    registry.register(
        name="complete_daily_task",
        description=(
            "Отмечает задачу как выполненную " + CRITICAL_TASK_MATCHING_STRATEGY
        ),
        parameters=complete_daily_task_tool_schema(),
        handler=complete_daily_task,
    )
    registry.register(
        name="delete_daily_task",
        description=(
            "Удаляет задачу из списка на сегодня " + CRITICAL_TASK_MATCHING_STRATEGY
        ),
        parameters=delete_daily_task_tool_schema(),
        handler=delete_daily_task,
    )


__all__ = [
    "DEFAULT_FORWARD_SCAN_DAYS",
    "TARGET_DATE_DESCRIPTION",
    "CRITICAL_TASK_MATCHING_STRATEGY",
    "add_daily_task",
    "get_daily_tasks",
    "complete_daily_task",
    "delete_daily_task",
    "add_daily_task_tool_schema",
    "get_daily_tasks_tool_schema",
    "complete_daily_task_tool_schema",
    "delete_daily_task_tool_schema",
    "register_obsidian_daily_tools",
]
