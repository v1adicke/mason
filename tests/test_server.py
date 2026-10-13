import jwt
import pytest
from mcp import Client
from starlette.testclient import TestClient

from mason.server import create_app, create_server
from mason.telegram.demo import DEMO_CHAT_ID


@pytest.fixture
def http_client(auth_setup):
    verifier, key, claims = auth_setup
    app = create_app(verifier.settings, verifier=verifier)
    token = jwt.encode(claims, key, algorithm="HS256")
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json, text/event-stream",
    }
    with TestClient(app, base_url="http://127.0.0.1:8000", headers=headers) as client:
        yield client


def rpc(client, method, params=None, request_id=1):
    return client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}},
    )


def test_authenticated_http_search_and_context(http_client):
    initialized = rpc(
        http_client,
        "initialize",
        {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {"name": "mason-smoke-test", "version": "0.1.0"},
        },
    )
    assert initialized.status_code == 200
    assert initialized.json()["result"]["serverInfo"]["name"] == "Mason"
    tools = rpc(http_client, "tools/list").json()["result"]["tools"]
    assert {tool["name"] for tool in tools} == {
        "list_chats",
        "search_messages",
        "find_documents",
        "find_media",
        "get_message",
        "get_reply_chain",
        "get_thread_replies",
        "get_unread_messages",
        "get_pinned_messages",
        "get_message_context",
        "get_recent_messages",
    }
    assert all(tool["annotations"]["readOnlyHint"] for tool in tools)
    result = rpc(
        http_client, "tools/call", {"name": "search_messages", "arguments": {"query": "maths"}}
    ).json()["result"]
    assert not result.get("isError")
    found = result["structuredContent"]["messages"][0]
    context = rpc(
        http_client,
        "tools/call",
        {
            "name": "get_message_context",
            "arguments": {"chat_id": found["chat"]["id"], "message_id": found["message_id"]},
        },
    ).json()["result"]
    assert len(context["structuredContent"]["messages"]) == 4


def test_http_rejects_missing_or_invalid_tokens(http_client):
    for authorization in ("", "Bearer invalid"):
        response = http_client.post("/mcp", json={}, headers={"Authorization": authorization})
        assert response.status_code == 401
        assert "resource_metadata=" in response.headers["WWW-Authenticate"]


def test_authenticated_http_sender_filter(http_client):
    tools = rpc(http_client, "tools/list").json()["result"]["tools"]
    search = next(tool for tool in tools if tool["name"] == "search_messages")
    assert "sender_id" in search["inputSchema"]["properties"]
    assert "sender_id" not in search["inputSchema"]["required"]
    for sender_id, expected_ids in ((1, [4, 1]), (999, [])):
        result = rpc(
            http_client,
            "tools/call",
            {"name": "search_messages", "arguments": {"query": "maths", "sender_id": sender_id}},
        ).json()["result"]
        assert not result.get("isError")
        assert [message["message_id"] for message in result["structuredContent"]["messages"]] == (
            expected_ids
        )


def test_authenticated_http_document_lookup(http_client):
    result = rpc(
        http_client,
        "tools/call",
        {"name": "find_documents", "arguments": {"file_name": "maths.pdf"}},
    ).json()["result"]
    assert not result.get("isError")
    files = result["structuredContent"]["messages"]
    assert [message["message_id"] for message in files] == [2]
    assert files[0]["file_name"] == "discrete_maths.pdf"
    assert files[0]["mime_type"] == "application/pdf"
    assert files[0]["file_size"] == 1024


def test_authenticated_http_pinned_messages(http_client):
    result = rpc(
        http_client,
        "tools/call",
        {
            "name": "get_pinned_messages",
            "arguments": {"chat_id": DEMO_CHAT_ID, "limit": 5},
        },
    ).json()["result"]
    assert not result.get("isError")
    messages = result["structuredContent"]["messages"]
    assert [message["message_id"] for message in messages] == [2]
    assert messages[0]["pinned"]
    assert result["structuredContent"]["next_cursor"] is None
    denied = rpc(
        http_client,
        "tools/call",
        {
            "name": "get_pinned_messages",
            "arguments": {"chat_id": 999},
        },
    ).json()["result"]
    assert denied["isError"]
    assert "chat_not_allowed" in denied["content"][0]["text"]


