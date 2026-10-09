from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from telethon.errors import FloodWaitError

from mason.telegram.demo import DEMO_CHAT_ID, DemoBackend
from mason.telegram.models import Chat
from mason.telegram.service import ServiceError, TelegramService


@pytest.fixture
def service():
    return TelegramService(DemoBackend(), [DEMO_CHAT_ID], "Asia/Nicosia")


async def test_forbidden_chat_never_reaches_telegram(service):
    service.backend.read_messages = AsyncMock()
    service.backend.get_context = AsyncMock()
    with pytest.raises(ServiceError, match="chat_not_allowed"):
        await service.search_messages("homework", chat_id=123)
    with pytest.raises(ServiceError, match="chat_not_allowed"):
        await service.get_message_context(123, 1)
    service.backend.read_messages.assert_not_awaited()
    service.backend.get_context.assert_not_awaited()


async def test_search_pages_have_no_duplicates(service):
    first = await service.search_messages("maths", limit=1)
    second = await service.search_messages("maths", limit=1, cursor=first.next_cursor)
    assert [message.message_id for message in first.messages + second.messages] == [4, 1]
    assert second.next_cursor is None
    assert first.messages[0].date.utcoffset().total_seconds() == 7200
    assert first.messages[0].url is None


async def test_cursor_cannot_be_reused_for_another_search(service):
    first = await service.search_messages("maths", limit=1)
    with pytest.raises(ServiceError, match="invalid_cursor"):
        await service.search_messages("homework", cursor=first.next_cursor)


async def test_changed_allowlist_invalidates_search_cursor(service):
    first = await service.search_messages("maths", limit=1)
    service.allowed_chats = [123]
    with pytest.raises(ServiceError, match="invalid_cursor"):
        await service.search_messages("maths", cursor=first.next_cursor)


async def test_dates_use_an_inclusive_start_and_exclusive_end(service):
    result = await service.search_messages(
        "homework",
        date_from=datetime(2026, 1, 1, 12, tzinfo=UTC),
        date_to=datetime(2026, 1, 2, 12, tzinfo=UTC),
    )
    assert [message.message_id for message in result.messages] == [1]
    with pytest.raises(ServiceError, match="timezone"):
        await service.search_messages("homework", date_from=datetime(2026, 1, 1))


async def test_context_uses_existing_messages_with_gaps(service):
    for message, new_id in zip(service.backend.messages, [2, 8, 15, 30], strict=True):
        message.message_id = new_id
    result = await service.get_message_context(DEMO_CHAT_ID, 15, before=1, after=1)
    assert [message.message_id for message in result.messages] == [8, 15, 30]
    with pytest.raises(ServiceError, match="message_not_found"):
        await service.get_message_context(DEMO_CHAT_ID, 14)


async def test_flood_wait_blocks_followup_requests(service):
    service.backend.read_messages = AsyncMock(side_effect=FloodWaitError(None, capture=40))
    with pytest.raises(ServiceError, match="rate_limited"):
        await service.get_recent_messages(DEMO_CHAT_ID)
    with pytest.raises(ServiceError, match="rate_limited"):
        await service.get_recent_messages(DEMO_CHAT_ID)
    assert service.backend.read_messages.await_count == 1


async def test_message_text_is_bounded_without_mutating_the_backend(service):
    service.backend.messages[-1].text = "x" * 3000
    result = await service.get_recent_messages(DEMO_CHAT_ID, limit=1)
    assert len(result.messages[0].text) == 2000
    assert result.messages[0].text_truncated
    assert len(service.backend.messages[-1].text) == 3000


async def test_global_search_keeps_per_chat_positions():
    first = DemoBackend()
    second = DemoBackend()
    second.chat = Chat(id=99, title="Second chat", kind="private")
    second.messages = [
        message.model_copy(update={"chat": second.chat}) for message in second.messages
    ]
    backends = {DEMO_CHAT_ID: first, 99: second}
    backend = AsyncMock()

    async def read(chat_id, **kwargs):
        return await backends[chat_id].read_messages(chat_id, **kwargs)

    backend.read_messages.side_effect = read
    service = TelegramService(backend, list(backends), "UTC")
    messages = []
    cursor = None
    for _ in range(4):
        page = await service.search_messages("maths", limit=1, cursor=cursor)
        messages.extend((message.chat.id, message.message_id) for message in page.messages)
        cursor = page.next_cursor
    assert len(set(messages)) == 4
    assert messages == [(99, 4), (DEMO_CHAT_ID, 4), (99, 1), (DEMO_CHAT_ID, 1)]
    assert cursor is None


async def test_sender_filter_keeps_matching_messages_across_pages(service):
    for message in service.backend.messages:
        message.text = "maths homework"
    service.backend.messages[1].sender_id = 2
    ids = []
    cursor = None
    for _ in range(3):
        page = await service.search_messages("maths", sender_id=1, limit=1, cursor=cursor)
        ids.extend(message.message_id for message in page.messages)
        assert all(message.sender_id == 1 for message in page.messages)
        cursor = page.next_cursor
    assert ids == [4, 3, 1]
    assert cursor is None
    other = await service.search_messages("maths", sender_id=2)
    assert [message.message_id for message in other.messages] == [2]
    absent = await service.search_messages("maths", sender_id=999)
    assert absent.messages == []


async def test_sender_filter_cannot_be_changed_mid_search(service):
    page = await service.search_messages("maths", sender_id=1, limit=1)
    for sender_id in (2, None):
        with pytest.raises(ServiceError, match="invalid_cursor"):
            await service.search_messages("maths", sender_id=sender_id, cursor=page.next_cursor)


@pytest.mark.parametrize("sender_id", [0, True, "demo sender"])
async def test_invalid_sender_does_not_reach_telegram(service, sender_id):
    service.backend.read_messages = AsyncMock()
    with pytest.raises(ServiceError, match="invalid_sender"):
        await service.search_messages("maths", sender_id=sender_id)
    service.backend.read_messages.assert_not_awaited()


async def test_sender_filter_does_not_bypass_the_chat_allowlist(service):
    service.backend.read_messages = AsyncMock()
    with pytest.raises(ServiceError, match="chat_not_allowed"):
        await service.search_messages("maths", chat_id=123, sender_id=1)
    service.backend.read_messages.assert_not_awaited()


async def test_an_unexpected_sender_is_rejected(service):
    service.backend.read_messages = AsyncMock(return_value=service.backend.messages[:1])
    with pytest.raises(ServiceError, match="unexpected sender"):
        await service.search_messages("maths", sender_id=2)
