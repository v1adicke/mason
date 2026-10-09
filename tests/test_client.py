from datetime import UTC, datetime
from unittest.mock import AsyncMock

from telethon.tl import types

from mason.telegram.client import TelethonBackend
from mason.telegram.service import TelegramService


async def test_saved_messages_can_be_found_by_its_telegram_name():
    backend = TelethonBackend.__new__(TelethonBackend)
    backend.client = AsyncMock()
    backend.client.get_entity.return_value = types.User(
        id=123, first_name="Demo owner", is_self=True
    )
    service = TelegramService(backend, [123], "Asia/Nicosia")
    for query in ("Saved Messages", "Избранное"):
        page = await service.list_chats(query, 20, None)
        assert [chat.id for chat in page.chats] == [123]
        assert page.chats[0].kind == "private"


async def test_other_private_chats_keep_their_display_name():
    backend = TelethonBackend.__new__(TelethonBackend)
    backend.client = AsyncMock()
    backend.client.get_entity.return_value = types.User(id=456, first_name="Demo contact")
    chat = await backend.get_chat(456)
    assert chat.title == "Demo contact"


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


async def test_sender_filter_is_sent_to_telethon_with_chat_and_pagination():
    from mason.telegram.models import Chat

    chat_id = -1001234567890
    backend = TelethonBackend.__new__(TelethonBackend)
    backend.get_chat = AsyncMock(
        return_value=Chat(id=chat_id, title="Study group", kind="supergroup")
    )
    backend.client = AsyncMock()
    calls = []

    async def iterate(peer, **kwargs):
        calls.append((peer, kwargs))
        yield types.Message(
            id=8,
            peer_id=types.PeerChannel(1234567890),
            from_id=types.PeerUser(123),
            date=datetime(2026, 1, 1, tzinfo=UTC),
            message="a test message",
        )

    backend.client.iter_messages = iterate
    date_to = datetime(2026, 2, 1, tzinfo=UTC)
    result = await backend.read_messages(
        chat_id, limit=2, query="maths", before_id=15, date_to=date_to, sender_id=123
    )
    assert result[0].sender_id == 123
    assert calls == [
        (
            chat_id,
            {
                "limit": 2,
                "search": "maths",
                "offset_id": 15,
                "offset_date": date_to,
                "from_user": 123,
            },
        )
    ]