def test_authenticated_http_reply_chain_and_thread(http_client):
    chain = rpc(
        http_client,
        "tools/call",
        {"name": "get_reply_chain", "arguments": {"chat_id": DEMO_CHAT_ID, "message_id": 4}},
    ).json()["result"]
    assert not chain.get("isError")
    assert [message["message_id"] for message in chain["structuredContent"]["messages"]] == [
        1,
        2,
        4,
    ]
    assert chain["structuredContent"]["stop_reason"] == "end"
    first = rpc(
        http_client,
        "tools/call",
        {
            "name": "get_thread_replies",
            "arguments": {"chat_id": DEMO_CHAT_ID, "message_id": 1, "limit": 1},
        },
    ).json()["result"]
    assert not first.get("isError")
    assert first["structuredContent"]["root_message_id"] == 1
    assert first["structuredContent"]["messages"][0]["message_id"] == 4
    second = rpc(
        http_client,
        "tools/call",
        {
            "name": "get_thread_replies",
            "arguments": {
                "chat_id": DEMO_CHAT_ID,
                "message_id": 1,
                "cursor": first["structuredContent"]["next_cursor"],
            },
        },
    ).json()["result"]
    assert [message["message_id"] for message in second["structuredContent"]["messages"]] == [2]
    assert second["structuredContent"]["next_cursor"] is None
    for tool in ("get_reply_chain", "get_thread_replies"):
        denied = rpc(
            http_client,
            "tools/call",
            {"name": tool, "arguments": {"chat_id": 999, "message_id": 1}},
        ).json()["result"]
        assert denied["isError"]
        assert "chat_not_allowed" in denied["content"][0]["text"]


def test_authenticated_http_unread_read_does_not_change_state(http_client):
    for _ in range(2):
        result = rpc(
            http_client,
            "tools/call",
            {"name": "get_unread_messages", "arguments": {"chat_id": DEMO_CHAT_ID}},
        ).json()["result"]
        assert not result.get("isError")
        page = result["structuredContent"]
        assert [message["message_id"] for message in page["messages"]] == [4, 3]
        assert page["read_inbox_max_id"] == 2
        assert page["unread_count"] == 2
        assert not page["unread_mark"]
    denied = rpc(
        http_client, "tools/call", {"name": "get_unread_messages", "arguments": {"chat_id": 999}}
    ).json()["result"]
    assert denied["isError"]
    assert "chat_not_allowed" in denied["content"][0]["text"]


def test_authenticated_http_media_search(http_client):
    tool = next(
        tool
        for tool in rpc(http_client, "tools/list").json()["result"]["tools"]
        if tool["name"] == "find_media"
    )
    assert tool["inputSchema"]["properties"]["media_type"]["enum"] == [
        "photo",
        "video",
        "voice",
        "audio",
    ]
    assert tool["inputSchema"]["required"] == ["media_type"]
    for arguments, error in (
        ({"media_type": "photo"}, None),
        ({"media_type": "photo", "chat_id": 999}, "chat_not_allowed"),
        ({"media_type": "document"}, "media_type"),
    ):
        result = rpc(
            http_client, "tools/call", {"name": "find_media", "arguments": arguments}
        ).json()["result"]
        if error:
            assert result["isError"]
            assert error in result["content"][0]["text"]
        else:
            assert not result.get("isError")
            assert result["structuredContent"]["messages"] == []


def test_authenticated_http_media_metadata(auth_setup):
    from mason.telegram.demo import DemoBackend
    from mason.telegram.service import TelegramService

    verifier, key, claims = auth_setup
    backend = DemoBackend()
    for message, kind in zip(backend.messages, ["photo", "video", "voice", "audio"], strict=True):
        message.media_type = kind
        message.media_duration = 12 if kind != "photo" else None
    service = TelegramService(backend, [DEMO_CHAT_ID], "UTC")
    app = create_app(verifier.settings, verifier=verifier, service=service)
    headers = {
        "Authorization": f"Bearer {jwt.encode(claims, key, algorithm='HS256')}",
        "Accept": "application/json, text/event-stream",
    }
    with TestClient(app, base_url="http://127.0.0.1:8000", headers=headers) as client:
        for kind in ("photo", "video", "voice", "audio"):
            result = rpc(
                client, "tools/call", {"name": "find_media", "arguments": {"media_type": kind}}
            ).json()["result"]
            assert not result.get("isError")
            messages = result["structuredContent"]["messages"]
            assert len(messages) == 1
            assert messages[0]["media_type"] == kind
            assert messages[0]["media_duration"] == (12 if kind != "photo" else None)


