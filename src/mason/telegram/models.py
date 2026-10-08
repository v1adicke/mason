from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class Chat(BaseModel):
    id: int
    title: str
    kind: Literal["private", "group", "supergroup", "channel"]
    username: str | None = None


class Message(BaseModel):
    chat: Chat
    message_id: int
    sender: str | None
    sender_id: int | None
    date: datetime
    text: str
    text_truncated: bool = False
    url: str | None = None
    reply_to_message_id: int | None = None
    edited_at: datetime | None = None
    media_type: str | None = None
    file_name: str | None = None


class ChatPage(BaseModel):
    chats: list[Chat]
    next_cursor: str | None = None


class MessagePage(BaseModel):
    messages: list[Message]
    next_cursor: str | None = None
    searched_chats: list[int]
    timezone: str


class MessageContext(BaseModel):
    messages: list[Message]
    anchor_id: int
    timezone: str
