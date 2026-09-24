"""Auth, rate limiting, health and provider degradation."""
from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.providers.base import ProviderError
from app.providers.factory import reset_provider_cache


def test_health_is_public_and_reports_provider(client):
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["provider"] == "heuristic"
    assert payload["degraded_mode"] is False


def test_request_id_is_echoed(client, auth_headers):
    response = client.post(
        "/moderate", json={"text": "hello"}, headers={**auth_headers, "X-Request-ID": "trace-123"}
    )
    assert response.headers["X-Request-ID"] == "trace-123"


def test_generated_request_id_when_absent(client, auth_headers):
    response = client.post("/moderate", json={"text": "hello"}, headers=auth_headers)
    assert len(response.headers["X-Request-ID"]) == 12


def test_rate_limit_returns_429_with_retry_after(client, auth_headers):
    from app.core.dependencies import limiter

    limiter.max_requests = 3
    try:
        limiter._hits.clear()
        statuses = [
            client.post("/moderate", json={"text": "hello"}, headers=auth_headers).status_code
            for _ in range(5)
        ]
    finally:
        limiter.max_requests = get_settings().rate_limit_requests
        limiter._hits.clear()

    assert statuses[:3] == [200, 200, 200]
    assert statuses[3] == 429
    assert statuses[4] == 429


def test_rate_limit_is_scoped_per_api_key(client, monkeypatch):
    from app.core.dependencies import limiter

    monkeypatch.setenv("API_KEYS", "key-one,key-two")
    get_settings.cache_clear()
    limiter.max_requests = 1
    limiter._hits.clear()
    try:
        first = client.post("/moderate", json={"text": "hi"}, headers={"X-API-Key": "key-one"})
        second_for_same_key = client.post("/moderate", json={"text": "hi"}, headers={"X-API-Key": "key-one"})
        other_key = client.post("/moderate", json={"text": "hi"}, headers={"X-API-Key": "key-two"})
    finally:
        limiter.max_requests = get_settings().rate_limit_requests
        limiter._hits.clear()

    assert first.status_code == 200
    assert second_for_same_key.status_code == 429
    assert other_key.status_code == 200


def test_cors_preflight_allows_configured_origin(client):
    response = client.options(
        "/moderate",
        headers={
            "Origin": "http://localhost:8000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "x-api-key",
        },
    )
    assert response.status_code in (200, 204)
    assert response.headers["access-control-allow-origin"] == "http://localhost:8000"


def test_openai_provider_is_used_when_configured(client, monkeypatch):
    monkeypatch.setenv("PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    get_settings.cache_clear()
    reset_provider_cache()

    async def fake_chat(self, system, user, *, event, json_mode=True):
        return {"is_safe": False, "flags": ["toxicity"], "confidence": 0.91, "reason": "insult"}

    monkeypatch.setattr("app.providers.openai_provider.OpenAIProvider._chat", fake_chat)

    response = client.post(
        "/moderate", json={"text": "whatever"}, headers={"X-API-Key": "test-api-key"}
    )
    payload = response.json()
    assert payload["provider"] == "openai"
    assert payload["is_safe"] is False
    assert payload["flags"] == ["toxicity"]
    assert payload["degraded"] is False


def test_falls_back_to_heuristic_when_provider_fails(client, monkeypatch):
    monkeypatch.setenv("PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    get_settings.cache_clear()
    reset_provider_cache()

    async def broken_chat(self, *args, **kwargs):
        raise ProviderError("upstream 500")

    monkeypatch.setattr("app.providers.openai_provider.OpenAIProvider._chat", broken_chat)

    payload = client.post(
        "/moderate", json={"text": "you idiot and a loser"}, headers={"X-API-Key": "test-api-key"}
    ).json()
    assert payload["degraded"] is True  # answered by the local heuristic
    assert payload["is_safe"] is False
    assert "toxicity" in payload["flags"]


def test_no_fallback_surfaces_503(client, monkeypatch):
    monkeypatch.setenv("PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("ALLOW_HEURISTIC_FALLBACK", "False")
    get_settings.cache_clear()
    reset_provider_cache()

    async def broken_chat(self, *args, **kwargs):
        raise ProviderError("upstream 500")

    monkeypatch.setattr("app.providers.openai_provider.OpenAIProvider._chat", broken_chat)

    response = client.post("/moderate", json={"text": "hello"}, headers={"X-API-Key": "test-api-key"})
    assert response.status_code == 503
    assert response.json()["detail"] == "Moderation provider unavailable."


def test_unconfigured_provider_degrades_instead_of_crashing(client, monkeypatch):
    monkeypatch.setenv("PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    get_settings.cache_clear()
    reset_provider_cache()

    response = client.post("/moderate", json={"text": "hello"}, headers={"X-API-Key": "test-api-key"})
    assert response.status_code == 200
    assert response.json()["provider"] == "heuristic"

    health = client.get("/health").json()
    assert health["degraded_mode"] is True


def test_unknown_method_is_405(client, auth_headers):
    assert client.get("/moderate", headers=auth_headers).status_code == 405


@pytest.mark.parametrize("path", ["/moderate", "/caption", "/mood-check"])
def test_all_endpoints_require_key(client, path):
    assert client.post(path, json={}).status_code == 401
