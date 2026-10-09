import asyncio
import contextlib
import os
import re
import shutil
import signal
import socket
import sys
from pathlib import Path

from dotenv import set_key

from mason.config import NgrokSettings, Settings
from mason.doctor import check_endpoint, doctor


def find_executable(name: str) -> str:
    """find the tunnel binary without downloading anything"""
    executable = shutil.which(name)
    if not executable:
        local = Path.home() / ".local/bin" / name
        if local.is_file() and os.access(local, os.X_OK):
            executable = str(local)
    if not executable:
        raise ValueError(f"install {name} before running mason start")
    return executable


def check_port(port: int) -> None:
    """refuse to replace a running server"""
    with socket.socket() as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            listener.bind(("127.0.0.1", port))
        except OSError:
            raise ValueError(f"port {port} is busy; stop the existing server first") from None


async def read_tunnel(process, address: asyncio.Future) -> None:
    """extract the public address and discard raw tunnel logs"""
    while line := await process.stdout.readline():
        match = re.search(rb"https://[a-z0-9]+(?:-[a-z0-9]+)*\.trycloudflare\.com\b", line)
        if match and not address.done():
            address.set_result(match.group().decode("ascii"))
    if not address.done():
        address.set_exception(ValueError("the tunnel stopped before publishing an address"))


async def wait_ready(settings: Settings, processes: list) -> None:
    """wait for public discovery and anonymous refusal"""
    async with asyncio.timeout(60):
        while True:
            if any(process.returncode is not None for process in processes):
                raise ValueError("a startup process stopped; check the local configuration")
            try:
                await asyncio.to_thread(check_endpoint, settings)
                return
            except Exception:
                await asyncio.sleep(1)


async def stop_process(process) -> None:
    """give a child time to exit before killing it"""
    if process.returncode is None:
        with contextlib.suppress(ProcessLookupError):
            process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=5)
        except TimeoutError:
            with contextlib.suppress(ProcessLookupError):
                process.kill()
            await process.wait()


def load_settings() -> Settings:
    """check local setup before creating any child processes"""
    if not doctor():
        raise ValueError("finish local setup before running mason start")
    if not Path(".env").is_file():
        raise ValueError("create a private .env file before running mason start")
    settings = Settings()
    check_port(settings.port)
    return settings


def save_url(public_url: str) -> None:
    """save only the verified public address in the private environment file"""
    path = Path(".env")
    if path.is_symlink() or path.stat().st_uid != os.getuid() or path.stat().st_mode & 0o077:
        raise ValueError(".env must be owned by you and have permissions 600")
    set_key(path, "MASON_PUBLIC_URL", public_url)
    path.chmod(0o600)


async def start(tunnel_kind: str = "cloudflare") -> None:
    """run a selected tunnel and server until interrupted"""
    settings = await asyncio.to_thread(load_settings)
    if tunnel_kind == "ngrok":
        token = NgrokSettings().ngrok_authtoken.get_secret_value()
        if token == "replace-locally":
            raise ValueError("run mason configure ngrok locally")
        command = [
            find_executable("ngrok"),
            "http",
            f"http://127.0.0.1:{settings.port}",
            "--url",
            settings.origin,
            "--inspect=false",
            "--log=stdout",
            "--log-format=json",
        ]
        tunnel_environment = dict(os.environ, NGROK_AUTHTOKEN=token)
    elif tunnel_kind == "cloudflare":
        command = [
            find_executable("cloudflared"),
            "tunnel",
            "--url",
            f"http://127.0.0.1:{settings.port}",
            "--protocol",
            "http2",
            "--no-autoupdate",
        ]
        tunnel_environment = None
    else:
        raise ValueError("choose cloudflare or ngrok")
    processes = []
    tasks = []
    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGTERM, asyncio.current_task().cancel)
    try:
        print(f"starting the {tunnel_kind} HTTPS tunnel", flush=True)
        tunnel = await asyncio.create_subprocess_exec(
            *command,
            env=tunnel_environment,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            start_new_session=True,
        )
        processes.append(tunnel)
        address = asyncio.get_running_loop().create_future()
        if tunnel_kind == "ngrok":
            address.set_result(settings.origin)
        reader = asyncio.create_task(read_tunnel(tunnel, address))
        tasks.append(reader)
        origin = await asyncio.wait_for(address, timeout=45)
        public_url = origin + "/mcp"
        environment = dict(os.environ, MASON_PUBLIC_URL=public_url)
        server = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "mason.cli",
            "serve",
            env=environment,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            start_new_session=True,
        )
        processes.append(server)
        print("checking HTTPS and OAuth discovery", flush=True)
        await wait_ready(settings.model_copy(update={"public_url": public_url}), processes)
        await asyncio.to_thread(save_url, public_url)
        print(f"MCP URL: {public_url}", flush=True)
        print(f"GitHub callback: {origin}/auth/callback", flush=True)
        if public_url != settings.public_url:
            print("update the GitHub callback and ChatGPT connection for this address", flush=True)
        print("server ready; press Ctrl+C to stop both processes", flush=True)
        tasks.extend(asyncio.create_task(process.wait()) for process in processes)
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
        raise ValueError("the server or tunnel stopped; both processes have been shut down")
    except TimeoutError:
        raise ValueError("startup timed out; check the network and local configuration") from None
    finally:
        for process in reversed(processes):
            await stop_process(process)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        loop.remove_signal_handler(signal.SIGTERM)
