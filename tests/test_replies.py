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


async def test_chain_follows_parents_instead_of_chronological_neighbors(service):
    chain = await service.get_reply_chain(DEMO_CHAT_ID, 4)
    assert [message.message_id for message in chain.messages] == [1, 2, 4]
    assert chain.stop_reason == "end"
    assert chain.anchor_id == 4
    assert chain.next_message_id is None
    assert chain.messages[1].file_name == "discrete_maths.pdf"
    assert chain.messages[0].date.utcoffset().total_seconds() == 7200


async def test_chain_continuation_does_not_read_past_the_limit(service):
    original = service.backend.get_message
    service.backend.get_message = AsyncMock(side_effect=original)
    first = await service.get_reply_chain(DEMO_CHAT_ID, 4, limit=2)
    assert [message.message_id for message in first.messages] == [2, 4]
    assert first.stop_reason == "limit"
    assert first.next_message_id == 1
    assert service.backend.get_message.await_count == 2
    second = await service.get_reply_chain(DEMO_CHAT_ID, first.next_message_id, limit=2)
    assert [message.message_id for message in second.messages + first.messages] == [1, 2, 4]
    assert second.stop_reason == "end"


async def test_deleted_parent_returns_partial_chain_and_missing_id(service):
    service.backend.messages[1].reply_to_message_id = 99
    chain = await service.get_reply_chain(DEMO_CHAT_ID, 4)
    assert [message.message_id for message in chain.messages] == [2, 4]
    assert chain.stop_reason == "missing"
    assert chain.missing_message_id == 99
    assert chain.next_message_id is None
    with pytest.raises(ServiceError, match="message_not_found"):
        await service.get_reply_chain(DEMO_CHAT_ID, 99)


@pytest.mark.parametrize(
    "changed,reason",
    [
        ({"reply_to_chat_id": 99, "reply_to_message_id": 4}, "other_chat"),
        ({"reply_to_scheduled": True, "reply_to_message_id": 4}, "scheduled"),
    ],
)
async def test_chain_does_not_follow_external_or_scheduled_replies(service, changed, reason):
    service.allowed_chats.append(99)
    source = service.backend.messages[-1].model_copy(update=changed)
    service.backend.get_message = AsyncMock(return_value=source)
    chain = await service.get_reply_chain(DEMO_CHAT_ID, 4)
    assert chain.stop_reason == reason
    assert len(chain.messages) == 1
    assert chain.next_message_id is None
    service.backend.get_message.assert_awaited_once_with(DEMO_CHAT_ID, 4)


async def test_cycles_are_rejected_without_repeated_reads(service):
    service.backend.messages[1].reply_to_message_id = 4
    original = service.backend.get_message
    service.backend.get_message = AsyncMock(side_effect=original)
    with pytest.raises(ServiceError, match="cyclic"):
        await service.get_reply_chain(DEMO_CHAT_ID, 4)
    assert service.backend.get_message.await_count == 2


async def test_chain_keeps_text_bounded_without_changing_source(service):
    for message in service.backend.messages:
        message.text = "x" * 3000
    chain = await service.get_reply_chain(DEMO_CHAT_ID, 4)
    assert all(len(message.text) == 2000 and message.text_truncated for message in chain.messages)
    assert all(len(message.text) == 3000 for message in service.backend.messages)


@pytest.mark.parametrize("method", ["get_reply_chain", "get_thread_replies"])
async def test_reply_reads_enforce_access_before_touching_telegram(service, method):
    service.backend.get_message = AsyncMock()
    service.backend.get_chat = AsyncMock()
    service.backend.read_replies = AsyncMock()
    with pytest.raises(ServiceError, match="chat_not_allowed"):
        await getattr(service, method)(999, 4)
    service.backend.get_message.assert_not_awaited()
    service.backend.get_chat.assert_not_awaited()
    service.backend.read_replies.assert_not_awaited()


@pytest.mark.parametrize(
    "method,message_id,limit",
    [
        ("get_reply_chain", 0, 10),
        ("get_reply_chain", True, 10),
        ("get_reply_chain", 1, 11),
        ("get_reply_chain", 1, False),
        ("get_thread_replies", -1, 20),
        ("get_thread_replies", 1, 51),
    ],
)
async def test_reply_bounds_are_checked_before_backend_reads(service, method, message_id, limit):
    service.backend = AsyncMock()
    with pytest.raises(ServiceError, match="invalid_"):
        await getattr(service, method)(DEMO_CHAT_ID, message_id, limit)
    service.backend.get_message.assert_not_awaited()
    service.backend.get_chat.assert_not_awaited()


async def test_reply_chain_rejects_wrong_parent_source(service):
    service.backend.get_message = AsyncMock(
        side_effect=[
            service.backend.messages[-1],
            service.backend.messages[1].model_copy(update={"message_id": 99}),
        ]
    )
    with pytest.raises(ServiceError, match="invalid_source"):
        await service.get_reply_chain(DEMO_CHAT_ID, 4)


async def test_thread_pages_exclude_root_and_keep_nested_replies(service):
    first = await service.get_thread_replies(DEMO_CHAT_ID, 1, limit=1)
    second = await service.get_thread_replies(DEMO_CHAT_ID, 1, limit=1, cursor=first.next_cursor)
    assert [message.message_id for message in first.messages + second.messages] == [4, 2]
    assert first.root_message_id == 1
    assert second.next_cursor is None
    assert 3 not in [message.message_id for message in first.messages + second.messages]
    assert (await service.get_thread_replies(DEMO_CHAT_ID, 3)).messages == []


