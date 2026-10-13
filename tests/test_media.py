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
    backend = DemoBackend()
    for message, name in zip(
        backend.messages, ["old.mp4", "other.mp4", "another.mp4", "new.mp4"], strict=True
    ):
        message.media_type = "video"
        message.file_name = name
        message.media_duration = 12.5
    return TelegramService(backend, [DEMO_CHAT_ID], "UTC")


async def test_media_search_combines_caption_date_and_sender_filters(service):
    service.backend.messages[1].sender_id = 2
    page = await service.find_media(
        "video",
        query="maths",
        sender_id=1,
        date_from=datetime(2026, 1, 2, tzinfo=UTC),
        date_to=datetime(2026, 1, 5, tzinfo=UTC),
    )
    assert [message.message_id for message in page.messages] == [4]
    assert page.messages[0].media_duration == 12.5
    assert page.messages[0].url is None
    assert (await service.find_media("photo")).messages == []


async def test_empty_filename_pages_continue_to_older_media(service):
    first = await service.find_media("video", file_name="OLD.MP4", limit=1)
    assert first.messages == []
    assert first.next_cursor is not None
    second = await service.find_media(
        "video", file_name="OLD.MP4", limit=1, cursor=first.next_cursor
    )
    assert [message.message_id for message in second.messages] == [1]
    last = await service.find_media(
        "video", file_name="OLD.MP4", limit=1, cursor=second.next_cursor
    )
    assert last.messages == []
    assert last.next_cursor is None


async def test_media_pagination_keeps_unreturned_filename_matches(service):
    found = []
    cursor = None
    for _ in range(4):
        page = await service.find_media("video", file_name=".mp4", limit=1, cursor=cursor)
        found.extend(message.message_id for message in page.messages)
        cursor = page.next_cursor
    assert found == [4, 3, 2, 1]
    assert cursor is None


async def test_media_scan_stops_at_the_lower_date_bound(service):
    page = await service.find_media(
        "video",
        file_name="old.mp4",
        limit=1,
        date_from=datetime(2026, 1, 4, tzinfo=UTC),
    )
    assert page.messages == []
    assert page.next_cursor is None


async def test_media_cursors_bind_type_and_filters_and_cannot_read_history(service):
    page = await service.find_media("video", limit=1)
    calls = [
        service.find_media("audio", cursor=page.next_cursor),
        service.find_media("video", file_name="new.mp4", cursor=page.next_cursor),
        service.find_media("video", sender_id=2, cursor=page.next_cursor),
        service.get_recent_messages(DEMO_CHAT_ID, cursor=page.next_cursor),
        service.find_documents(cursor=page.next_cursor),
    ]
    for call in calls:
        with pytest.raises(ServiceError, match="invalid_cursor"):
            await call


@pytest.mark.parametrize(
    "arguments",
    [
        {"media_type": "document"},
        {"media_type": "photo", "query": " "},
        {"media_type": "photo", "file_name": ""},
        {"media_type": "video", "limit": 0},
        {"media_type": "voice", "sender_id": 0},
    ],
)
async def test_invalid_media_filters_never_reach_telegram(service, arguments):
    service.backend.read_messages = AsyncMock()
    with pytest.raises(ServiceError, match="invalid_"):
        await service.find_media(**arguments)
    service.backend.read_messages.assert_not_awaited()


async def test_media_search_cannot_bypass_chat_access(service):
    service.backend.read_messages = AsyncMock()
    with pytest.raises(ServiceError, match="chat_not_allowed"):
        await service.find_media("photo", chat_id=999)
    service.backend.read_messages.assert_not_awaited()


@pytest.mark.parametrize(
    "changed",
    [
        {"media_type": "photo"},
        {"chat": Chat(id=999, title="Other", kind="private")},
        {"sender_id": 2},
    ],
)
async def test_media_results_check_type_chat_and_sender(service, changed):
    service.backend.read_messages = AsyncMock(
        return_value=[service.backend.messages[0].model_copy(update=changed)]
    )
    with pytest.raises(ServiceError, match="invalid_source"):
        await service.find_media("video", sender_id=1)


async def test_document_reads_still_accept_document_based_media(service):
    result = await service.find_documents(file_name="old.mp4")
    assert [message.message_id for message in result.messages] == [1]
    assert result.messages[0].media_type == "video"


