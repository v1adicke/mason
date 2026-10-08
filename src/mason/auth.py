from time import time

from fastmcp.server.auth.providers.github import GitHubProvider
from key_value.aio.stores.memory import MemoryStore
from mcp.server.auth.provider import AccessToken

from mason.config import Settings

READ_SCOPE = "read:user"


def create_auth(settings: Settings):
    """let the library handle OAuth while keeping trial state in memory"""
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
        client_storage=MemoryStore(),
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
            if type(expiry) is not int or expiry <= time() or claims.get("token_use") != "access":
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
