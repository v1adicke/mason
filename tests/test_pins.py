from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from telethon.tl import types

from mason.telegram.client import TelethonBackend
from mason.telegram.demo import DEMO_CHAT_ID, DemoBackend
from mason.telegram.models import Chat
from mason.telegram.service import ServiceError, TelegramService


@pytest.fixture
def service():
    return TelegramService(DemoBackend(), [DEMO_CHAT_ID], "UTC")


async def test_pins_use_the_actual_flag_and_page_without_duplicates(service):
    service.backend.messages[-1].pinned = True
    first = await service.get_pinned_messages(DEMO_CHAT_ID, limit=1)
    second = await service.get_pinned_messages(DEMO_CHAT_ID, limit=1, cursor=first.next_cursor)
    assert [message.message_id for message in first.messages + second.messages] == [4, 2]
    assert all(message.pinned for message in first.messages + second.messages)
    assert first.next_cursor is not None
    assert second.next_cursor is None
    assert second.messages[0].file_name == "discrete_maths.pdf"
    assert len(service.backend.messages) == 4


async def test_empty_pins_and_unpinning_between_pages_are_live_reads(service):
    service.backend.messages[-1].pinned = True
    first = await service.get_pinned_messages(DEMO_CHAT_ID, limit=1)
    for message in service.backend.messages:
        message.pinned = False
    second = await service.get_pinned_messages(DEMO_CHAT_ID, limit=1, cursor=first.next_cursor)
    assert second.messages == []
    assert second.next_cursor is None
    assert (await service.get_pinned_messages(DEMO_CHAT_ID)).messages == []


async def test_pin_cursors_cannot_be_used_for_other_reads_or_chats(service):
    service.backend.messages[-1].pinned = True
    service.allowed_chats.append(99)
    pins = await service.get_pinned_messages(DEMO_CHAT_ID, limit=1)
    recent = await service.get_recent_messages(DEMO_CHAT_ID, limit=1)
    for read in (
        service.get_recent_messages(DEMO_CHAT_ID, cursor=pins.next_cursor),
        service.search_messages("maths", chat_id=DEMO_CHAT_ID, cursor=pins.next_cursor),
        service.get_pinned_messages(DEMO_CHAT_ID, cursor=recent.next_cursor),
        service.get_pinned_messages(99, cursor=pins.next_cursor),
    ):
        with pytest.raises(ServiceError, match="invalid_cursor"):
            await read


@pytest.mark.parametrize("limit", [0, 51])
async def test_pin_limits_are_checked_before_reading_telegram(service, limit):
    service.backend.read_messages = AsyncMock()
    with pytest.raises(ServiceError, match="invalid_limit"):
        await service.get_pinned_messages(DEMO_CHAT_ID, limit=limit)
    service.backend.read_messages.assert_not_awaited()


async def test_pins_cannot_bypass_chat_access(service):
    service.backend.read_messages = AsyncMock()
    with pytest.raises(ServiceError, match="chat_not_allowed"):
        await service.get_pinned_messages(999)
    service.backend.read_messages.assert_not_awaited()


@pytest.mark.parametrize(
    "changed",
    [
        {"pinned": False},
        {"chat": Chat(id=999, title="Other", kind="private")},
    ],
)
async def test_unexpected_pin_sources_are_refused(service, changed):
    service.backend.read_messages = AsyncMock(
        return_value=[service.backend.messages[1].model_copy(update=changed)]
    )
    with pytest.raises(ServiceError, match="invalid_source"):
        await service.get_pinned_messages(DEMO_CHAT_ID)


async def test_telethon_uses_pinned_filter_and_bounded_offsets():
    backend = TelethonBackend.__new__(TelethonBackend)
    backend.client = AsyncMock()
    backend.get_chat = AsyncMock(return_value=Chat(id=123, title="Demo", kind="private"))
    calls = []

    async def iterate(peer, **kwargs):
        calls.append((peer, kwargs))
        yield types.Message(
            id=8,
            peer_id=types.PeerUser(123),
            date=datetime(2026, 1, 1, tzinfo=UTC),
            message="a fictional pin",
            pinned=True,
        )

    backend.client.iter_messages = iterate
    result = await backend.read_messages(123, pinned_only=True, limit=3, before_id=15)
    assert result[0].pinned
    assert calls[0][0] == 123
    assert calls[0][1]["limit"] == 3
    assert calls[0][1]["offset_id"] == 15
    assert isinstance(calls[0][1]["filter"], types.InputMessagesFilterPinned)
    backend.client.pin_message.assert_not_called()
    backend.client.unpin_message.assert_not_called()
