from datetime import UTC, datetime
from unittest.mock import AsyncMock

from telethon.tl import types

from mason.telegram.client import TelethonBackend


async def test_telethon_context_reads_neighbors_without_assuming_dense_ids():
    chat_id = -1001234567890
    backend = TelethonBackend.__new__(TelethonBackend)
    backend.client = AsyncMock()
    backend.client.get_entity.return_value = types.Channel(
        id=1234567890,
        title="Study group",
        photo=types.ChatPhotoEmpty(),
        date=datetime(2026, 1, 1, tzinfo=UTC),
        megagroup=True,
    )

    def message(number):
        return types.Message(
            id=number,
            peer_id=types.PeerChannel(1234567890),
            date=datetime(2026, 1, 1, tzinfo=UTC),
            message="a test message",
        )

    backend.client.get_messages.return_value = message(8)
    calls = []

    async def iterate(peer, **kwargs):
        calls.append((peer, kwargs))
        yield message(15 if kwargs.get("reverse") else 2)

    backend.client.iter_messages = iterate
    result = await backend.get_context(chat_id, 8, before=1, after=1)
    assert [item.message_id for item in result] == [2, 8, 15]
    assert calls == [
        (chat_id, {"limit": 1, "max_id": 8}),
        (chat_id, {"limit": 1, "min_id": 8, "reverse": True}),
    ]


async def test_service_messages_are_kept_in_recent_history():
    from mason.telegram.models import Chat

    backend = TelethonBackend.__new__(TelethonBackend)
    backend.get_chat = AsyncMock(
        return_value=Chat(id=-1001234567890, title="Study group", kind="supergroup")
    )
    backend.client = AsyncMock()

    async def iterate(peer, **kwargs):
        yield types.MessageService(
            id=8,
            peer_id=types.PeerChannel(1234567890),
            date=datetime(2026, 1, 1, tzinfo=UTC),
            action=types.MessageActionPinMessage(),
        )
        yield types.Message(
            id=2,
            peer_id=types.PeerChannel(1234567890),
            date=datetime(2026, 1, 1, tzinfo=UTC),
            message="an older message",
        )

    backend.client.iter_messages = iterate
    messages = await backend.read_messages(-1001234567890, limit=2)
    assert [(message.message_id, message.kind) for message in messages] == [
        (8, "service"),
        (2, "message"),
    ]
    assert messages[0].text == ""
