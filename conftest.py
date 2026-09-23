"""Shared pytest fixtures.

The AI service is never called for real in tests: a `httpx.MockTransport`
stands in, so the *actual* `AIServiceClient` (headers, retries, parsing, error
mapping) is exercised end to end.
"""
from __future__ import annotations

import json
from unittest import mock

import httpx
import pytest
from rest_framework.test import APIClient

from ai_companion.client import AIServiceClient


# ---------------------------------------------------------------------------
# Fake AI microservice
# ---------------------------------------------------------------------------
def make_handler(mood_signal: str = "neutral", status_code: int = 200, calls: list | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(request)
        if status_code != 200:
            return httpx.Response(status_code, json={"detail": "boom"})
        body = json.loads(request.content or b"{}")
        path = request.url.path
        if path == "/moderate":
            text = (body.get("text") or "").lower()
            unsafe = any(word in text for word in ("kill", "hate you"))
            return httpx.Response(
                200,
                json={
                    "is_safe": not unsafe,
                    "flags": ["toxicity"] if unsafe else [],
                    "confidence": 0.42 if unsafe else 0.95,
                    "reason": "Flagged by the toxicity policy." if unsafe else "No issues found.",
                    "provider": "mock",
                },
            )
        if path == "/caption":
            idea = body.get("idea", "")
            return httpx.Response(
                200,
                json={
                    "suggestions": [f"{idea} — one", f"{idea} — two", f"{idea} — three"],
                    "provider": "mock",
                },
            )
        if path == "/mood-check":
            return httpx.Response(
                200,
                json={
                    "mood_signal": mood_signal,
                    "suggestion": "Small walks help.",
                    "provider": "mock",
                    "posts_analyzed": len(body.get("texts", [])),
                },
            )
        if path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        return httpx.Response(404, json={"detail": "not found"})

    return handler


@pytest.fixture
def ai_calls():
    return []


@pytest.fixture
def mock_ai_client(ai_calls):
    """Patch the client factory used by tasks and API views."""
    transport = httpx.MockTransport(make_handler(calls=ai_calls))
    client = AIServiceClient(transport=transport, retries=0, timeout=1.0)
    with mock.patch("ai_companion.tasks.get_client", return_value=client), \
            mock.patch("ai_companion.api_views.get_client", return_value=client):
        yield client


@pytest.fixture
def negative_mood_client(ai_calls):
    transport = httpx.MockTransport(make_handler(mood_signal="negative", calls=ai_calls))
    client = AIServiceClient(transport=transport, retries=0, timeout=1.0)
    with mock.patch("ai_companion.tasks.get_client", return_value=client), \
            mock.patch("ai_companion.api_views.get_client", return_value=client):
        yield client


# ---------------------------------------------------------------------------
# Users / clients
# ---------------------------------------------------------------------------
@pytest.fixture
def user_factory(db):
    from accounts.models import User

    def _make(username="alice", email=None, **kwargs):
        return User.objects.create_user(
            username=username,
            email=email or f"{username}@example.com",
            password="Str0ngPass!234",
            **kwargs,
        )

    return _make


@pytest.fixture
def user(user_factory):
    return user_factory()


@pytest.fixture
def other_user(user_factory):
    return user_factory(username="bob", email="bob@example.com")


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def auth_client(api_client, user):
    """Session-authenticated client (also valid for DRF's SessionAuthentication)."""
    api_client.force_authenticate(user=user)
    return api_client
