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
    token = jwt.encode(claims, key, algorithm="RS256", headers={"kid": "test"})
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


def test_http_rejects_another_owner(http_client, auth_setup):
    _, key, claims = auth_setup
    claims["sub"] = "someone-else"
    token = jwt.encode(claims, key, algorithm="RS256", headers={"kid": "test"})
    response = http_client.post("/mcp", json={}, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_discovery_is_public_but_contains_no_telegram_data(http_client):
    response = http_client.get("/.well-known/oauth-protected-resource/mcp")
    assert response.status_code == 200
    assert response.json()["resource"] == "https://mason.example.com/mcp"
    assert response.json()["scopes_supported"] == ["telegram:read"]
    assert "owner" not in response.text


def test_http_bounds_request_size_and_rate(http_client):
    response = http_client.post("/mcp", content="x" * 17000)
    assert response.status_code == 413
    responses = [http_client.post("/mcp", json={}).status_code for _ in range(61)]
    assert responses[-1] == 429


def test_http_rejects_unexpected_host(http_client):
    response = http_client.post("/mcp", json={}, headers={"Host": "evil.example.com"})
    assert response.status_code == 421


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
