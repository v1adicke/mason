import os
from getpass import getpass
from pathlib import Path

from dotenv import dotenv_values, set_key

from mason.config import Settings


def configure(target: str) -> None:
    """save credentials from hidden prompts in the local environment file"""
    path = Path(".env")
    if not path.exists():
        template = Path(".env.example").read_text()
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as file:
            file.write(template)
    if path.is_symlink() or path.stat().st_uid != os.getuid() or path.stat().st_mode & 0o077:
        raise ValueError(".env must be owned by you and have permissions 600")
    current = dotenv_values(path)
    if target == "github":
        client_id = getpass("GitHub OAuth client ID: ").strip()
        secret = getpass("GitHub OAuth client secret: ").strip()
        owner = getpass("GitHub numeric owner ID (empty to keep the current value): ").strip()
        owner = owner or current.get("MASON_GITHUB_OWNER_ID", "")
        if not client_id or len(secret) < 12 or not owner.isdecimal() or int(owner) <= 0:
            raise ValueError("check the GitHub client credentials and numeric owner ID")
        values = {
            "MASON_GITHUB_CLIENT_ID": client_id,
            "MASON_GITHUB_CLIENT_SECRET": secret,
            "MASON_GITHUB_OWNER_ID": owner,
        }
    elif target == "ngrok":
        origin = getpass("ngrok HTTPS domain from your dashboard: ").strip().rstrip("/")
        if not origin.startswith("https://"):
            origin = "https://" + origin
        url = origin if origin.endswith("/mcp") else origin + "/mcp"
        url = Settings.validate_endpoint(Settings.validate_url(url))
        token = getpass("ngrok authtoken: ").strip()
        if not token or token == "replace-locally":
            raise ValueError("enter the ngrok authtoken locally")
        values = {"MASON_PUBLIC_URL": url, "MASON_NGROK_AUTHTOKEN": token}
    elif target == "telegram":
        api_id = getpass("Telegram API ID: ").strip()
        api_hash = getpass("Telegram API hash: ").strip()
        if not api_id.isdecimal() or int(api_id) <= 0 or not api_hash:
            raise ValueError("check the Telegram API credentials")
        values = {"MASON_TELEGRAM_API_ID": api_id, "MASON_TELEGRAM_API_HASH": api_hash}
    else:
        raise ValueError("choose github, telegram, or ngrok")
    for key, value in values.items():
        set_key(path, key, value)
    path.chmod(0o600)
    print(f"{target} credentials saved locally")
