import json

import pytest

from mason.doctor import check_endpoint, doctor


def responses(settings):
    return iter(
        [
            (200, {"status": "ok"}, {}),
            (
                401,
                {},
                {
                    "WWW-Authenticate": 'Bearer resource_metadata="'
                    + settings.origin
                    + '/.well-known/oauth-protected-resource/mcp"'
                },
            ),
            (
                200,
                {"resource": settings.public_url, "authorization_servers": [settings.origin + "/"]},
                {},
            ),
            (
                200,
                {
                    "issuer": settings.origin + "/",
                    "code_challenge_methods_supported": ["S256"],
                    "authorization_endpoint": settings.origin + "/authorize",
                    "token_endpoint": settings.origin + "/token",
                    "registration_endpoint": settings.origin + "/register",
                },
                {},
            ),
        ]
    )


def test_public_endpoint_is_checked_without_sending_credentials(auth_setup, monkeypatch):
    verifier, _, _ = auth_setup
    replies = responses(verifier.settings)
    requests = []

    def fetch(url, **kwargs):
        requests.append((url, kwargs))
        return next(replies)

    monkeypatch.setattr("mason.doctor.fetch_json", fetch)
    check_endpoint(verifier.settings)
    assert len(requests) == 4
    assert all("token" not in kwargs and "headers" not in kwargs for _, kwargs in requests)


def test_anonymous_success_is_not_considered_a_healthy_endpoint(auth_setup, monkeypatch):
    verifier, _, _ = auth_setup
    replies = iter([(200, {"status": "ok"}, {}), (200, {}, {})])
    monkeypatch.setattr("mason.doctor.fetch_json", lambda *args, **kwargs: next(replies))
    with pytest.raises(ValueError, match="refuse anonymous"):
        check_endpoint(verifier.settings)


def test_diagnostics_do_not_print_invalid_secret_values(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MASON_GITHUB_CLIENT_SECRET", "private-value")
    monkeypatch.setenv("MASON_PUBLIC_URL", "http://invalid.example.com")
    assert doctor() is False
    assert "private-value" not in capsys.readouterr().out


def test_malformed_network_response_is_reported_without_echoing_it(auth_setup, monkeypatch, capsys):
    verifier, _, _ = auth_setup
    settings = verifier.settings.model_copy(update={"public_url": "https://mason.test/mcp"})
    monkeypatch.setattr("mason.doctor.Settings", lambda: settings)

    def fetch(*args, **kwargs):
        raise json.JSONDecodeError("private response contents", "private response contents", 0)

    monkeypatch.setattr("mason.doctor.fetch_json", fetch)
    assert doctor(network=True) is False
    assert "private response contents" not in capsys.readouterr().out
