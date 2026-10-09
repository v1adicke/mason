import asyncio
import base64
import hashlib
import json
from contextlib import asynccontextmanager
from datetime import datetime
from time import monotonic
from zoneinfo import ZoneInfo

from telethon.errors import FloodWaitError, RPCError

from mason.telegram.backend import TelegramBackend
from mason.telegram.models import ChatPage, Message, MessageContext, MessagePage


class ServiceError(Exception):
    """carry a safe error message across the tool boundary"""


class TelegramService:
    """enforce chat access and keep every read bounded"""

    def __init__(self, backend: TelegramBackend, allowed_chats: list[int], timezone: str):
        if not allowed_chats or len(allowed_chats) > 20:
            raise ValueError("choose between 1 and 20 allowed chats")
        self.backend = backend
        self.allowed_chats = sorted(set(allowed_chats))
        self.timezone = ZoneInfo(timezone)
        self.lock = asyncio.Lock()
        self.blocked_until = 0.0

    def _check_chat(self, chat_id: int) -> None:
        if chat_id not in self.allowed_chats:
            raise ServiceError("chat_not_allowed: choose a chat from list_chats")

    @asynccontextmanager
    async def _operation(self):
        remaining = self.blocked_until - monotonic()
        if remaining > 0:
            raise ServiceError(f"rate_limited: retry in {int(remaining) + 1} seconds")
        if self.lock.locked():
            raise ServiceError("busy: wait for the current Telegram request to finish")
        async with self.lock:
            try:
                async with asyncio.timeout(30):
                    yield
            except FloodWaitError as error:
                self.blocked_until = monotonic() + error.seconds
                raise ServiceError(f"rate_limited: retry in {error.seconds} seconds") from None
            except TimeoutError:
                raise ServiceError("timeout: try a smaller request or a specific chat") from None
            except (RPCError, ValueError, OSError):
                raise ServiceError(
                    "telegram_unavailable: check the connection and chat access"
                ) from None

    def _key(self, *values: object) -> str:
        return hashlib.sha256(json.dumps(values, default=str).encode()).hexdigest()

    def _decode_cursor(self, cursor: str | None, key: str, default: object) -> object:
        if cursor is None:
            return default
        try:
            if len(cursor) > 4096:
                raise ValueError
            value = json.loads(base64.urlsafe_b64decode(cursor))
            if not isinstance(value, dict) or value.get("key") != key:
                raise ValueError
            return value["position"]
        except (ValueError, KeyError, TypeError):
            raise ServiceError("invalid_cursor: reuse the cursor with the same search") from None

    def _encode_cursor(self, key: str, position: object) -> str:
        value = json.dumps({"key": key, "position": position}, separators=(",", ":"))
        return base64.urlsafe_b64encode(value.encode()).decode()

    def _format_messages(self, messages: list[Message]) -> list[Message]:
        remaining = 20000
        result = []
        for message in messages:
            self._check_chat(message.chat.id)
            text = message.text[: min(2000, remaining)]
            remaining -= len(text)
            result.append(
                message.model_copy(
                    update={
                        "text": text,
                        "text_truncated": len(text) < len(message.text),
                        "date": message.date.astimezone(self.timezone),
                        "edited_at": message.edited_at.astimezone(self.timezone)
                        if message.edited_at
                        else None,
                    }
                )
            )
        return result

    async def list_chats(
        self, query: str | None = None, limit: int = 20, cursor: str | None = None
    ) -> ChatPage:
        if not 1 <= limit <= 50 or (query is not None and len(query) > 256):
            raise ServiceError("invalid_request: check the query and limit")
        key = self._key("chats", query, self.allowed_chats)
        offset = self._decode_cursor(cursor, key, 0)
        if type(offset) is not int or offset < 0:
            raise ServiceError("invalid_cursor: expected a chat offset")
        async with self._operation():
            chats = [await self.backend.get_chat(chat_id) for chat_id in self.allowed_chats]
        for chat in chats:
            self._check_chat(chat.id)
        if query:
            chats = [chat for chat in chats if query.casefold() in chat.title.casefold()]
        next_offset = offset + limit
        return ChatPage(
            chats=chats[offset:next_offset],
            next_cursor=self._encode_cursor(key, next_offset) if next_offset < len(chats) else None,
        )

    async def search_messages(
        self,
        query: str,
        chat_id: int | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 20,
        cursor: str | None = None,
        sender_id: int | None = None,
    ) -> MessagePage:
        query = query.strip()
        if not query or len(query) > 256:
            raise ServiceError("invalid_query: use between 1 and 256 characters")
        if sender_id is not None and (type(sender_id) is not int or sender_id == 0):
            raise ServiceError("invalid_sender: use a numeric sender_id from a returned message")
        return await self._read(query, chat_id, date_from, date_to, limit, cursor, sender_id)

    async def get_recent_messages(
        self, chat_id: int, limit: int = 20, cursor: str | None = None
    ) -> MessagePage:
        return await self._read(None, chat_id, None, None, limit, cursor)

    async def _read(
        self,
        query: str | None,
        chat_id: int | None,
        date_from: datetime | None,
        date_to: datetime | None,
        limit: int,
        cursor: str | None,
        sender_id: int | None = None,
    ) -> MessagePage:
        if not 1 <= limit <= 50:
            raise ServiceError("invalid_limit: choose between 1 and 50 messages")
        for date in (date_from, date_to):
            if date is not None and date.utcoffset() is None:
                raise ServiceError("invalid_date: include a timezone offset")
        if date_from and date_to and date_from >= date_to:
            raise ServiceError("invalid_date: date_from must be earlier than date_to")
        if chat_id is not None:
            self._check_chat(chat_id)
        chat_ids = [chat_id] if chat_id is not None else self.allowed_chats
        key = self._key("messages", query, chat_ids, date_from, date_to, sender_id)
        offsets = self._decode_cursor(cursor, key, {})
        if not isinstance(offsets, dict) or any(
            chat not in {str(value) for value in chat_ids} or type(offset) is not int or offset < 0
            for chat, offset in offsets.items()
        ):
            raise ServiceError("invalid_cursor: expected message offsets")
        matches = []
        async with self._operation():
            for current_chat in chat_ids:
                messages = await self.backend.read_messages(
                    current_chat,
                    limit=limit + 1,
                    query=query,
                    before_id=offsets.get(str(current_chat), 0),
                    date_to=date_to,
                    sender_id=sender_id,
                )
                for message in messages:
                    if message.chat.id != current_chat:
                        raise ServiceError("invalid_source: unexpected chat in the result")
                    if sender_id is not None and message.sender_id != sender_id:
                        raise ServiceError("invalid_source: unexpected sender in the result")
                    if date_from and message.date < date_from:
                        continue
                    if date_to and message.date >= date_to:
                        continue
                    matches.append(message)
        matches.sort(
            key=lambda message: (message.date, message.chat.id, message.message_id), reverse=True
        )
        selected = matches[:limit]
        for message in selected:
            offsets[str(message.chat.id)] = message.message_id
        return MessagePage(
            messages=self._format_messages(selected),
            next_cursor=self._encode_cursor(key, offsets) if len(matches) > limit else None,
            searched_chats=chat_ids,
            timezone=str(self.timezone),
        )

    async def get_message_context(
        self, chat_id: int, message_id: int, before: int = 5, after: int = 5
    ) -> MessageContext:
        self._check_chat(chat_id)
        if message_id <= 0 or not 0 <= before <= 10 or not 0 <= after <= 10:
            raise ServiceError(
                "invalid_context: use a positive ID and at most 10 messages per side"
            )
        async with self._operation():
            messages = await self.backend.get_context(chat_id, message_id, before, after)
        if not any(message.message_id == message_id for message in messages):
            raise ServiceError("message_not_found: it may have been deleted or become unavailable")
        if any(message.chat.id != chat_id for message in messages):
            raise ServiceError("invalid_source: unexpected chat in the result")
        return MessageContext(
            messages=self._format_messages(messages),
            anchor_id=message_id,
            timezone=str(self.timezone),
        )
