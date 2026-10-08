import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from mason.auth import OwnerTokenVerifier
from mason.config import Settings


@pytest.fixture
def auth_setup():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    settings = Settings(
        _env_file=None,
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


async def test_owner_token_is_accepted(auth_setup):
    verifier, key, claims = auth_setup
    token = jwt.encode(claims, key, algorithm="RS256", headers={"kid": "test"})
    result = await verifier.verify_token(token)
    assert result.subject == "owner"
    assert result.resource == "https://mason.example.com/mcp"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("sub", "someone-else"),
        ("aud", "https://another-service.example.com"),
        ("iss", "https://another-issuer.example.com/"),
        ("scope", "telegram:write"),
        ("exp", 1),
    ],
)
async def test_invalid_claims_are_rejected(auth_setup, field, value):
    verifier, key, claims = auth_setup
    claims[field] = value
    token = jwt.encode(claims, key, algorithm="RS256", headers={"kid": "test"})
    assert await verifier.verify_token(token) is None


async def test_wrong_signature_is_rejected(auth_setup):
    verifier, _, claims = auth_setup
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = jwt.encode(claims, other_key, algorithm="RS256", headers={"kid": "test"})
    assert await verifier.verify_token(token) is None


async def test_malformed_token_does_not_fetch_keys(auth_setup):
    verifier, _, _ = auth_setup

    def fail(token):
        raise AssertionError("unexpected key lookup")

    verifier.keys.get_signing_key_from_jwt = fail
    assert await verifier.verify_token("not-a-token") is None
