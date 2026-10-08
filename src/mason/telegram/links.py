import re

from telethon.utils import resolve_id

from mason.telegram.models import Chat


def message_url(chat: Chat, message_id: int) -> str | None:
    """build message links only for supported chat types"""
    if chat.kind not in {"supergroup", "channel"}:
        return None
    if chat.username and re.fullmatch(r"[a-zA-Z0-9_]{5,32}", chat.username):
        return f"https://t.me/{chat.username}/{message_id}"
    if chat.id <= -1000000000000:
        channel_id, _ = resolve_id(chat.id)
        return f"https://t.me/c/{channel_id}/{message_id}"
    return None
