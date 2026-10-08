import base64
import hashlib
from urllib.parse import urlsplit

import httpx2
from fastmcp.server.auth.providers.github import GitHubTokenVerifier
from starlette.testclient import TestClient

from mason.server import create_app


def test_oauth_discovery_advertises_the_proxy_and_pkce(auth_setup):
    verifier, _, _ = auth_setup
    app = create_app(verifier.settings, verifier=verifier)
    with TestClient(app, base_url=verifier.settings.origin) as client:
        resource = client.get("/.well-known/oauth-protected-resource/mcp").json()
        oauth = client.get("/.well-known/oauth-authorization-server").json()
        assert resource["authorization_servers"] == [oauth["issuer"]]
        assert oauth["issuer"] == "https://mason.example.com/"
        assert "S256" in oauth["code_challenge_methods_supported"]
        assert oauth["registration_endpoint"] == "https://mason.example.com/register"
        assert oauth["authorization_response_iss_parameter_supported"] is True


def test_unknown_client_callback_is_rejected(auth_setup):
    verifier, _, _ = auth_setup
    app = create_app(verifier.settings, verifier=verifier)
    with TestClient(app, base_url=verifier.settings.origin) as client:
        response = client.post(
            "/register",
            json={"redirect_uris": ["https://untrusted.example.com/callback"]},
        )
        assert response.status_code == 400


def test_authorization_requires_consent_before_github_redirect(auth_setup):
    verifier, _, _ = auth_setup
    app = create_app(verifier.settings, verifier=verifier)
    callback = "https://chatgpt.com/connector_platform_oauth_redirect"
    with TestClient(app, base_url=verifier.settings.origin, follow_redirects=False) as client:
        registered = client.post(
            "/register",
            json={
                "client_name": "Mason test client",
                "redirect_uris": [callback],
                "grant_types": ["authorization_code", "refresh_token"],
                "response_types": ["code"],
                "token_endpoint_auth_method": "none",
                "scope": "read:user",
            },
        )
        assert registered.status_code == 201
        verifier_text = "a" * 43
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier_text.encode()).digest())
        response = client.get(
            "/authorize",
            params={
                "client_id": registered.json()["client_id"],
                "redirect_uri": callback,
                "response_type": "code",
                "scope": "read:user",
                "state": "test-state",
                "code_challenge": challenge.rstrip(b"=").decode(),
                "code_challenge_method": "S256",
                "resource": verifier.settings.public_url,
            },
        )
        assert response.status_code in {302, 303, 307}
        location = response.headers["Location"]
        assert urlsplit(location).path == "/consent"
        consent = client.get(location)
        assert consent.status_code == 200
        assert "csrf_token" in consent.text
        assert "Mason test client" in consent.text
        assert (
            "Content-Security-Policy" in consent.headers
            or "Content-Security-Policy" in consent.text
        )


def test_oauth_routes_reject_an_unexpected_host(auth_setup):
    verifier, _, _ = auth_setup
    app = create_app(verifier.settings, verifier=verifier)
    with TestClient(app, base_url=verifier.settings.origin) as client:
        response = client.post("/register", json={}, headers={"Host": "evil.example.com"})
        assert response.status_code == 400


async def test_github_identity_and_scopes_are_checked_without_repo_permissions():
    requests = []

    def respond(request):
        requests.append(request)
        data = {"id": 123, "login": "demo-owner"} if request.url.path == "/user" else []
        return httpx2.Response(200, json=data, headers={"X-OAuth-Scopes": "read:user"})

    async with httpx2.AsyncClient(transport=httpx2.MockTransport(respond)) as client:
        verifier = GitHubTokenVerifier(required_scopes=["read:user"], http_client=client)
        result = await verifier.verify_token("fictional-github-token")
        assert result.subject == "123"
        assert result.scopes == ["read:user"]
        assert all(request.url.host == "api.github.com" for request in requests)
