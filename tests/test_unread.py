from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from telethon.tl import functions, types

from mason.telegram.client import TelethonBackend
from mason.telegram.demo import DEMO_CHAT_ID, DemoBackend
from mason.telegram.models import Chat
from mason.telegram.service import ServiceError, TelegramService


@pytest.fixture
def service():
    return TelegramService(DemoBackend(), [DEMO_CHAT_ID], "UTC")


async def test_unread_pages_are_incoming_and_do_not_change_read_state(service):
    service.backend.messages[-1].outgoing = True
    first = await service.get_unread_messages(DEMO_CHAT_ID)
    second = await service.get_unread_messages(DEMO_CHAT_ID)
    assert [message.message_id for message in first.messages] == [3]
    assert second == first
    assert first.read_inbox_max_id == 2
    assert first.unread_count == 1
    assert service.backend.read_inbox_max_id == 2


async def test_empty_outgoing_pages_can_continue_without_skipping_unread(service):
    service.backend.read_inbox_max_id = 0
    for message in service.backend.messages[2:]:
        message.outgoing = True
    first = await service.get_unread_messages(DEMO_CHAT_ID, limit=1)
    assert first.messages == []
    assert first.next_cursor is not None
    second = await service.get_unread_messages(DEMO_CHAT_ID, limit=1, cursor=first.next_cursor)
    third = await service.get_unread_messages(DEMO_CHAT_ID, limit=1, cursor=second.next_cursor)
    assert [message.message_id for message in second.messages + third.messages] == [2, 1]
    assert third.next_cursor is None


async def test_unread_pagination_preserves_unreturned_incoming_messages(service):
    service.backend.read_inbox_max_id = 0
    found = []
    cursor = None
    for _ in range(4):
        page = await service.get_unread_messages(DEMO_CHAT_ID, limit=1, cursor=cursor)
        found.extend(message.message_id for message in page.messages)
        cursor = page.next_cursor
    assert found == [4, 3, 2, 1]
    assert cursor is None


async def test_manual_unread_badge_does_not_make_read_messages_unread(service):
    service.backend.read_inbox_max_id = 4
    service.backend.unread_mark = True
    service.backend.read_messages = AsyncMock()
    page = await service.get_unread_messages(DEMO_CHAT_ID)
    assert page.messages == []
    assert page.unread_count == 0
    assert page.unread_mark
    assert page.next_cursor is None
    service.backend.read_messages.assert_not_awaited()


async def test_reading_in_another_client_invalidates_unread_continuation(service):
    first = await service.get_unread_messages(DEMO_CHAT_ID, limit=1)
    service.backend.read_inbox_max_id = 4
    service.backend.read_messages = AsyncMock()
    with pytest.raises(ServiceError, match="invalid_cursor"):
        await service.get_unread_messages(DEMO_CHAT_ID, cursor=first.next_cursor)
    service.backend.read_messages.assert_not_awaited()


async def test_unread_cursor_cannot_be_used_for_other_reads_or_chats(service):
    first = await service.get_unread_messages(DEMO_CHAT_ID, limit=1)
    with pytest.raises(ServiceError, match="invalid_cursor"):
        await service.get_recent_messages(DEMO_CHAT_ID, cursor=first.next_cursor)
    service.allowed_chats.append(99)
    state = await service.backend.get_read_state(DEMO_CHAT_ID)
    service.backend.get_read_state = AsyncMock(
        return_value=state.model_copy(update={"chat_id": 99})
    )
    with pytest.raises(ServiceError, match="invalid_cursor"):
        await service.get_unread_messages(99, cursor=first.next_cursor)


@pytest.mark.parametrize("limit", [0, 51, True])
async def test_unread_limits_are_checked_before_dialog_access(service, limit):
    service.backend.get_read_state = AsyncMock()
    with pytest.raises(ServiceError, match="invalid_limit"):
        await service.get_unread_messages(DEMO_CHAT_ID, limit=limit)
    service.backend.get_read_state.assert_not_awaited()


async def test_unread_reads_cannot_bypass_chat_access(service):
    service.backend.get_read_state = AsyncMock()
    with pytest.raises(ServiceError, match="chat_not_allowed"):
        await service.get_unread_messages(99)
    service.backend.get_read_state.assert_not_awaited()


@pytest.mark.parametrize(
    "changed,error",
    [
        ({"chat_id": 99}, "invalid_source"),
        ({"topic_based": True}, "unsupported_unread"),
    ],
)
async def test_wrong_dialog_sources_and_topic_read_markers_are_refused(service, changed, error):
    state = await service.backend.get_read_state(DEMO_CHAT_ID)
    service.backend.get_read_state = AsyncMock(return_value=state.model_copy(update=changed))
    service.backend.read_messages = AsyncMock()
    with pytest.raises(ServiceError, match=error):
        await service.get_unread_messages(DEMO_CHAT_ID)
    service.backend.read_messages.assert_not_awaited()


@pytest.mark.parametrize(
    "changed",
    [
        {"message_id": 2},
        {"chat": Chat(id=99, title="Other", kind="private")},
    ],
)
async def test_unread_messages_must_belong_to_the_chat_and_follow_its_marker(service, changed):
    service.backend.read_messages = AsyncMock(
        return_value=[service.backend.messages[-1].model_copy(update=changed)]
    )
    with pytest.raises(ServiceError, match="invalid_source"):
        await service.get_unread_messages(DEMO_CHAT_ID)


def dialog(peer=None):
    return types.Dialog(
        peer=peer or types.PeerUser(123),
        top_message=8,
        read_inbox_max_id=2,
        read_outbox_max_id=4,
        unread_count=2,
        unread_mentions_count=0,
        unread_reactions_count=0,
        unread_poll_votes_count=0,
        notify_settings=types.PeerNotifySettings(),
        unread_mark=True,
    )


async def test_native_dialog_read_is_scoped_to_one_peer_and_never_marks_read():
    backend = TelethonBackend.__new__(TelethonBackend)
    backend.client = AsyncMock(return_value=SimpleNamespace(dialogs=[dialog()]))
    backend.client.get_entity.return_value = types.User(id=123, first_name="Demo")
    backend.client.get_input_entity.return_value = types.InputPeerUser(123, 1)
    state = await backend.get_read_state(123)
    assert state.read_inbox_max_id == 2
    assert state.unread_count == 2
    assert state.unread_mark
    request = backend.client.call_args.args[0]
    assert isinstance(request, functions.messages.GetPeerDialogsRequest)
    assert len(request.peers) == 1
    assert request.peers[0].peer.user_id == 123
    backend.client.send_read_acknowledge.assert_not_called()
    backend.client.return_value.dialogs = [dialog(types.PeerUser(99))]
    with pytest.raises(ValueError, match="unexpected dialog"):
        await backend.get_read_state(123)
    backend.client.reset_mock()
    backend.client.get_entity.return_value = types.User(id=99, first_name="Other")
    with pytest.raises(ValueError, match="unexpected dialog"):
        await backend.get_read_state(123)
    backend.client.assert_not_awaited()


async def test_native_history_read_passes_the_lower_marker_and_keeps_outgoing_flag():
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
            message="fictional outgoing message",
            out=True,
        )

    backend.client.iter_messages = iterate
    result = await backend.read_messages(123, limit=3, before_id=10, min_id=2)
    assert calls[0][0] == 123
    assert calls[0][1]["min_id"] == 2
    assert calls[0][1]["offset_id"] == 10
    assert calls[0][1]["limit"] == 3
    assert result[0].outgoing
    backend.client.send_read_acknowledge.assert_not_called()