async def test_thread_cursor_binds_chat_root_and_read_type(service):
    first = await service.get_thread_replies(DEMO_CHAT_ID, 1, limit=1)
    service.allowed_chats.append(99)
    calls = [
        service.get_thread_replies(DEMO_CHAT_ID, 3, cursor=first.next_cursor),
        service.get_thread_replies(99, 1, cursor=first.next_cursor),
        service.get_recent_messages(DEMO_CHAT_ID, cursor=first.next_cursor),
    ]
    for call in calls:
        with pytest.raises(ServiceError, match="invalid_cursor"):
            await call


@pytest.mark.parametrize("kind", ["private", "group", "channel"])
async def test_thread_reads_do_not_search_private_chats_or_follow_channel_comments(service, kind):
    service.backend.chat.kind = kind
    service.backend.get_message = AsyncMock()
    service.backend.read_replies = AsyncMock()
    with pytest.raises(ServiceError, match="unsupported_thread"):
        await service.get_thread_replies(DEMO_CHAT_ID, 1)
    service.backend.get_message.assert_not_awaited()
    service.backend.read_replies.assert_not_awaited()


async def test_thread_rejects_missing_roots_and_reply_ids_used_as_roots(service):
    with pytest.raises(ServiceError, match="message_not_found"):
        await service.get_thread_replies(DEMO_CHAT_ID, 99)
    for message_id in (2, 4):
        with pytest.raises(ServiceError, match="invalid_thread"):
            await service.get_thread_replies(DEMO_CHAT_ID, message_id)


@pytest.mark.parametrize(
    "changed",
    [
        {"reply_to_message_id": 3, "thread_root_message_id": None},
        {"chat": Chat(id=99, title="Other", kind="supergroup")},
        {"reply_to_chat_id": 99},
        {"reply_to_scheduled": True},
    ],
)
async def test_thread_rejects_unrelated_messages_and_external_peers(service, changed):
    service.backend.read_replies = AsyncMock(
        return_value=[service.backend.messages[1].model_copy(update=changed)]
    )
    with pytest.raises(ServiceError, match="invalid_source"):
        await service.get_thread_replies(DEMO_CHAT_ID, 1)


async def test_thread_rejects_duplicate_ids_and_nonadvancing_offsets(service):
    first = await service.get_thread_replies(DEMO_CHAT_ID, 1, limit=1)
    message = service.backend.messages[-1]
    service.backend.read_replies = AsyncMock(return_value=[message, message])
    with pytest.raises(ServiceError, match="invalid_source"):
        await service.get_thread_replies(DEMO_CHAT_ID, 1)
    service.backend.read_replies.return_value = [message]
    with pytest.raises(ServiceError, match="invalid_source"):
        await service.get_thread_replies(DEMO_CHAT_ID, 1, cursor=first.next_cursor)


def native_message(peer=None, reply=None):
    return types.Message(
        id=8,
        peer_id=peer or types.PeerChannel(1234567890),
        date=datetime(2026, 1, 1, tzinfo=UTC),
        message="fictional reply",
        reply_to=reply,
    )


def test_native_reply_metadata_preserves_chat_and_thread_identity():
    backend = TelethonBackend.__new__(TelethonBackend)
    chat = Chat(id=DEMO_CHAT_ID, title="Demo", kind="supergroup")
    result = backend._message(
        chat,
        native_message(
            reply=types.MessageReplyHeader(
                reply_to_msg_id=4,
                reply_to_top_id=1,
            )
        ),
    )
    assert result.reply_to_message_id == 4
    assert result.reply_to_chat_id == DEMO_CHAT_ID
    assert result.thread_root_message_id == 1
    external = backend._message(
        chat,
        native_message(
            reply=types.MessageReplyHeader(
                reply_to_msg_id=8,
                reply_to_peer_id=types.PeerUser(99),
                reply_to_scheduled=True,
            )
        ),
    )
    assert external.reply_to_chat_id == 99
    assert external.reply_to_scheduled
    with pytest.raises(ValueError, match="unexpected message peer"):
        backend._message(chat, native_message(peer=types.PeerChannel(999)))


async def test_native_threads_use_bounded_reply_reads_and_never_mark_read():
    backend = TelethonBackend.__new__(TelethonBackend)
    backend.client = AsyncMock()
    backend.get_chat = AsyncMock(
        return_value=Chat(id=DEMO_CHAT_ID, title="Demo", kind="supergroup")
    )
    calls = []

    async def iterate(peer, **kwargs):
        calls.append((peer, kwargs))
        yield native_message(reply=types.MessageReplyHeader(reply_to_msg_id=1))

    backend.client.iter_messages = iterate
    result = await backend.read_replies(DEMO_CHAT_ID, 1, limit=3, before_id=15)
    assert calls == [(DEMO_CHAT_ID, {"reply_to": 1, "limit": 3, "offset_id": 15})]
    assert result[0].reply_to_message_id == 1
    backend.client.send_read_acknowledge.assert_not_called()
    backend.client.download_media.assert_not_called()
    backend.get_chat.return_value.kind = "channel"
    with pytest.raises(ValueError, match="supergroup"):
        await backend.read_replies(DEMO_CHAT_ID, 1, limit=3)
    assert len(calls) == 1