def test_authenticated_http_message_text_continuation(http_client):
    first = rpc(
        http_client,
        "tools/call",
        {
            "name": "get_message",
            "arguments": {"chat_id": DEMO_CHAT_ID, "message_id": 2, "text_limit": 5},
        },
    ).json()["result"]
    assert not first.get("isError")
    content = first["structuredContent"]
    assert content["message"]["text"] == "The h"
    assert content["next_text_offset"] == 5
    second = rpc(
        http_client,
        "tools/call",
        {
            "name": "get_message",
            "arguments": {"chat_id": DEMO_CHAT_ID, "message_id": 2, "text_offset": 5},
        },
    ).json()["result"]
    assert second["structuredContent"]["message"]["text"].startswith("omework PDF")
    assert second["structuredContent"]["next_text_offset"] is None
    forbidden = rpc(
        http_client,
        "tools/call",
        {
            "name": "get_message",
            "arguments": {"chat_id": 999, "message_id": 2},
        },
    ).json()["result"]
    assert forbidden["isError"]
    assert "chat_not_allowed" in forbidden["content"][0]["text"]


def test_authenticated_http_recent_messages_by_date(http_client):
    tools = rpc(http_client, "tools/list").json()["result"]["tools"]
    recent = next(tool for tool in tools if tool["name"] == "get_recent_messages")
    for field in ("date_from", "date_to"):
        assert field in recent["inputSchema"]["properties"]
        assert field not in recent["inputSchema"]["required"]
    result = rpc(
        http_client,
        "tools/call",
        {
            "name": "get_recent_messages",
            "arguments": {
                "chat_id": DEMO_CHAT_ID,
                "date_from": "2026-01-02T14:00:00+02:00",
                "date_to": "2026-01-04T14:00:00+02:00",
            },
        },
    ).json()["result"]
    assert not result.get("isError")
    assert [message["message_id"] for message in result["structuredContent"]["messages"]] == [3, 2]


def test_http_rejects_another_owner(http_client, auth_setup):
    verifier, key, claims = auth_setup
    verifier.provider._token_validator.verify_token.return_value.subject = "456"
    token = jwt.encode(claims, key, algorithm="HS256")
    response = http_client.post("/mcp", json={}, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_discovery_is_public_but_contains_no_telegram_data(http_client):
    response = http_client.get("/.well-known/oauth-protected-resource/mcp")
    assert response.status_code == 200
    assert response.json()["resource"] == "https://mason.example.com/mcp"
    assert response.json()["scopes_supported"] == ["read:user"]
    assert "owner" not in response.text


def test_http_bounds_request_size_and_rate(http_client):
    response = http_client.post("/mcp", content="x" * 17000)
    assert response.status_code == 413
    responses = [http_client.post("/mcp", json={}).status_code for _ in range(61)]
    assert responses[-1] == 429


def test_http_rejects_unexpected_host(http_client):
    response = http_client.post("/mcp", json={}, headers={"Host": "evil.example.com"})
    assert response.status_code == 400


async def test_mcp_errors_do_not_expose_backend_details(auth_setup, caplog):
    verifier, _, _ = auth_setup
    server = create_server(verifier.settings, verifier=verifier)
    async with Client(server) as client:
        forbidden = await client.call_tool("get_recent_messages", {"chat_id": 999, "limit": 1})
        assert forbidden.is_error
        assert "chat_not_allowed" in forbidden.content[0].text
        result = await client.call_tool("get_recent_messages", {"chat_id": DEMO_CHAT_ID})
        assert not result.is_error
    assert "fictional" not in caplog.text


async def test_unexpected_backend_errors_are_sanitized(auth_setup, caplog):
    from unittest.mock import AsyncMock

    from mason.telegram.demo import DemoBackend
    from mason.telegram.service import TelegramService

    verifier, _, _ = auth_setup
    backend = DemoBackend()
    backend.read_messages = AsyncMock(side_effect=RuntimeError("private message and token"))
    service = TelegramService(backend, [DEMO_CHAT_ID], "UTC")
    server = create_server(verifier.settings, service=service, verifier=verifier)
    async with Client(server) as client:
        result = await client.call_tool("search_messages", {"query": "maths"})
        assert result.is_error
        assert "internal_error" in result.content[0].text
        assert "private message and token" not in str(result)
    assert "private message and token" not in caplog.text
