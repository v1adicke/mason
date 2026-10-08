import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from pydantic import ValidationError

from mason.config import Settings, TelegramSettings
from mason.telegram.client import prepare_session


class NoRedirects(HTTPRedirectHandler):
    """keep diagnostic requests on the configured endpoint"""

    def redirect_request(self, request, file, code, message, headers, url):
        return None


def fetch_json(url: str, *, method: str = "GET") -> tuple[int, dict, dict]:
    """read a bounded public response without credentials"""
    request = Request(
        url,
        data=b"{}" if method == "POST" else None,
        method=method,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
    )
    try:
        response = build_opener(NoRedirects()).open(request, timeout=10)
    except HTTPError as error:
        response = error
    with response:
        body = response.read(65537)
        if len(body) > 65536:
            raise ValueError("response is too large")
        data = json.loads(body)
        if not isinstance(data, dict):
            raise ValueError("expected a JSON object")
        return response.status, data, dict(response.headers)


def check_endpoint(settings: Settings) -> None:
    """check discovery and anonymous refusal without running Telegram tools"""
    status, health, _ = fetch_json(settings.origin + "/health")
    if status != 200 or health.get("status") != "ok":
        raise ValueError("health check failed")
    status, _, headers = fetch_json(settings.public_url, method="POST")
    expected = settings.origin + "/.well-known/oauth-protected-resource/mcp"
    challenge = next(
        (value for name, value in headers.items() if name.lower() == "www-authenticate"), ""
    )
    if status != 401 or f'resource_metadata="{expected}"' not in challenge:
        raise ValueError("the MCP endpoint must refuse anonymous access and advertise discovery")
    status, resource, _ = fetch_json(expected)
    if status != 200 or resource.get("resource") != settings.public_url:
        raise ValueError("protected resource metadata does not match the public URL")
    status, oauth, _ = fetch_json(settings.origin + "/.well-known/oauth-authorization-server")
    if status != 200 or resource.get("authorization_servers") != [oauth.get("issuer")]:
        raise ValueError("OAuth issuer metadata does not match the resource metadata")
    if "S256" not in oauth.get("code_challenge_methods_supported", []):
        raise ValueError("OAuth must support PKCE S256")
    for name, suffix in (
        ("authorization_endpoint", "/authorize"),
        ("token_endpoint", "/token"),
        ("registration_endpoint", "/register"),
    ):
        if oauth.get(name) != settings.origin + suffix:
            raise ValueError("OAuth endpoints do not match the configured origin")


def doctor(*, network: bool = False) -> bool:
    """report setup readiness without printing credentials or conversations"""
    path = Path(".env")
    if path.exists() and (
        path.is_symlink() or path.stat().st_uid != os.getuid() or path.stat().st_mode & 0o077
    ):
        print("not ready: .env must be owned by you and have permissions 600")
        return False
    try:
        settings = Settings()
    except ValidationError as error:
        fields = sorted({str(item["loc"][0]) for item in error.errors()})
        print(f"not ready: check local settings for {', '.join(fields)}")
        return False
    if "example.com" in settings.public_url or settings.github_client_id == "replace-locally":
        print("not ready: replace the example URL and GitHub client credentials")
        return False
    if settings.github_client_secret.get_secret_value() == "replace-locally":
        print("not ready: run mason configure github locally")
        return False
    print("server settings: ready")
    if settings.mode == "telegram":
        try:
            telegram = TelegramSettings()
            if not telegram.allowed_chats:
                raise ValueError("choose allowed chats before using Telegram mode")
            prepare_session(telegram.session_path)
        except ValidationError:
            print("not ready: run mason configure telegram locally")
            return False
        except (ValueError, OSError):
            print("not ready: check the local session permissions and allowed chats")
            return False
        print("Telegram session file and allowlist: ready")
    else:
        print("data source: fictional demo messages")
    if network:
        try:
            check_endpoint(settings)
        except Exception:
            print("not ready: the public endpoint or OAuth discovery check failed")
            return False
        print("public HTTPS, OAuth discovery, and anonymous refusal: ready")
        print("a real sign-in and ChatGPT tool call still need to be tested")
    return True
