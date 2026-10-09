import os
from datetime import datetime
from pathlib import Path

from telethon import TelegramClient, utils
from telethon.tl import types

from mason.config import TelegramSettings
from mason.telegram.links import message_url
from mason.telegram.models import Chat, Message


def prepare_session(path: Path, *, create: bool = False) -> None:
    """check the session location and its file permissions"""
    if create:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.parent.stat().st_uid != os.getuid() or path.parent.stat().st_mode & 0o077:
        raise ValueError("the session directory must have permissions 700")
    if not create and not path.is_file():
        raise ValueError("run mason login first")
    for file in path.parent.glob(path.name + "*"):
        if file.is_symlink() or file.stat().st_uid != os.getuid() or file.stat().st_mode & 0o077:
            raise ValueError("session files must have permissions 600")


def create_client(settings: TelegramSettings) -> TelegramClient:
    """disable updates and automatic waits for the read-only client"""
    os.umask(0o077)
    return TelegramClient(
        str(settings.session_path),
        settings.telegram_api_id,
        settings.telegram_api_hash.get_secret_value(),
        receive_updates=False,
        flood_sleep_threshold=0,
        request_retries=1,
        connection_retries=2,
        timeout=10,
    )


class TelethonBackend:
    """translate bounded read operations into Telethon calls"""

    def __init__(self, settings: TelegramSettings):
        prepare_session(settings.session_path)
        self.client = create_client(settings)

    async def connect(self) -> None:
        await self.client.connect()
        if not await self.client.is_user_authorized():
            await self.client.disconnect()
            raise ValueError("run mason login to authorize Telegram")

    async def disconnect(self) -> None:
        await self.client.disconnect()

    async def get_chat(self, chat_id: int) -> Chat:
        entity = await self.client.get_entity(chat_id)
        if isinstance(entity, types.Channel):
            kind = "supergroup" if entity.megagroup else "channel"
        elif isinstance(entity, types.Chat):
            kind = "group"
        elif isinstance(entity, types.User):
            kind = "private"
        else:
            raise ValueError("chat is unavailable")
        title = (
            "Saved Messages (Избранное)"
            if isinstance(entity, types.User) and entity.is_self
            else utils.get_display_name(entity)[:200]
        )
        return Chat(
            id=utils.get_peer_id(entity),
            title=title,
            kind=kind,
            username=getattr(entity, "username", None),
        )

    def _message(self, chat: Chat, message: types.Message | types.MessageService) -> Message:
        media_type = None
        if message.photo:
            media_type = "photo"
        elif message.document:
            media_type = "document"
        return Message(
            chat=chat,
            message_id=message.id,
            kind="service" if isinstance(message, types.MessageService) else "message",
            sender=utils.get_display_name(message.sender)[:200] if message.sender else None,
            sender_id=message.sender_id,
            date=message.date,
            text=message.message or "",
            url=message_url(chat, message.id),
            reply_to_message_id=message.reply_to_msg_id,
            edited_at=message.edit_date,
            media_type=media_type,
            file_name=message.file.name[:200] if message.file and message.file.name else None,
        )

    async def read_messages(
        self,
        chat_id: int,
        *,
        limit: int,
        query: str | None = None,
        before_id: int = 0,
        date_to: datetime | None = None,
        sender_id: int | None = None,
    ) -> list[Message]:
        chat = await self.get_chat(chat_id)
        messages = []
        async for message in self.client.iter_messages(
            chat_id,
            limit=limit,
            search=query,
            offset_id=before_id,
            offset_date=date_to,
            from_user=sender_id,
        ):
            if isinstance(message, (types.Message, types.MessageService)):
                messages.append(self._message(chat, message))
        return messages

    async def get_context(
        self, chat_id: int, message_id: int, before: int, after: int
    ) -> list[Message]:
        chat = await self.get_chat(chat_id)
        anchor = await self.client.get_messages(chat_id, ids=message_id)
        if not isinstance(anchor, (types.Message, types.MessageService)):
            return []
        messages = [anchor]
        if before:
            async for message in self.client.iter_messages(
                chat_id, limit=before, max_id=message_id
            ):
                if isinstance(message, (types.Message, types.MessageService)):
                    messages.append(message)
        if after:
            async for message in self.client.iter_messages(
                chat_id, limit=after, min_id=message_id, reverse=True
            ):
                if isinstance(message, (types.Message, types.MessageService)):
                    messages.append(message)
        return [self._message(chat, message) for message in sorted(messages, key=lambda m: m.id)]
