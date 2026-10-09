from datetime import datetime
from typing import Protocol

from mason.telegram.models import Chat, Message


class TelegramBackend(Protocol):
    """describe the reads used by the service"""

    async def connect(self) -> None: ...

    async def disconnect(self) -> None: ...

    async def get_chat(self, chat_id: int) -> Chat: ...

    async def read_messages(
        self,
        chat_id: int,
        *,
        limit: int,
        query: str | None = None,
        before_id: int = 0,
        date_to: datetime | None = None,
        sender_id: int | None = None,
        documents_only: bool = False,
    ) -> list[Message]: ...

    async def get_context(
        self, chat_id: int, message_id: int, before: int, after: int
    ) -> list[Message]: ...
