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
    return TelegramService(DemoBackend(), [DEMO_CHAT_ID], "Asia/Nicosia")


async def test_long_unicode_text_can_be_read_without_gaps_or_source_mutation(service):
    original = "aб🙂\n" * 1200
    source = service.backend.messages[0]
    source.text = original
    source.edited_at = datetime(2026, 1, 2, tzinfo=UTC)
    chunks = []
    offset = 0
    while True:
        result = await service.get_message(DEMO_CHAT_ID, 1, text_offset=offset, text_limit=777)
        assert result.text_offset == offset
        assert result.total_text_length == len(original)
        assert len(result.message.text) <= 777
        assert result.message.text_truncated
        assert result.message.date.utcoffset().total_seconds() == 7200
        assert result.message.edited_at.utcoffset().total_seconds() == 7200
        chunks.append(result.message.text)
        offset = result.next_text_offset
        if offset is None:
            break
    assert "".join(chunks) == original
    assert source.text == original
    assert not source.text_truncated


async def test_short_document_and_empty_service_messages_keep_their_metadata(service):
    result = await service.get_message(DEMO_CHAT_ID, 2)
    assert result.next_text_offset is None
    assert not result.message.text_truncated
    assert result.message.file_name == "discrete_maths.pdf"
    source = service.backend.messages[0]
    source.text = ""
    source.kind = "service"
    result = await service.get_message(DEMO_CHAT_ID, 1)
    assert result.total_text_length == 0
    assert result.message.kind == "service"
    assert result.next_text_offset is None


async def test_missing_message_and_offsets_after_an_edit_are_safe_errors(service):
    with pytest.raises(ServiceError, match="message_not_found"):
        await service.get_message(DEMO_CHAT_ID, 999)
    source = service.backend.messages[0]
    source.text = "x" * 2500
    result = await service.get_message(DEMO_CHAT_ID, 1)
    source.text = "a much shorter edited message"
    with pytest.raises(ServiceError, match="invalid_text_offset"):
        await service.get_message(DEMO_CHAT_ID, 1, text_offset=result.next_text_offset)


@pytest.mark.parametrize(
    "message_id,offset,limit",
    [
        (0, 0, 2000),
        (True, 0, 2000),
        (1, -1, 2000),
        (1, 1000001, 2000),
        (1, True, 2000),
        (1, 0, 0),
        (1, 0, 2001),
        (1, 0, True),
    ],
)
async def test_invalid_message_arguments_never_reach_telegram(service, message_id, offset, limit):
    service.backend.get_message = AsyncMock()
    with pytest.raises(ServiceError, match="invalid_message_read"):
        await service.get_message(DEMO_CHAT_ID, message_id, offset, limit)
    service.backend.get_message.assert_not_awaited()


async def test_message_reads_cannot_bypass_chat_access(service):
    service.backend.get_message = AsyncMock()
    with pytest.raises(ServiceError, match="chat_not_allowed"):
        await service.get_message(999, 1)
    service.backend.get_message.assert_not_awaited()


@pytest.mark.parametrize(
    "changed", [{"message_id": 9}, {"chat": Chat(id=999, title="Other", kind="private")}]
)
async def test_wrong_message_source_is_rejected(service, changed):
    service.backend.get_message = AsyncMock(
        return_value=service.backend.messages[0].model_copy(update=changed)
    )
    with pytest.raises(ServiceError, match="invalid_source"):
        await service.get_message(DEMO_CHAT_ID, 1)


async def test_telethon_fetches_one_id_from_the_requested_chat():
    backend = TelethonBackend.__new__(TelethonBackend)
    backend.client = AsyncMock()
    backend.get_chat = AsyncMock(return_value=Chat(id=123, title="Demo", kind="private"))
    backend.client.get_messages.return_value = types.Message(
        id=8,
        peer_id=types.PeerUser(123),
        date=datetime(2026, 1, 1, tzinfo=UTC),
        message="fictional message",
    )
    assert (await backend.get_message(123, 8)).text == "fictional message"
    backend.client.get_messages.assert_awaited_once_with(123, ids=8)
    backend.client.get_messages.return_value = types.MessageEmpty(id=9, peer_id=types.PeerUser(123))
    assert await backend.get_message(123, 9) is None
