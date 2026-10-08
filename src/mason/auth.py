import asyncio

import jwt
from jwt import PyJWKClient
from mcp.server.auth.provider import AccessToken

from mason.config import Settings

READ_SCOPE = "telegram:read"


class OwnerTokenVerifier:
    """accept signed access tokens belonging to the configured owner"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.keys = PyJWKClient(settings.oauth_jwks_url, timeout=5)

    async def verify_token(self, token: str) -> AccessToken | None:
        if len(token) > 8192:
            return None
        try:
            return await asyncio.to_thread(self._verify, token)
        except (jwt.PyJWTError, ValueError, TypeError, KeyError):
            return None

    def _verify(self, token: str) -> AccessToken | None:
        header = jwt.get_unverified_header(token)
        if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
            return None
        if len(header["kid"]) > 256:
            return None
        key = self.keys.get_signing_key_from_jwt(token).key
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=self.settings.public_url,
            issuer=self.settings.oauth_issuer,
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        )
        if claims["sub"] != self.settings.oauth_owner:
            return None
        scope = claims.get("scope", "")
        if not isinstance(scope, str) or READ_SCOPE not in scope.split():
            return None
        return AccessToken(
            token=token,
            client_id=str(claims.get("azp", claims["sub"])),
            subject=claims["sub"],
            scopes=scope.split(),
            expires_at=claims["exp"],
            resource=self.settings.public_url,
        )
