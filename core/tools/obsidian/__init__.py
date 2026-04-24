"""Obsidian tools package exports"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .schemas import CRITICAL_TASK_MATCHING_STRATEGY
from .schemas import TARGET_DATE_DESCRIPTION
from .schemas import add_daily_task_tool_schema
from .schemas import complete_daily_task_tool_schema
from .schemas import delete_daily_task_tool_schema
from .schemas import get_daily_tasks_tool_schema
from .schemas import read_note_tool_schema
from .schemas import replace_in_note_tool_schema
from .schemas import search_vault_tool_schema
from .tasks import add_daily_task
from .tasks import complete_daily_task
from .tasks import delete_daily_task
from .tasks import get_daily_tasks
from .vault import read_note
from .vault import replace_in_note
from .vault import search_vault

if TYPE_CHECKING:
    from .. import ToolRegistry


def register_obsidian_vault_tools(registry: ToolRegistry) -> None:
    """Register global Obsidian Vault search and read tools"""
    registry.register(
        name="search_vault",
        description="Ищет заметки в Obsidian Vault по запросу (имя файла + содержимое). Возвращает до 10 совпадений с фрагментами текста.",
        parameters=search_vault_tool_schema(),
        handler=search_vault,
    )
    registry.register(
        name="read_note",
        description="Читает полное содержимое .md заметки из Obsidian Vault по относительному пути. Используй путь из результатов search_vault.",
        parameters=read_note_tool_schema(),
        handler=read_note,
    )
    registry.register(
        name="replace_in_note",
        description=(
            "Заменяет ПЕРВОЕ вхождение точной подстроки (old_text) на новый текст (new_text) "
            "в указанной .md заметке Vault. old_text должен дословно совпадать с содержимым файла. "
            "Если не уверен в точном тексте — сначала вызови read_note."
        ),
        parameters=replace_in_note_tool_schema(),
        handler=replace_in_note,
    )


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
    "TARGET_DATE_DESCRIPTION",
    "CRITICAL_TASK_MATCHING_STRATEGY",
    "add_daily_task",
    "get_daily_tasks",
    "complete_daily_task",
    "delete_daily_task",
    "search_vault",
    "read_note",
    "replace_in_note",
    "add_daily_task_tool_schema",
    "get_daily_tasks_tool_schema",
    "complete_daily_task_tool_schema",
    "delete_daily_task_tool_schema",
    "search_vault_tool_schema",
    "read_note_tool_schema",
    "replace_in_note_tool_schema",
    "register_obsidian_daily_tools",
    "register_obsidian_vault_tools",
]
