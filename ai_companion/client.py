"""HTTP client for the FastAPI AI microservice.

Design notes:

* **Synchronous httpx client.** Django views/ORM run sync; the async work
  belongs to the FastAPI service (and to Celery for anything off the request
  path). Running an event loop inside a gunicorn worker buys nothing here.
* **Timeouts on every call**, retries only for idempotent/cheap failures
  (transport errors, 429, 5xx) with exponential backoff.
* **Typed errors** (see errors.py) so callers implement the fail-open /
  fail-closed policy instead of parsing bodies.
* **Structured logging** of every call: event name, latency, status, provider.
"""
from __future__ import annotations

import time
import uuid
from typing import Any

import httpx
from django.conf import settings

from ai_companion.errors import (
    AIServiceBadResponse,
    AIServiceError,
    AIServiceRejected,
    AIServiceTimeout,
    AIServiceUnavailable,
)
from common.logging import get_logger

logger = get_logger("ai_client")

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class AIServiceClient:
    """Thin, testable wrapper around the AI service REST API."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float | None = None,
        retries: int | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = (base_url or settings.AI_SERVICE_BASE_URL).rstrip("/")
        self.api_key = api_key or settings.AI_SERVICE_API_KEY
        self.timeout = timeout or settings.AI_SERVICE_TIMEOUT_SECONDS
        self.retries = retries if retries is not None else settings.AI_SERVICE_RETRIES
        self._transport = transport  # injectable for tests (httpx.MockTransport)

    # -- public API ------------------------------------------------------
    def moderate(self, text: str, *, post_id: int | None = None, language: str = "en") -> dict[str, Any]:
        return self._post("/moderate", {"text": text, "post_id": post_id, "language": language}, event="ai.moderate")

    def caption(self, idea: str, *, tone: str | None = None, count: int = 3) -> dict[str, Any]:
        payload = {"idea": idea, "count": count}
        if tone:
            payload["tone"] = tone
        return self._post("/caption", payload, event="ai.caption")

    def mood_check(self, texts: list[str], *, user_id: int | None = None) -> dict[str, Any]:
        return self._post(
            "/mood-check", {"texts": texts, "user_id": user_id}, event="ai.mood_check"
        )

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health", event="ai.health", retries=0)

    # -- internals -------------------------------------------------------
    def _post(self, path: str, payload: dict, *, event: str) -> dict:
        return self._request("POST", path, json=payload, event=event)

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        event: str,
        retries: int | None = None,
    ) -> dict:
        retries = self.retries if retries is None else retries
        headers = {
            "X-API-Key": self.api_key,
            "X-Request-ID": uuid.uuid4().hex[:12],
            "Accept": "application/json",
        }
        last_error: Exception | None = None

        for attempt in range(retries + 1):
            started = time.perf_counter()
            try:
                with httpx.Client(
                    base_url=self.base_url,
                    headers=headers,
                    timeout=httpx.Timeout(self.timeout, connect=min(3.0, self.timeout)),
                    transport=self._transport,
                ) as client:
                    response = client.request(method, path, json=json)
                duration_ms = round((time.perf_counter() - started) * 1000, 1)

                if response.status_code == 200:
                    logger.info(
                        "ai call succeeded",
                        extra={
                            "event": event, "attempt": attempt + 1, "status": 200,
                            "duration_ms": duration_ms, "path": path,
                        },
                    )
                    return self._parse(response, event)

                logger.warning(
                    "ai call failed",
                    extra={
                        "event": event, "attempt": attempt + 1, "status": response.status_code,
                        "duration_ms": duration_ms, "path": path,
                    },
                )
                if response.status_code in RETRYABLE_STATUS and attempt < retries:
                    time.sleep(self._backoff(attempt, response))
                    continue
                raise AIServiceRejected(
                    self._error_message(response), status_code=response.status_code
                )

            except httpx.TimeoutException as exc:
                duration_ms = round((time.perf_counter() - started) * 1000, 1)
                last_error = exc
                logger.warning(
                    "ai call timed out",
                    extra={
                        "event": event, "attempt": attempt + 1, "duration_ms": duration_ms,
                        "timeout_seconds": self.timeout, "path": path,
                    },
                )
                if attempt < retries:
                    time.sleep(self._backoff(attempt))
                    continue
                raise AIServiceTimeout() from exc

            except httpx.TransportError as exc:
                last_error = exc
                logger.warning(
                    "ai call transport error",
                    extra={
                        "event": event, "attempt": attempt + 1, "path": path,
                        "error": f"{type(exc).__name__}: {exc}",
                    },
                )
                if attempt < retries:
                    time.sleep(self._backoff(attempt))
                    continue
                raise AIServiceUnavailable(f"AI service unreachable: {exc}") from exc

        # Defensive: loop always returns or raises.
        raise AIServiceError(f"AI call failed: {last_error}")  # pragma: no cover

    @staticmethod
    def _backoff(attempt: int, response: httpx.Response | None = None) -> float:
        """Exponential backoff, honouring Retry-After when the service sends it."""
        if response is not None:
            retry_after = response.headers.get("Retry-After")
            if retry_after and retry_after.isdigit():
                return min(float(retry_after), 30.0)
        return min(0.5 * (2**attempt), 10.0)

    @staticmethod
    def _parse(response: httpx.Response, event: str) -> dict:
        try:
            data = response.json()
        except ValueError as exc:
            raise AIServiceBadResponse("AI service returned a non-JSON body") from exc
        if not isinstance(data, dict):
            raise AIServiceBadResponse("AI service returned a non-object body")
        logger.debug(
            "ai response parsed",
            extra={"event": event, "provider": data.get("provider"), "keys": sorted(data.keys())},
        )
        return data

    @staticmethod
    def _error_message(response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return f"AI service error (HTTP {response.status_code})"
        if isinstance(payload, dict):
            return str(payload.get("detail") or payload.get("error") or f"HTTP {response.status_code}")
        return f"HTTP {response.status_code}"


def get_client() -> AIServiceClient:
    """Factory so tests can monkeypatch a single entry point."""
    return AIServiceClient()