def attached_message(kind):
    date = datetime(2026, 1, 1, tzinfo=UTC)
    if kind == "photo":
        media = types.MessageMediaPhoto(
            photo=types.Photo(
                id=1,
                access_hash=1,
                file_reference=b"fictional",
                date=date,
                sizes=[types.PhotoSize(type="x", w=640, h=480, size=1024)],
                dc_id=1,
            )
        )
    else:
        attributes = [types.DocumentAttributeFilename("test.bin")]
        if kind in ("voice", "audio"):
            attributes.append(types.DocumentAttributeAudio(duration=12, voice=kind == "voice"))
        if kind in ("video", "video_note", "animation", "sticker"):
            attributes.append(
                types.DocumentAttributeVideo(
                    duration=12.5, w=640, h=480, round_message=kind == "video_note"
                )
            )
        if kind == "animation":
            attributes.append(types.DocumentAttributeAnimated())
        if kind == "sticker":
            attributes.append(
                types.DocumentAttributeSticker(alt="test", stickerset=types.InputStickerSetEmpty())
            )
        media = types.MessageMediaDocument(
            document=types.Document(
                id=1,
                access_hash=1,
                file_reference=b"fictional",
                date=date,
                mime_type="application/octet-stream",
                size=1024,
                dc_id=1,
                attributes=attributes,
            )
        )
    return types.Message(
        id=8, peer_id=types.PeerUser(123), date=date, message="fictional caption", media=media
    )


@pytest.mark.parametrize(
    "kind,filter_type",
    [
        ("photo", types.InputMessagesFilterPhotos),
        ("video", types.InputMessagesFilterVideo),
        ("voice", types.InputMessagesFilterVoice),
        ("audio", types.InputMessagesFilterMusic),
    ],
)
async def test_native_media_search_uses_bounded_filters_and_never_downloads(kind, filter_type):
    backend = TelethonBackend.__new__(TelethonBackend)
    backend.client = AsyncMock()
    backend.get_chat = AsyncMock(return_value=Chat(id=123, title="Demo", kind="private"))
    calls = []

    async def iterate(peer, **kwargs):
        calls.append((peer, kwargs))
        yield attached_message(kind)

    backend.client.iter_messages = iterate
    date_to = datetime(2026, 2, 1, tzinfo=UTC)
    result = await backend.read_messages(
        123,
        media_type=kind,
        limit=3,
        query="caption",
        before_id=15,
        date_to=date_to,
        sender_id=123,
    )
    assert calls[0][0] == 123
    options = calls[0][1].copy()
    assert isinstance(options.pop("filter"), filter_type)
    assert options == {
        "limit": 3,
        "search": "caption",
        "offset_id": 15,
        "offset_date": date_to,
        "from_user": 123,
    }
    assert result[0].media_type == kind
    assert result[0].file_size == 1024
    if kind in ("voice", "audio"):
        assert result[0].media_duration == 12
        assert result[0].media_width is None
    else:
        assert result[0].media_width == 640
        assert result[0].media_height == 480
        assert result[0].media_duration == (12.5 if kind == "video" else None)
    backend.client.download_media.assert_not_called()
    backend.client.download_file.assert_not_called()
    backend.client.send_read_acknowledge.assert_not_called()


@pytest.mark.parametrize("kind", ["video_note", "animation", "sticker", "document"])
def test_video_subtypes_are_not_mislabelled_as_regular_video(kind):
    backend = TelethonBackend.__new__(TelethonBackend)
    chat = Chat(id=123, title="Demo", kind="private")
    assert backend._message(chat, attached_message(kind)).media_type == kind


def test_link_previews_are_not_attached_photos():
    backend = TelethonBackend.__new__(TelethonBackend)
    message = attached_message("photo")
    message.media = types.MessageMediaWebPage(
        webpage=types.WebPage(
            id=1,
            url="https://example.com",
            display_url="example.com",
            hash=1,
            photo=message.media.photo,
        )
    )
    result = backend._message(Chat(id=123, title="Demo", kind="private"), message)
    assert result.media_type is None
    assert result.file_size is None
    assert result.media_width is None
