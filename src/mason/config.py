from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """read server settings from the local environment"""

    model_config = SettingsConfigDict(env_prefix="MASON_", env_file=".env", extra="ignore")

    mode: Literal["demo", "telegram"] = "demo"
    public_url: str
    oauth_issuer: str
    oauth_jwks_url: str
    oauth_owner: str = Field(min_length=1, max_length=512)
    port: int = Field(default=8000, ge=1024, le=65535)
    timezone: str = "Asia/Nicosia"

    @field_validator("public_url", "oauth_issuer", "oauth_jwks_url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        """accept explicit HTTPS URLs without credentials"""
        url = urlsplit(value)
        if url.scheme != "https" or not url.hostname or url.username or url.password:
            raise ValueError("an HTTPS URL without credentials is required")
        if url.query or url.fragment:
            raise ValueError("URL parameters are not supported")
        return value

    @field_validator("public_url")
    @classmethod
    def validate_endpoint(cls, value: str) -> str:
        """keep the public resource and MCP endpoint identical"""
        if urlsplit(value).path != "/mcp":
            raise ValueError("the public URL must end with /mcp")
        return value

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        ZoneInfo(value)
        return value


class TelegramSettings(BaseSettings):
    """keep Telegram credentials separate from server settings"""

    model_config = SettingsConfigDict(env_prefix="MASON_", env_file=".env", extra="ignore")

    telegram_api_id: int = Field(gt=0)
    telegram_api_hash: SecretStr = Field(min_length=1)
    allowed_chats: list[int] = Field(default_factory=list, max_length=20)
    session_path: Path = Field(
        default_factory=lambda: Path.home() / ".local/share/mason/telegram.session"
    )

    @field_validator("session_path")
    @classmethod
    def validate_session_path(cls, value: Path) -> Path:
        """keep the session outside the checkout"""
        path = value.expanduser().resolve()
        root = Path(__file__).resolve().parents[2]
        if path.is_relative_to(root) or path.is_relative_to(Path.cwd().resolve()):
            raise ValueError("the session must live outside the project directory")
        if path.suffix != ".session":
            raise ValueError("use a .session file")
        return path
