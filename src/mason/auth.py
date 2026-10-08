import os
from pathlib import Path
from time import time

from cryptography.fernet import Fernet
from fastmcp.server.auth.jwt_issuer import derive_jwt_key
from fastmcp.server.auth.providers.github import GitHubProvider
from key_value.aio.protocols import AsyncKeyValue
from key_value.aio.stores.filetree import FileTreeStore
from key_value.aio.wrappers.encryption import FernetEncryptionWrapper
from mcp.server.auth.provider import AccessToken

from mason.config import Settings

READ_SCOPE = "read:user"


def create_storage(settings: Settings, directory: Path | None = None):
    """keep OAuth state encrypted in a private local directory"""
    directory = directory or Path.home() / ".local/share/mason/oauth"
    if directory.is_symlink():
        raise ValueError("the OAuth directory must not be a symbolic link")
    os.umask(0o077)
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if directory.stat().st_uid != os.getuid() or directory.stat().st_mode & 0o077:
        raise ValueError("the OAuth directory must be owned by you with permissions 700")
    key = derive_jwt_key(
        high_entropy_material=settings.github_client_secret.get_secret_value(),
        salt="mason-oauth-storage",
    )
    return FernetEncryptionWrapper(
        key_value=FileTreeStore(data_directory=directory),
        fernet=Fernet(key),
        raise_on_decryption_error=False,
    )


def create_auth(settings: Settings, *, storage: AsyncKeyValue | None = None):
    """let the library handle OAuth with encrypted local state"""
    provider = GitHubProvider(
        client_id=settings.github_client_id,
        client_secret=settings.github_client_secret.get_secret_value(),
        base_url=settings.origin,
        required_scopes=[READ_SCOPE],
        allowed_client_redirect_uris=[
            "https://chatgpt.com/connector_platform_oauth_redirect",
            "https://chatgpt.com/connector/oauth/*",
            "http://localhost:*",
            "http://127.0.0.1:*",
        ],
        client_storage=storage if storage is not None else create_storage(settings),
        require_authorization_consent=True,
        fastmcp_access_token_expiry_seconds=900,
        enable_cimd=False,
    )
    provider.set_mcp_path("/mcp")
    return OwnerTokenVerifier(settings, provider)


class OwnerTokenVerifier:
    """accept proxy tokens only after GitHub confirms the owner's identity"""

    def __init__(self, settings: Settings, provider: GitHubProvider):
        self.settings = settings
        self.provider = provider

    async def verify_token(self, token: str) -> AccessToken | None:
        if len(token) > 8192:
            return None
        try:
            claims = self.provider.jwt_issuer.verify_token(token)
            expiry = claims.get("exp")
            if (
                type(expiry) is not int
                or expiry <= time()
                or claims.get("token_use", "access") != "access"
            ):
                return None
            verified = await self.provider.verify_token(token)
            if verified is None or verified.subject != str(self.settings.github_owner_id):
                return None
            if (
                READ_SCOPE not in verified.scopes
                or READ_SCOPE not in claims.get("scope", "").split()
            ):
                return None
            return AccessToken(
                token=token,
                client_id=verified.client_id,
                subject=verified.subject,
                scopes=[READ_SCOPE],
                expires_at=expiry,
                resource=self.settings.public_url,
            )
        except Exception:
            return None
