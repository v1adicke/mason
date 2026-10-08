import asyncio
import time
from unittest.mock import AsyncMock

import pytest
from fastmcp.server.auth.oauth_proxy.models import JTIMapping, UpstreamTokenSet
from key_value.aio.stores.memory import MemoryStore
from mcp.server.auth.provider import AccessToken

from mason.auth import create_auth
from mason.config import Settings


@pytest.fixture
def auth_setup():
    settings = Settings(
        _env_file=None,
        mode="demo",
        public_url="https://mason.example.com/mcp",
        github_client_id="fictional-client-id",
        github_client_secret="fictional-client-secret-for-tests",
        github_owner_id=123,
    )
    verifier = create_auth(settings, storage=MemoryStore())
    provider = verifier.provider
    now = int(time.time())
    provider._token_validator.verify_token = AsyncMock(
        return_value=AccessToken(
            token="fictional-github-token", client_id="123", subject="123", scopes=["read:user"]
        )
    )

    async def seed():
        await provider._upstream_token_store.put(
            key="test-upstream",
            value=UpstreamTokenSet(
                upstream_token_id="test-upstream",
                access_token="fictional-github-token",
                refresh_token=None,
                refresh_token_expires_at=None,
                expires_at=now + 3600,
                token_type="Bearer",
                scope="read:user",
                client_id="mcp-test-client",
                created_at=now,
            ),
        )
        await provider._jti_mapping_store.put(
            key="test-jti",
            value=JTIMapping(jti="test-jti", upstream_token_id="test-upstream", created_at=now),
        )

    asyncio.run(seed())
    claims = {
        "iss": str(provider.issuer_url),
        "aud": settings.public_url,
        "sub": "mcp-test-client",
        "client_id": "mcp-test-client",
        "scope": "read:user",
        "jti": "test-jti",
        "token_use": "access",
        "iat": now,
        "exp": now + 300,
    }
    return verifier, provider._jwt_signing_key, claims
