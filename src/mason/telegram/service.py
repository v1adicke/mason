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
from mason.telegram.models import (
    DOCUMENT_TYPES,
    ChatPage,
    MediaType,
    Message,
    MessageContext,
    MessagePage,
    MessageRead,
    ReplyChain,
    ThreadPage,
    UnreadPage,
)


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
        return await self._read(query, chat_id, date_from, date_to, limit, cursor, sender_id)

    async def find_documents(
        self,
        query: str | None = None,
        chat_id: int | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 20,
        cursor: str | None = None,
        sender_id: int | None = None,
        file_name: str | None = None,
    ) -> MessagePage:
        """find document messages without downloading their contents"""
        query = query.strip() if query is not None else None
        file_name = file_name.strip() if file_name is not None else None
        for name, value in (("query", query), ("file_name", file_name)):
            if value is not None and (not value or len(value) > 256):
                raise ServiceError(f"invalid_{name}: use between 1 and 256 characters")
        return await self._read(
            query, chat_id, date_from, date_to, limit, cursor, sender_id, True, file_name
        )

    async def get_recent_messages(
        self,
        chat_id: int,
        limit: int = 20,
        cursor: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> MessagePage:
        return await self._read(None, chat_id, date_from, date_to, limit, cursor)

    async def find_media(
        self,
        media_type: MediaType,
        query: str | None = None,
        chat_id: int | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 20,
        cursor: str | None = None,
        sender_id: int | None = None,
        file_name: str | None = None,
    ) -> MessagePage:
        """find attached media by type and caption without downloading files"""
        if media_type not in ("photo", "video", "voice", "audio"):
            raise ServiceError("invalid_media_type: choose photo, video, voice, or audio")
        query = query.strip() if query is not None else None
        file_name = file_name.strip() if file_name is not None else None
        for name, value in (("query", query), ("file_name", file_name)):
            if value is not None and (not value or len(value) > 256):
                raise ServiceError(f"invalid_{name}: use between 1 and 256 characters")
        return await self._read(
            query,
            chat_id,
            date_from,
            date_to,
            limit,
            cursor,
            sender_id,
            file_name=file_name,
            media_type=media_type,
        )

    async def get_pinned_messages(
        self, chat_id: int, limit: int = 20, cursor: str | None = None
    ) -> MessagePage:
        """read current pinned messages from one allowed chat"""
        self._check_chat(chat_id)
        return await self._read(None, chat_id, None, None, limit, cursor, pinned_only=True)

    async def _read(
        self,
        query: str | None,
        chat_id: int | None,
        date_from: datetime | None,
        date_to: datetime | None,
        limit: int,
        cursor: str | None,
        sender_id: int | None = None,
        documents_only: bool = False,
        file_name: str | None = None,
        pinned_only: bool = False,
        media_type: MediaType | None = None,
    ) -> MessagePage:
        if not 1 <= limit <= 50:
            raise ServiceError("invalid_limit: choose between 1 and 50 messages")
        if sender_id is not None and (type(sender_id) is not int or sender_id == 0):
            raise ServiceError("invalid_sender: use a numeric sender_id from a returned message")
        for date in (date_from, date_to):
            if date is not None and date.utcoffset() is None:
                raise ServiceError("invalid_date: include a timezone offset")
        if date_from and date_to and date_from >= date_to:
            raise ServiceError("invalid_date: date_from must be earlier than date_to")
        if chat_id is not None:
            self._check_chat(chat_id)
        chat_ids = [chat_id] if chat_id is not None else self.allowed_chats
        kind = "pinned" if pinned_only else "messages"
        if media_type:
            kind = "media:" + media_type
        key = self._key(
            kind,
            query,
            chat_ids,
            date_from,
            date_to,
            sender_id,
            documents_only,
            file_name,
        )
        offsets = self._decode_cursor(cursor, key, {})
        if not isinstance(offsets, dict) or any(
            chat not in {str(value) for value in chat_ids} or type(offset) is not int or offset < 0
            for chat, offset in offsets.items()
        ):
            raise ServiceError("invalid_cursor: expected message offsets")
        matches = []
        scanned_offsets = {}
        filtered_scan = documents_only or media_type is not None
        more_filtered = False
        async with self._operation():
            for current_chat in chat_ids:
                messages = await self.backend.read_messages(
                    current_chat,
                    limit=limit + 1,
                    query=query,
                    before_id=offsets.get(str(current_chat), 0),
                    date_to=date_to,
                    sender_id=sender_id,
                    documents_only=documents_only,
                    pinned_only=pinned_only,
                    media_type=media_type,
                )
                if filtered_scan and messages:
                    scanned_offsets[str(current_chat)] = messages[-1].message_id
                    if len(messages) == limit + 1 and (
                        date_from is None or messages[-1].date >= date_from
                    ):
                        more_filtered = True
                for message in messages:
                    if message.chat.id != current_chat:
                        raise ServiceError("invalid_source: unexpected chat in the result")
                    if sender_id is not None and message.sender_id != sender_id:
                        raise ServiceError("invalid_source: unexpected sender in the result")
                    if documents_only and message.media_type not in DOCUMENT_TYPES:
                        raise ServiceError("invalid_source: expected a document message")
                    if media_type is not None and message.media_type != media_type:
                        raise ServiceError("invalid_source: unexpected media type in the result")
                    if pinned_only and not message.pinned:
                        raise ServiceError("invalid_source: expected a pinned message")
                    if date_from and message.date < date_from:
                        continue
                    if date_to and message.date >= date_to:
                        continue
                    if (
                        file_name
                        and file_name.casefold() not in (message.file_name or "").casefold()
                    ):
                        continue
                    matches.append(message)
        matches.sort(
            key=lambda message: (message.date, message.chat.id, message.message_id), reverse=True
        )
        selected = matches[:limit]
        for message in selected:
            offsets[str(message.chat.id)] = message.message_id
        if filtered_scan:
            pending_chats = {str(message.chat.id) for message in matches[limit:]}
            offsets.update(
                (chat, offset)
                for chat, offset in scanned_offsets.items()
                if chat not in pending_chats
            )
        return MessagePage(
            messages=self._format_messages(selected),
            next_cursor=self._encode_cursor(key, offsets)
            if len(matches) > limit or more_filtered
            else None,
            searched_chats=chat_ids,
            timezone=str(self.timezone),
        )

    async def get_message(
        self, chat_id: int, message_id: int, text_offset: int = 0, text_limit: int = 2000
    ) -> MessageRead:
        """read one message in bounded text chunks without changing the source"""
        self._check_chat(chat_id)
        if (
            type(message_id) is not int
            or message_id <= 0
            or type(text_offset) is not int
            or not 0 <= text_offset <= 1000000
            or type(text_limit) is not int
            or not 1 <= text_limit <= 2000
        ):
            raise ServiceError("invalid_message_read: check the ID, text offset, and limit")
        async with self._operation():
            message = await self.backend.get_message(chat_id, message_id)
        if message is None:
            raise ServiceError("message_not_found: it may have been deleted or become unavailable")
        if message.chat.id != chat_id or message.message_id != message_id:
            raise ServiceError("invalid_source: unexpected message in the result")
        total = len(message.text)
        if text_offset and text_offset >= total:
            raise ServiceError("invalid_text_offset: the message may have changed; start at zero")
        end = min(text_offset + text_limit, total)
        chunk = message.model_copy(update={"text": message.text[text_offset:end]})
        formatted = self._format_messages([chunk])[0].model_copy(
            update={"text_truncated": text_offset > 0 or end < total}
        )
        return MessageRead(
            message=formatted,
            text_offset=text_offset,
            total_text_length=total,
            next_text_offset=end if end < total else None,
            timezone=str(self.timezone),
        )

    async def get_reply_chain(self, chat_id: int, message_id: int, limit: int = 10) -> ReplyChain:
        """follow parent replies inside one chat with a bounded number of reads"""
        self._check_chat(chat_id)
        if (
            type(message_id) is not int
            or message_id <= 0
            or type(limit) is not int
            or not 1 <= limit <= 10
        ):
            raise ServiceError("invalid_reply_chain: use a positive ID and a limit from 1 to 10")
        messages = []
        seen = set()
        current_id = message_id
        next_id = missing_id = None
        stop_reason = "end"
        async with self._operation():
            while True:
                message = await self.backend.get_message(chat_id, current_id)
                if message is None:
                    if not messages:
                        raise ServiceError("message_not_found: the starting message is unavailable")
                    stop_reason, missing_id = "missing", current_id
                    break
                if message.chat.id != chat_id or message.message_id != current_id:
                    raise ServiceError("invalid_source: unexpected message in the reply chain")
                messages.append(message)
                seen.add(current_id)
                parent_id = message.reply_to_message_id
                if parent_id is None:
                    break
                if message.reply_to_scheduled:
                    stop_reason = "scheduled"
                    break
                if message.reply_to_chat_id not in (None, chat_id):
                    stop_reason = "other_chat"
                    break
                if type(parent_id) is not int or parent_id <= 0 or parent_id in seen:
                    raise ServiceError("invalid_source: invalid or cyclic reply chain")
                if len(messages) == limit:
                    stop_reason, next_id = "limit", parent_id
                    break
                current_id = parent_id
        return ReplyChain(
            messages=self._format_messages(list(reversed(messages))),
            anchor_id=message_id,
            stop_reason=stop_reason,
            next_message_id=next_id,
            missing_message_id=missing_id,
            timezone=str(self.timezone),
        )

    async def get_unread_messages(
        self, chat_id: int, limit: int = 20, cursor: str | None = None
    ) -> UnreadPage:
        """read incoming messages after the inbox marker without marking them read"""
        self._check_chat(chat_id)
        if type(limit) is not int or not 1 <= limit <= 50:
            raise ServiceError("invalid_limit: choose between 1 and 50 messages")
        async with self._operation():
            state = await self.backend.get_read_state(chat_id)
            if state.chat_id != chat_id:
                raise ServiceError("invalid_source: unexpected dialog in the result")
            if state.topic_based:
                raise ServiceError(
                    "unsupported_unread: topic-based chats need separate read markers"
                )
            key = self._key("unread", chat_id, state.read_inbox_max_id)
            offset = self._decode_cursor(cursor, key, 0)
            if type(offset) is not int or offset < 0:
                raise ServiceError("invalid_cursor: expected an unread message offset")
            messages = (
                await self.backend.read_messages(
                    chat_id, limit=limit + 1, before_id=offset, min_id=state.read_inbox_max_id
                )
                if state.unread_count
                else []
            )
            seen = set()
            for message in messages:
                if (
                    message.chat.id != chat_id
                    or message.message_id <= state.read_inbox_max_id
                    or (offset and message.message_id >= offset)
                    or message.message_id in seen
                ):
                    raise ServiceError("invalid_source: unexpected unread message")
                seen.add(message.message_id)
        messages.sort(key=lambda message: message.message_id, reverse=True)
        incoming = [message for message in messages if not message.outgoing]
        selected = incoming[:limit]
        next_offset = None
        if len(incoming) > limit:
            next_offset = selected[-1].message_id
        elif len(messages) == limit + 1:
            next_offset = messages[-1].message_id
        return UnreadPage(
            messages=self._format_messages(selected),
            searched_chats=[chat_id],
            timezone=str(self.timezone),
            read_inbox_max_id=state.read_inbox_max_id,
            unread_count=state.unread_count,
            unread_mark=state.unread_mark,
            next_cursor=self._encode_cursor(key, next_offset) if next_offset is not None else None,
        )

    async def get_thread_replies(
        self, chat_id: int, message_id: int, limit: int = 20, cursor: str | None = None
    ) -> ThreadPage:
        """read a supergroup thread using its root message id"""
        self._check_chat(chat_id)
        if (
            type(message_id) is not int
            or message_id <= 0
            or type(limit) is not int
            or not 1 <= limit <= 50
        ):
            raise ServiceError("invalid_thread: use a positive root ID and a limit from 1 to 50")
        key = self._key("thread", chat_id, message_id)
        offset = self._decode_cursor(cursor, key, 0)
        if type(offset) is not int or offset < 0:
            raise ServiceError("invalid_cursor: expected a thread message offset")
        async with self._operation():
            chat = await self.backend.get_chat(chat_id)
            if chat.id != chat_id:
                raise ServiceError("invalid_source: unexpected thread chat")
            if chat.kind != "supergroup":
                raise ServiceError("unsupported_thread: use get_reply_chain to read parent replies")
            anchor = await self.backend.get_message(chat_id, message_id)
            if anchor is None:
                raise ServiceError("message_not_found: the thread root is unavailable")
            if anchor.chat.id != chat_id or anchor.message_id != message_id:
                raise ServiceError("invalid_source: unexpected thread root")
            root_id = anchor.thread_root_message_id
            if (
                root_id is None
                and anchor.reply_to_chat_id in (None, chat_id)
                and not anchor.reply_to_scheduled
            ):
                root_id = anchor.reply_to_message_id
            if root_id is not None and root_id != message_id:
                raise ServiceError(
                    "invalid_thread: find the root with thread_root_message_id or get_reply_chain"
                )
            messages = await self.backend.read_replies(
                chat_id, message_id, limit=limit + 1, before_id=offset
            )
            seen = set()
            for message in messages:
                if (
                    message.chat.id != chat_id
                    or message.reply_to_chat_id not in (None, chat_id)
                    or message.reply_to_scheduled
                    or (message.thread_root_message_id or message.reply_to_message_id) != message_id
                    or message.message_id == message_id
                    or message.message_id in seen
                    or (offset and message.message_id >= offset)
                ):
                    raise ServiceError("invalid_source: unexpected message in the thread")
                seen.add(message.message_id)
        messages.sort(key=lambda message: message.message_id, reverse=True)
        selected = messages[:limit]
        return ThreadPage(
            messages=self._format_messages(selected),
            root_message_id=message_id,
            searched_chats=[chat_id],
            timezone=str(self.timezone),
            next_cursor=self._encode_cursor(key, selected[-1].message_id)
            if len(messages) > limit
            else None,
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
