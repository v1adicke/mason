import asyncio
import os
import socket
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from dotenv import dotenv_values

from mason.config import NgrokSettings, Settings
from mason.doctor import fetch_json
from mason.launch import check_port, read_tunnel, save_url, start, stop_process


class Process:
    def __init__(self, output=b""):
        self.returncode = None
        self.stdout = asyncio.StreamReader()
        self.stdout.feed_data(output)
        self.exited = asyncio.Event()
        self.terminated = False
        self.killed = False

    async def wait(self):
        await self.exited.wait()
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.finish(0)

    def kill(self):
        self.killed = True
        self.finish(-9)

    def finish(self, code):
        self.returncode = code
        self.exited.set()
        self.stdout.feed_eof()


@pytest.fixture
def launch_setup(tmp_path, monkeypatch, auth_setup):
    monkeypatch.chdir(tmp_path)
    path = Path(".env")
    path.write_text("MASON_PUBLIC_URL=https://old.test/mcp\nKEEP=fictional-private-value\n")
    path.chmod(0o600)
    settings = auth_setup[0].settings.model_copy(update={"public_url": "https://old.test/mcp"})
    monkeypatch.setattr("mason.launch.Settings", lambda: settings)
    monkeypatch.setattr("mason.launch.doctor", lambda: True)
    monkeypatch.setattr("mason.launch.check_port", lambda port: None)
    monkeypatch.setattr("mason.launch.find_executable", lambda name: "/fictional/" + name)
    return path, settings


def test_busy_port_is_refused():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        with pytest.raises(ValueError, match="busy"):
            check_port(listener.getsockname()[1])


def test_running_server_with_address_reuse_is_still_refused():
    with socket.socket() as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        with pytest.raises(ValueError, match="busy"):
            check_port(listener.getsockname()[1])


def test_closed_connections_do_not_block_a_restart():
    with socket.socket() as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        with socket.create_connection(("127.0.0.1", port), timeout=1) as client:
            connection, _ = listener.accept()
            connection.close()
            assert client.recv(1) == b""
    check_port(port)


async def test_tunnel_logs_are_not_echoed(capsys):
    process = Process(b"private log details\n| https://fictional-new.trycloudflare.com |\n")
    process.finish(0)
    address = asyncio.get_running_loop().create_future()
    await read_tunnel(process, address)
    assert await address == "https://fictional-new.trycloudflare.com"
    assert capsys.readouterr().out == ""


async def test_tunnel_exit_before_an_address_has_a_safe_error():
    process = Process(b"fictional-private-error\n")
    process.finish(1)
    address = asyncio.get_running_loop().create_future()
    await read_tunnel(process, address)
    with pytest.raises(ValueError, match="before publishing"):
        await address


async def test_startup_failure_stops_children_and_keeps_the_old_url(
    launch_setup, monkeypatch, capsys
):
    path, _ = launch_setup
    original = path.read_text()
    tunnel = Process(b"https://fictional-new.trycloudflare.com\n")
    server = Process()
    spawn = AsyncMock(side_effect=[tunnel, server])
    monkeypatch.setattr("mason.launch.asyncio.create_subprocess_exec", spawn)
    monkeypatch.setattr(
        "mason.launch.wait_ready", AsyncMock(side_effect=TimeoutError("private error"))
    )
    with pytest.raises(ValueError, match="timed out"):
        await start()
    assert tunnel.terminated and server.terminated
    assert path.read_text() == original
    assert "private error" not in capsys.readouterr().out
    assert spawn.call_args_list[1].kwargs["env"]["MASON_PUBLIC_URL"] == (
        "https://fictional-new.trycloudflare.com/mcp"
    )


async def test_cancellation_stops_both_children_and_preserves_private_settings(
    launch_setup, monkeypatch, capsys
):
    path, _ = launch_setup
    tunnel = Process(b"https://fictional-new.trycloudflare.com\n")
    server = Process()
    monkeypatch.setattr(
        "mason.launch.asyncio.create_subprocess_exec", AsyncMock(side_effect=[tunnel, server])
    )
    monkeypatch.setattr("mason.launch.wait_ready", AsyncMock())
    ready = asyncio.Event()
    output_print = print

    def print_and_signal(*args, **kwargs):
        output_print(*args, **kwargs)
        if args[0].startswith("server ready"):
            ready.set()

    monkeypatch.setattr("mason.launch.print", print_and_signal, raising=False)
    task = asyncio.create_task(start())
    try:
        async with asyncio.timeout(2):
            await ready.wait()
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert tunnel.terminated and server.terminated
    config = dotenv_values(path)
    assert config["MASON_PUBLIC_URL"] == "https://fictional-new.trycloudflare.com/mcp"
    assert config["KEEP"] == "fictional-private-value"
    assert path.stat().st_mode & 0o077 == 0
    output = capsys.readouterr().out
    assert "fictional-private-value" not in output
    assert "GitHub callback: https://fictional-new.trycloudflare.com/auth/callback" in output


async def test_failed_local_setup_does_not_spawn_any_process(launch_setup, monkeypatch):
    monkeypatch.setattr("mason.launch.doctor", lambda: False)
    spawn = AsyncMock()
    monkeypatch.setattr("mason.launch.asyncio.create_subprocess_exec", spawn)
    with pytest.raises(ValueError, match="finish local setup"):
        await start()
    spawn.assert_not_called()


async def test_a_stubborn_child_is_killed(monkeypatch):
    process = Process()
    process.terminate = lambda: None
    original_wait_for = asyncio.wait_for

    async def quick_wait(awaitable, **kwargs):
        return await original_wait_for(awaitable, timeout=0.01)

    monkeypatch.setattr("mason.launch.asyncio.wait_for", quick_wait)
    await stop_process(process)
    assert process.killed


