"""Unit tests for the AI service HTTP client (headers, retries, error mapping)."""
from __future__ import annotations

import json
from unittest import mock

import httpx
import pytest

from ai_companion.client import AIServiceClient
from ai_companion.errors import (
    AIServiceBadResponse,
    AIServiceRejected,
    AIServiceTimeout,
    AIServiceUnavailable,
)


def client_with(handler, retries=0, timeout=1.0):
    return AIServiceClient(
        base_url="http://ai.test",
        api_key="unit-test-key",
        transport=httpx.MockTransport(handler),
        retries=retries,
        timeout=timeout,
    )


@pytest.mark.django_db
class TestRequestShape:
    def test_sends_api_key_header_and_json_body(self):
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["headers"] = dict(request.headers)
            seen["body"] = json.loads(request.content)
            return httpx.Response(200, json={"is_safe": True, "flags": [], "confidence": 0.9})

        result = client_with(handler).moderate("hello", post_id=7)
        assert result["is_safe"] is True
        assert seen["headers"]["x-api-key"] == "unit-test-key"
        assert seen["body"] == {"text": "hello", "post_id": 7, "language": "en"}

    def test_mood_check_payload(self):
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["body"] = json.loads(request.content)
            return httpx.Response(200, json={"mood_signal": "neutral", "suggestion": ""})

        client_with(handler).mood_check(["a", "b"], user_id=3)
        assert seen["body"] == {"texts": ["a", "b"], "user_id": 3}

    def test_caption_payload_only_includes_tone_when_given(self):
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["body"] = json.loads(request.content)
            return httpx.Response(200, json={"suggestions": []})

        client_with(handler).caption("sunset", count=2)
        assert seen["body"] == {"idea": "sunset", "count": 2}


@pytest.mark.django_db
class TestRetryBehaviour:
    def test_retries_503_then_succeeds(self):
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            if calls["n"] == 1:
                return httpx.Response(503, json={"detail": "cold start"})
            return httpx.Response(200, json={"is_safe": True, "flags": [], "confidence": 1.0})

        with mock.patch("ai_companion.client.time.sleep") as sleep:
            result = client_with(handler, retries=2).moderate("hi")

        assert result["is_safe"] is True
        assert calls["n"] == 2
        sleep.assert_called_once()  # backoff between attempts

    def test_honours_retry_after_header(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, json={"detail": "slow down"}, headers={"Retry-After": "7"})

        with mock.patch("ai_companion.client.time.sleep") as sleep:
            with pytest.raises(AIServiceRejected) as exc_info:
                client_with(handler, retries=1).caption("idea")

        assert exc_info.value.status_code == 429
        sleep.assert_called_with(7.0)

    def test_does_not_retry_client_errors(self):
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(422, json={"detail": "text too long"})

        with pytest.raises(AIServiceRejected) as exc_info:
            client_with(handler, retries=3).moderate("x" * 5000)

        assert calls["n"] == 1
        assert "text too long" in str(exc_info.value)


@pytest.mark.django_db
class TestErrorMapping:
    def test_timeout_maps_to_timeout_error(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("too slow", request=request)

        with pytest.raises(AIServiceTimeout) as exc_info:
            client_with(handler, timeout=0.01).moderate("hi")
        assert exc_info.value.code == "ai_service_timeout"

    def test_connect_error_maps_to_unavailable(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused", request=request)

        with pytest.raises(AIServiceUnavailable):
            client_with(handler).moderate("hi")

    def test_non_json_body_maps_to_bad_response(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="<html>gateway</html>")

        with pytest.raises(AIServiceBadResponse):
            client_with(handler).moderate("hi")

    def test_non_object_json_maps_to_bad_response(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=["unexpected", "array"])

        with pytest.raises(AIServiceBadResponse):
            client_with(handler).moderate("hi")

    def test_health_endpoint(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"status": "ok", "provider": "heuristic"})

        assert client_with(handler).health()["status"] == "ok"
