import pytest
from pydantic import ValidationError

from mason.config import Settings, TelegramSettings
from mason.telegram.client import prepare_session


@pytest.mark.parametrize(
    "url",
    [
        "http://mason.example.com/mcp",
        "https://user:password@mason.example.com/mcp",
        "https://mason.example.com/mcp?token=secret",
        "https://mason.example.com/",
    ],
)
def test_server_rejects_insecure_or_ambiguous_urls(auth_setup, url):
    verifier, _, _ = auth_setup
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **(verifier.settings.model_dump() | {"public_url": url}))


def test_telegram_session_cannot_live_in_the_checkout():
    with pytest.raises(ValidationError):
        TelegramSettings(
            _env_file=None,
            telegram_api_id=12345,
            telegram_api_hash="test-placeholder",
            session_path="telegram.session",
        )


def test_session_permissions_are_checked(tmp_path):
    directory = tmp_path / "session"
    directory.mkdir(mode=0o700)
    session = directory / "telegram.session"
    session.touch(mode=0o600)
    prepare_session(session)
    session.chmod(0o644)
    with pytest.raises(ValueError, match="600"):
        prepare_session(session)
    session.chmod(0o600)
    directory.chmod(0o755)
    with pytest.raises(ValueError, match="700"):
        prepare_session(session)
