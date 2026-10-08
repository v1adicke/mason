import time
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from mason.auth import OwnerTokenVerifier
from mason.config import Settings


@pytest.fixture
def auth_setup():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    settings = Settings(
        _env_file=None,
        mode="demo",
        public_url="https://mason.example.com/mcp",
        oauth_issuer="https://auth.example.com/",
        oauth_jwks_url="https://auth.example.com/jwks",
        oauth_owner="owner",
    )
    verifier = OwnerTokenVerifier(settings)
    verifier.keys.get_signing_key_from_jwt = lambda token: SimpleNamespace(key=key.public_key())
    claims = {
        "sub": "owner",
        "iss": settings.oauth_issuer,
        "aud": settings.public_url,
        "scope": "telegram:read",
        "iat": int(time.time()),
        "exp": int(time.time()) + 300,
    }
    return verifier, key, claims
