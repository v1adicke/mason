import pytest
from mcp.shared.auth import OAuthClientInformationFull

from mason.auth import create_auth, create_storage


async def test_registered_client_survives_a_new_provider(auth_setup, tmp_path):
    settings = auth_setup[0].settings
    directory = tmp_path / "oauth"
    client = OAuthClientInformationFull(
        client_id="fictional-client",
        redirect_uris=["https://chatgpt.com/connector_platform_oauth_redirect"],
        scope="read:user",
    )
    first_store = create_storage(settings, directory)
    first = create_auth(settings, storage=first_store)
    await first.provider.register_client(client)
    sensitive = {"token": "fictional-sensitive-upstream-token"}
    await first_store.put("sensitive", sensitive)
    second_store = create_storage(settings, directory)
    second = create_auth(settings, storage=second_store)
    restored = await second.provider.get_client(client.client_id)
    assert restored.client_id == client.client_id
    assert restored.redirect_uris == client.redirect_uris
    assert await second_store.get("sensitive") == sensitive
    for file in directory.rglob("*"):
        if file.is_file():
            assert sensitive["token"].encode() not in file.read_bytes()
            assert file.stat().st_mode & 0o077 == 0


async def test_changed_secret_cannot_decrypt_existing_state(auth_setup, tmp_path):
    settings = auth_setup[0].settings
    store = create_storage(settings, tmp_path / "oauth")
    await store.put("test", {"token": "fictional-sensitive-token"})
    changed = settings.model_copy(
        update={
            "github_client_secret": type(settings.github_client_secret)(
                "another-fictional-secret-with-enough-entropy"
            )
        }
    )
    assert await create_storage(changed, tmp_path / "oauth").get("test") is None


def test_shared_oauth_directory_is_rejected(auth_setup, tmp_path):
    directory = tmp_path / "oauth"
    directory.mkdir(mode=0o755)
    directory.chmod(0o755)
    with pytest.raises(ValueError, match="permissions 700"):
        create_storage(auth_setup[0].settings, directory)


def test_symlinked_oauth_directory_is_rejected(auth_setup, tmp_path):
    directory = tmp_path / "oauth"
    directory.symlink_to(tmp_path / "target")
    with pytest.raises(ValueError, match="symbolic link"):
        create_storage(auth_setup[0].settings, directory)
