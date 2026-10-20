import json
import sys

import jwt
import pytest
from mcp import types
from starlette.testclient import TestClient

from mason.gateway import Gateway
from mason.server import create_app

FAKE_SERVER = """
from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from pydantic import BaseModel
server = MCPServer('fake', log_level='CRITICAL')
counter = 0
class Result(BaseModel):
    value: int
    calls: int
@server.tool(annotations=ToolAnnotations(read_only_hint=True, destructive_hint=False))
async def read(value: int = 0) -> Result:
    global counter
    counter += 1
    return Result(value=value, calls=counter)
@server.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=True))
async def write() -> dict:
    return {'unexpected': True}
server.run(transport='stdio')
"""


def write_config(tmp_path, names=("telegram",)):
    path = tmp_path / "upstreams.json"
    config = {
        "mcpServers": {
            name: {"command": sys.executable, "args": ["-c", FAKE_SERVER], "read_only": True}
            for name in names
        }
    }
    path.write_text(json.dumps(config))
    path.chmod(0o600)
    return path


async def test_namespaces_and_write_denial_over_real_stdio(tmp_path):
    gateway = Gateway.from_file(write_config(tmp_path, ("telegram", "another")))
    async with gateway.connect():
        tools = (await gateway.list_tools(None, None)).tools
        assert {tool.name for tool in tools} == {"telegram_read", "another_read"}
        assert tools[0].input_schema["properties"]["value"]["type"] == "integer"
        result = await gateway.call_tool(
            None, types.CallToolRequestParams(name="telegram_read", arguments={"value": 42})
        )
        assert result.structured_content == {"value": 42, "calls": 1}
        other = await gateway.call_tool(
            None, types.CallToolRequestParams(name="another_read", arguments={})
        )
        assert other.structured_content["calls"] == 1
        for name in ("telegram_write", "write", "missing_read"):
            refused = await gateway.call_tool(
                None, types.CallToolRequestParams(name=name, arguments={})
            )
            assert refused.is_error
            assert "tool_not_allowed" in refused.content[0].text
    assert not gateway.clients


def test_gateway_reuses_upstream_and_preserves_http_auth(tmp_path, auth_setup):
    verifier, key, claims = auth_setup
    settings = verifier.settings.model_copy(
        update={"mode": "gateway", "upstreams_file": write_config(tmp_path)}
    )
    app = create_app(settings, verifier=verifier)
    token = jwt.encode(claims, key, algorithm="HS256")
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json, text/event-stream"}
    with TestClient(app, base_url="http://127.0.0.1:8000", headers=headers) as client:
        for authorization in ("", "Bearer invalid"):
            refused = client.post("/mcp", json={}, headers={"Authorization": authorization})
            assert refused.status_code == 401
        for index in (1, 2):
            result = client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": index,
                    "method": "tools/call",
                    "params": {
                        "name": "telegram_read",
                        "arguments": {"value": index},
                    },
                },
            )
            assert result.status_code == 200
            assert result.json()["result"]["structuredContent"] == {"value": index, "calls": index}
        listed = client.post(
            "/mcp", json={"jsonrpc": "2.0", "id": 3, "method": "tools/list"}
        ).json()["result"]["tools"]
        assert [tool["name"] for tool in listed] == ["telegram_read"]
        assert client.get("/health").json() == {"status": "ok"}
        assert client.get("/.well-known/oauth-protected-resource/mcp").status_code == 200


def test_configuration_is_private_and_validated(tmp_path):
    path = write_config(tmp_path)
    path.chmod(0o644)
    with pytest.raises(ValueError, match="permissions 600"):
        Gateway.from_file(path)
    path.chmod(0o600)
    link = tmp_path / "linked.json"
    link.symlink_to(path)
    with pytest.raises(ValueError):
        Gateway.from_file(link)
    for config in ({}, {"mcpServers": {}}, {"mcpServers": {"bad/name": {"command": "x"}}}):
        path.write_text(json.dumps(config))
        with pytest.raises(ValueError):
            Gateway.from_file(path)


async def test_transport_errors_do_not_expose_arguments(tmp_path, caplog):
    gateway = Gateway.from_file(write_config(tmp_path))

    class Broken:
        async def call_tool(self, name, arguments):
            raise ValueError("private-token-do-not-echo")

    import asyncio

    gateway.clients["telegram"] = Broken()
    gateway.locks["telegram"] = asyncio.Lock()
    gateway.routes["telegram_read"] = ("telegram", "read")
    result = await gateway.call_tool(
        None, types.CallToolRequestParams(name="telegram_read", arguments={})
    )
    assert result.is_error
    assert "private-token" not in result.model_dump_json()
    assert "private-token" not in caplog.text


async def test_only_explicit_write_exceptions_are_exposed(tmp_path):
    path = write_config(tmp_path)
    config = json.loads(path.read_text())
    config["mcpServers"]["telegram"]["allow_writes"] = ["write"]
    path.write_text(json.dumps(config))
    gateway = Gateway.from_file(path)
    async with gateway.connect():
        assert set(gateway.tools) == {"telegram_read", "telegram_write"}
        assert gateway.tools["telegram_write"].annotations.read_only_hint is False
