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


def add_documents(backend, names):
    for message, name in zip(backend.messages, names, strict=True):
        message.media_type = "document"
        message.file_name = name


async def test_filename_search_finds_a_document_without_a_matching_caption(service):
    page = await service.find_documents(file_name="MATHS.PDF")
    assert [message.message_id for message in page.messages] == [2]
    assert "maths" not in page.messages[0].text.casefold()
    assert page.messages[0].mime_type == "application/pdf"
    assert page.messages[0].file_size == 1024
    assert page.messages[0].url is None
    assert page.next_cursor is None
    caption = await service.find_documents(query="pinned")
    assert [message.message_id for message in caption.messages] == [2]


async def test_empty_document_pages_continue_without_skipping_matches(service):
    add_documents(service.backend, ["old.pdf", "other.txt", "another.txt", "new.pdf"])
    first = await service.find_documents(file_name="old.pdf", limit=1)
    assert first.messages == []
    assert first.next_cursor is not None
    second = await service.find_documents(file_name="old.pdf", limit=1, cursor=first.next_cursor)
    assert [message.message_id for message in second.messages] == [1]
    assert second.next_cursor is not None
    last = await service.find_documents(file_name="old.pdf", limit=1, cursor=second.next_cursor)
    assert last.messages == []
    assert last.next_cursor is None


async def test_document_search_does_not_skip_unreturned_matches(service):
    add_documents(service.backend, ["one.pdf", "two.pdf", "three.pdf", "four.pdf"])
    ids = []
    cursor = None
    for _ in range(4):
        page = await service.find_documents(file_name=".pdf", limit=1, cursor=cursor)
        ids.extend(message.message_id for message in page.messages)
        cursor = page.next_cursor
    assert ids == [4, 3, 2, 1]
    assert cursor is None


async def test_document_scan_stops_at_the_lower_date_bound(service):
    add_documents(service.backend, ["old.pdf", "other.txt", "another.txt", "new.pdf"])
    page = await service.find_documents(
        file_name="old.pdf", limit=1, date_from=datetime(2026, 1, 4, tzinfo=UTC)
    )
    assert page.messages == []
    assert page.next_cursor is None


async def test_document_filters_combine_and_bind_the_cursor(service):
    add_documents(service.backend, ["one.pdf", "two.pdf", "three.pdf", "four.pdf"])
    service.backend.messages[1].sender_id = 2
    page = await service.find_documents(
        sender_id=1, date_to=datetime(2026, 1, 4, tzinfo=UTC), file_name=".pdf", limit=1
    )
    assert [message.message_id for message in page.messages] == [3]
    with pytest.raises(ServiceError, match="invalid_cursor"):
        await service.find_documents(file_name=".txt", cursor=page.next_cursor)
    with pytest.raises(ServiceError, match="invalid_cursor"):
        await service.search_messages("maths", cursor=page.next_cursor)


async def test_document_search_enforces_the_chat_allowlist(service):
    service.backend.read_messages = AsyncMock()
    with pytest.raises(ServiceError, match="chat_not_allowed"):
        await service.find_documents(chat_id=999)
    service.backend.read_messages.assert_not_awaited()


@pytest.mark.parametrize("filters", [{"file_name": " "}, {"query": ""}, {"sender_id": 0}])
async def test_invalid_document_filters_do_not_reach_telegram(service, filters):
    service.backend.read_messages = AsyncMock()
    with pytest.raises(ServiceError, match="invalid_"):
        await service.find_documents(**filters)
    service.backend.read_messages.assert_not_awaited()


async def test_non_document_results_are_rejected(service):
    service.backend.read_messages = AsyncMock(return_value=service.backend.messages[:1])
    with pytest.raises(ServiceError, match="expected a document"):
        await service.find_documents()


async def test_document_pagination_merges_chats_without_losing_matches():
    first, second = DemoBackend(), DemoBackend()
    second.chat = Chat(id=99, title="Second chat", kind="private")
    second.messages = [
        message.model_copy(update={"chat": second.chat}) for message in second.messages
    ]
    add_documents(first, ["one.pdf", "other.txt", "three.pdf", "four.pdf"])
    add_documents(second, ["one.pdf", "other.txt", "three.pdf", "four.pdf"])
    backends = {DEMO_CHAT_ID: first, 99: second}
    backend = AsyncMock()

    async def read(chat_id, **kwargs):
        return await backends[chat_id].read_messages(chat_id, **kwargs)

    backend.read_messages.side_effect = read
    service = TelegramService(backend, list(backends), "UTC")
    found = []
    cursor = None
    for _ in range(10):
        page = await service.find_documents(file_name=".pdf", limit=1, cursor=cursor)
        found.extend((message.chat.id, message.message_id) for message in page.messages)
        cursor = page.next_cursor
        if cursor is None:
            break
    assert found == [
        (99, 4),
        (DEMO_CHAT_ID, 4),
        (99, 3),
        (DEMO_CHAT_ID, 3),
        (99, 1),
        (DEMO_CHAT_ID, 1),
    ]
    assert cursor is None


async def test_telethon_document_reads_only_return_metadata():
    backend = TelethonBackend.__new__(TelethonBackend)
    backend.client = AsyncMock()
    backend.get_chat = AsyncMock(
        return_value=Chat(id=DEMO_CHAT_ID, title="Study group", kind="supergroup")
    )
    calls = []

    async def iterate(peer, **kwargs):
        calls.append((peer, kwargs))
        yield types.Message(
            id=2,
            peer_id=types.PeerChannel(1234567890),
            date=datetime(2026, 1, 1, tzinfo=UTC),
            message="homework",
            media=types.MessageMediaDocument(
                document=types.Document(
                    id=1,
                    access_hash=1,
                    file_reference=b"fictional-reference",
                    date=datetime(2026, 1, 1, tzinfo=UTC),
                    mime_type="application/pdf",
                    size=1024,
                    dc_id=1,
                    attributes=[types.DocumentAttributeFilename("discrete_maths.pdf")],
                )
            ),
        )

    backend.client.iter_messages = iterate
    result = await backend.read_messages(DEMO_CHAT_ID, documents_only=True, limit=2)
    assert calls[0][0] == DEMO_CHAT_ID
    assert isinstance(calls[0][1]["filter"], types.InputMessagesFilterDocument)
    assert calls[0][1]["limit"] == 2
    assert result[0].file_name == "discrete_maths.pdf"
    assert result[0].mime_type == "application/pdf"
    assert result[0].file_size == 1024
    backend.client.download_media.assert_not_called()
    backend.client.download_file.assert_not_called()
