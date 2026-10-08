from pathlib import Path

import pytest
from dotenv import dotenv_values

from mason.setup import configure


def test_hidden_credentials_are_saved_without_echoing_them(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    Path(".env.example").write_text("MASON_GITHUB_OWNER_ID=123\nMASON_MODE=demo\n")
    values = iter(["fictional-client-id", "fictional-secret-for-test", ""])
    monkeypatch.setattr("mason.setup.getpass", lambda prompt: next(values))
    configure("github")
    config = dotenv_values(".env")
    assert config["MASON_GITHUB_CLIENT_SECRET"] == "fictional-secret-for-test"
    assert config["MASON_GITHUB_OWNER_ID"] == "123"
    assert config["MASON_MODE"] == "demo"
    assert Path(".env").stat().st_mode & 0o077 == 0
    output = capsys.readouterr().out
    assert "fictional-secret-for-test" not in output
    assert "fictional-client-id" not in output


def test_insecure_environment_file_is_not_overwritten(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = Path(".env")
    path.write_text("keep=this\n")
    path.chmod(0o644)
    with pytest.raises(ValueError, match="600"):
        configure("github")
    assert path.read_text() == "keep=this\n"


def test_invalid_credentials_do_not_change_existing_values(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = Path(".env")
    path.write_text("MASON_GITHUB_OWNER_ID=123\n")
    path.chmod(0o600)
    monkeypatch.setattr("mason.setup.getpass", lambda prompt: "")
    with pytest.raises(ValueError):
        configure("github")
    assert path.read_text() == "MASON_GITHUB_OWNER_ID=123\n"
