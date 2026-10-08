import jwt
import pytest


async def test_owner_token_is_accepted(auth_setup):
    verifier, key, claims = auth_setup
    token = jwt.encode(claims, key, algorithm="HS256")
    result = await verifier.verify_token(token)
    assert result.subject == "123"
    assert result.resource == "https://mason.example.com/mcp"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("aud", "https://another-service.example.com/mcp"),
        ("iss", "https://another-issuer.example.com/"),
        ("scope", "repo"),
        ("exp", 1),
        ("exp", None),
        ("token_use", "refresh"),
        ("jti", "unknown-token"),
    ],
)
async def test_invalid_proxy_tokens_are_rejected(auth_setup, field, value):
    verifier, key, claims = auth_setup
    claims[field] = value
    token = jwt.encode(claims, key, algorithm="HS256")
    assert await verifier.verify_token(token) is None


async def test_another_github_owner_is_rejected(auth_setup):
    verifier, key, claims = auth_setup
    verifier.provider._token_validator.verify_token.return_value.subject = "456"
    token = jwt.encode(claims, key, algorithm="HS256")
    assert await verifier.verify_token(token) is None


async def test_revoked_github_token_is_rejected(auth_setup):
    verifier, key, claims = auth_setup
    verifier.provider._token_validator.verify_token.return_value = None
    token = jwt.encode(claims, key, algorithm="HS256")
    assert await verifier.verify_token(token) is None


async def test_wrong_signature_is_rejected(auth_setup):
    verifier, _, claims = auth_setup
    token = jwt.encode(claims, "another-signing-key-with-enough-entropy", algorithm="HS256")
    assert await verifier.verify_token(token) is None


async def test_malformed_token_never_reaches_github(auth_setup):
    verifier, _, _ = auth_setup
    assert await verifier.verify_token("not-a-token") is None
    verifier.provider._token_validator.verify_token.assert_not_awaited()