def test_public_url_update_refuses_an_insecure_file(launch_setup):
    path, _ = launch_setup
    original = path.read_text()
    path.chmod(0o644)
    with pytest.raises(ValueError, match="600"):
        save_url("https://fictional-new.trycloudflare.com/mcp")
    assert path.read_text() == original


async def test_child_exit_stops_the_other_process(launch_setup, monkeypatch):
    tunnel = Process(b"https://fictional-new.trycloudflare.com\n")
    server = Process()
    monkeypatch.setattr(
        "mason.launch.asyncio.create_subprocess_exec", AsyncMock(side_effect=[tunnel, server])
    )

    async def ready(*args):
        server.finish(1)

    monkeypatch.setattr("mason.launch.wait_ready", ready)
    with pytest.raises(ValueError, match="both processes"):
        await start()
    assert tunnel.terminated


async def test_real_demo_server_starts_and_stops_with_the_launcher(
    launch_setup, tmp_path, monkeypatch
):
    path, _ = launch_setup
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    path.write_text(
        "MASON_MODE=demo\n"
        "MASON_PUBLIC_URL=https://old.test/mcp\n"
        "MASON_GITHUB_CLIENT_ID=fictional-client\n"
        "MASON_GITHUB_CLIENT_SECRET=fictional-secret-for-smoke-test\n"
        "MASON_GITHUB_OWNER_ID=123\n"
        f"MASON_PORT={port}\n"
    )
    for name in tuple(os.environ):
        if name.startswith("MASON_"):
            monkeypatch.delenv(name)
    settings = Settings()
    monkeypatch.setattr("mason.launch.Settings", lambda: settings)
    spawn = asyncio.create_subprocess_exec
    processes = []

    async def spawn_local(*args, **kwargs):
        if args[0] == "/fictional/cloudflared":
            args = (
                sys.executable,
                "-u",
                "-c",
                "import time; print('https://fictional-new.trycloudflare.com'); time.sleep(60)",
            )
        else:
            kwargs["env"]["HOME"] = str(tmp_path)
        process = await spawn(*args, **kwargs)
        processes.append(process)
        return process

    async def local_ready(settings, processes):
        async with asyncio.timeout(10):
            while True:
                try:
                    status, body, _ = await asyncio.to_thread(
                        fetch_json, f"http://127.0.0.1:{port}/health"
                    )
                    assert status == 200 and body == {"status": "ok"}
                    status, _, _ = await asyncio.to_thread(
                        fetch_json, f"http://127.0.0.1:{port}/mcp", method="POST"
                    )
                    assert status == 401
                    return
                except OSError:
                    await asyncio.sleep(0.05)

    monkeypatch.setattr("mason.launch.asyncio.create_subprocess_exec", spawn_local)
    monkeypatch.setattr("mason.launch.wait_ready", local_ready)
    task = asyncio.create_task(start())
    try:
        async with asyncio.timeout(15):
            while dotenv_values(path)["MASON_PUBLIC_URL"] == "https://old.test/mcp":
                if task.done():
                    await task
                await asyncio.sleep(0.05)
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert len(processes) == 2
    assert all(process.returncode is not None for process in processes)


async def test_ngrok_uses_the_configured_address_without_logging_tokens(
    launch_setup, monkeypatch, capsys
):
    path, _ = launch_setup
    tunnel = Process(b"fictional-private-token in discarded agent logs\n")
    server = Process()
    spawn = AsyncMock(side_effect=[tunnel, server])
    monkeypatch.setattr("mason.launch.asyncio.create_subprocess_exec", spawn)
    monkeypatch.setattr(
        "mason.launch.NgrokSettings",
        lambda: NgrokSettings(_env_file=None, ngrok_authtoken="fictional-private-token"),
    )
    ready = AsyncMock()
    monkeypatch.setattr("mason.launch.wait_ready", ready)
    started = asyncio.Event()
    output_print = print

    def print_and_signal(*args, **kwargs):
        output_print(*args, **kwargs)
        if args[0].startswith("server ready"):
            started.set()

    monkeypatch.setattr("mason.launch.print", print_and_signal, raising=False)
    task = asyncio.create_task(start("ngrok"))
    try:
        async with asyncio.timeout(2):
            await started.wait()
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    tunnel_call = spawn.call_args_list[0]
    assert "fictional-private-token" not in str(tunnel_call.args)
    assert tunnel_call.kwargs["env"]["NGROK_AUTHTOKEN"] == "fictional-private-token"
    assert "--inspect=false" in tunnel_call.args
    assert tunnel_call.args[tunnel_call.args.index("--url") + 1] == "https://old.test"
    assert ready.call_args.args[0].public_url == "https://old.test/mcp"
    assert dotenv_values(path)["MASON_PUBLIC_URL"] == "https://old.test/mcp"
    assert tunnel.terminated and server.terminated
    output = capsys.readouterr().out
    assert "fictional-private-token" not in output
    assert "update the GitHub callback" not in output


async def test_missing_ngrok_token_does_not_spawn_a_tunnel(launch_setup, monkeypatch):
    from pydantic import ValidationError

    monkeypatch.delenv("MASON_NGROK_AUTHTOKEN", raising=False)
    spawn = AsyncMock()
    monkeypatch.setattr("mason.launch.asyncio.create_subprocess_exec", spawn)
    with pytest.raises(ValidationError):
        await start("ngrok")
    spawn.assert_not_called()
