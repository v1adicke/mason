"""Backward-compatible facade for Obsidian task tools"""

from __future__ import annotations

from .commands import add_daily_task
from .commands import complete_daily_task
from .commands import delete_daily_task
from .commands import get_daily_tasks


__all__ = [
    "add_daily_task",
    "get_daily_tasks",
    "complete_daily_task",
    "delete_daily_task",
]
