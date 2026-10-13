import os
from datetime import datetime
from pathlib import Path

from telethon import TelegramClient, utils
from telethon.tl import types

from mason.config import TelegramSettings
from mason.telegram.links import message_url
from mason.telegram.models import Chat, MediaType, Message


def message_media_type(message: types.Message | types.MessageService) -> str | None:
    """identify attached media without counting link previews"""
    if isinstance(message.media, types.MessageMediaPhoto) and message.photo:
        return "photo"
    if not isinstance(message.media, types.MessageMediaDocument) or not message.document:
        return None
    if message.voice:
        return "voice"
    if message.audio:
        return "audio"
    if message.video_note:
        return "video_note"
    if message.sticker:
        return "sticker"
    if message.gif:
        return "animation"
    if message.video:
        return "video"
    return "document"


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
        if utils.get_peer_id(message.peer_id) != chat.id:
            raise ValueError("unexpected message peer")
        media_type = message_media_type(message)
        file = message.file if media_type else None
        reply = message.reply_to if isinstance(message.reply_to, types.MessageReplyHeader) else None
        parent_id = reply.reply_to_msg_id if reply else None
        parent_chat_id = None
        if reply and reply.reply_to_peer_id:
            parent_chat_id = utils.get_peer_id(reply.reply_to_peer_id)
        elif parent_id:
            parent_chat_id = chat.id
        return Message(
            chat=chat,
            message_id=message.id,
            kind="service" if isinstance(message, types.MessageService) else "message",
            sender=utils.get_display_name(message.sender)[:200] if message.sender else None,
            sender_id=message.sender_id,
            date=message.date,
            text=message.message or "",
            pinned=bool(getattr(message, "pinned", False)),
            url=message_url(chat, message.id),
            reply_to_message_id=parent_id,
            reply_to_chat_id=parent_chat_id,
            reply_to_scheduled=bool(reply and reply.reply_to_scheduled),
            thread_root_message_id=reply.reply_to_top_id if reply else None,
            edited_at=message.edit_date,
            media_type=media_type,
            file_name=file.name[:200] if file and file.name else None,
            mime_type=file.mime_type[:100] if file and file.mime_type else None,
            file_size=file.size if file else None,
            media_width=file.width if file else None,
            media_height=file.height if file else None,
            media_duration=file.duration if file else None,
        )

    async def get_message(self, chat_id: int, message_id: int) -> Message | None:
        """read one message from the specified chat"""
        chat = await self.get_chat(chat_id)
        message = await self.client.get_messages(chat_id, ids=message_id)
        if not isinstance(message, (types.Message, types.MessageService)):
            return None
        return self._message(chat, message)

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
        pinned_only: bool = False,
        media_type: MediaType | None = None,
    ) -> list[Message]:
        if sum((documents_only, pinned_only, media_type is not None)) > 1:
            raise ValueError("choose one message filter")
        filters = {}
        if documents_only:
            filters["filter"] = types.InputMessagesFilterDocument()
        elif pinned_only:
            filters["filter"] = types.InputMessagesFilterPinned()
        elif media_type is not None:
            media_filters = {
                "photo": types.InputMessagesFilterPhotos,
                "video": types.InputMessagesFilterVideo,
                "voice": types.InputMessagesFilterVoice,
                "audio": types.InputMessagesFilterMusic,
            }
            filters["filter"] = media_filters[media_type]()
        chat = await self.get_chat(chat_id)
        messages = []
        async for message in self.client.iter_messages(
            chat_id,
            limit=limit,
            search=query,
            offset_id=before_id,
            offset_date=date_to,
            from_user=sender_id,
            **filters,
        ):
            if isinstance(message, (types.Message, types.MessageService)):
                messages.append(self._message(chat, message))
        return messages

    async def read_replies(
        self, chat_id: int, message_id: int, *, limit: int, before_id: int = 0
    ) -> list[Message]:
        """read a supergroup thread without following channel comments elsewhere"""
        chat = await self.get_chat(chat_id)
        if chat.kind != "supergroup":
            raise ValueError("reply threads require a supergroup")
        messages = []
        async for message in self.client.iter_messages(
            chat_id, reply_to=message_id, limit=limit, offset_id=before_id
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
