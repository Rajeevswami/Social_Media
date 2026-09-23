"""Shared async HTTP plumbing for hosted providers.

One `httpx.AsyncClient` per call is fine at this traffic level; the important
parts are the timeouts, the single retry on transport errors, and turning every
failure mode into a typed `ProviderError` the routers can handle uniformly.
"""
from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from app.core.config import get_settings
from app.providers.base import ProviderError

logger = logging.getLogger("ai.provider")


async def post_json(url: str, *, headers: dict[str, str], payload: dict[str, Any], event: str) -> Any:
    settings = get_settings()
    timeout = httpx.Timeout(settings.request_timeout_seconds, connect=settings.connect_timeout_seconds)
    attempts = settings.max_retries + 1
    last_error: Exception | None = None

    for attempt in range(attempts):
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, headers=headers, json=payload)
            duration_ms = round((time.perf_counter() - started) * 1000, 1)

            if response.status_code >= 500 or response.status_code == 429:
                logger.warning(
                    "provider returned retryable status",
                    extra={
                        "event": event,
                        "status": response.status_code,
                        "attempt": attempt + 1,
                        "duration_ms": duration_ms,
                    },
                )
                last_error = ProviderError(f"provider HTTP {response.status_code}")
                continue

            if response.status_code >= 400:
                raise ProviderError(f"provider rejected request: HTTP {response.status_code}")

            logger.info(
                "provider call ok",
                extra={"event": event, "status": response.status_code, "duration_ms": duration_ms},
            )
            return response.json()

        except httpx.TimeoutException as exc:
            last_error = exc
            logger.warning(
                "provider call timed out",
                extra={
                    "event": event, "attempt": attempt + 1,
                    "timeout_seconds": settings.request_timeout_seconds,
                },
            )
        except httpx.HTTPError as exc:
            last_error = exc
            logger.warning(
                "provider transport error",
                extra={"event": event, "attempt": attempt + 1, "error": f"{type(exc).__name__}: {exc}"},
            )
        except ValueError as exc:  # malformed JSON body
            raise ProviderError("provider returned a non-JSON body") from exc

    raise ProviderError(f"provider call failed after {attempts} attempt(s): {last_error}")
