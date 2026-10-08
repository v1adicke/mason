import argparse
import asyncio
import json
import logging
import os
from getpass import getpass

import uvicorn
from pydantic import ValidationError
from telethon.errors import SessionPasswordNeededError

from mason.config import Settings, TelegramSettings
from mason.doctor import doctor
from mason.server import create_app
from mason.setup import configure
from mason.telegram.client import create_client, prepare_session


async def login() -> None:
    """authorize Telegram through local terminal prompts"""
    settings = TelegramSettings()
    prepare_session(settings.session_path, create=True)
    client = create_client(settings)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            phone = getpass("Telegram phone number: ")
            sent = await client.send_code_request(phone)
            try:
                await client.sign_in(
                    phone=phone,
                    code=getpass("Telegram login code: "),
                    phone_code_hash=sent.phone_code_hash,
                )
            except SessionPasswordNeededError:
                await client.sign_in(password=getpass("Telegram 2FA password: "))
        print("Telegram session is ready")
    finally:
        await client.disconnect()
    prepare_session(settings.session_path)


async def list_local_chats() -> None:
    """list account dialogs locally to help choose the allowlist"""
    settings = TelegramSettings()
    prepare_session(settings.session_path)
    client = create_client(settings)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            raise ValueError("run mason login first")
        async for dialog in client.iter_dialogs():
            print(json.dumps({"id": dialog.id, "title": dialog.name}, ensure_ascii=False))
    finally:
        await client.disconnect()


def main() -> None:
    """run the server or a local Telegram setup command"""
    os.umask(0o077)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("mcp").setLevel(logging.CRITICAL)
    logging.getLogger("fastmcp").setLevel(logging.CRITICAL)
    logging.getLogger("telethon").setLevel(logging.CRITICAL)
    parser = argparse.ArgumentParser(prog="mason")
    parser.add_argument("command", choices=["serve", "login", "chats", "configure", "doctor"])
    parser.add_argument("target", nargs="?", choices=["github", "telegram"])
    parser.add_argument("--network", action="store_true")
    args = parser.parse_args()
    if args.target and args.command != "configure":
        parser.error("a target is only used with configure")
    if args.network and args.command != "doctor":
        parser.error("--network is only used with doctor")
    try:
        if args.command == "serve":
            settings = Settings()
            uvicorn.run(
                create_app(settings),
                host="127.0.0.1",
                port=settings.port,
                access_log=False,
                log_level="warning",
            )
        elif args.command == "login":
            asyncio.run(login())
        elif args.command == "configure":
            configure(args.target or "github")
        elif args.command == "doctor":
            if not doctor(network=args.network):
                parser.exit(1)
        else:
            asyncio.run(list_local_chats())
    except ValidationError as error:
        fields = sorted({str(item["loc"][0]) for item in error.errors()})
        parser.exit(1, f"check local configuration: {', '.join(fields)}\n")
    except (ValueError, OSError) as error:
        parser.exit(1, f"setup error: {error}\n")
    except Exception as error:
        parser.exit(1, f"operation failed ({type(error).__name__}); check local setup\n")


if __name__ == "__main__":
    main()
