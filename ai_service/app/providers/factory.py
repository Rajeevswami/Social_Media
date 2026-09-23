"""Provider selection + graceful degradation.

`get_provider()` returns the configured backend; `run_with_fallback()` wraps a
provider call so that, if the hosted model fails and fallback is allowed, the
deterministic heuristic answers instead — with `degraded=True` so the caller
(and the audit log) can tell the difference.
"""
from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from functools import lru_cache
from typing import TypeVar

from app.core.config import get_settings
from app.providers.base import AIProvider, ProviderError
from app.providers.heuristic import HeuristicProvider

logger = logging.getLogger("ai.provider")

T = TypeVar("T")


@lru_cache(maxsize=4)
def _build(provider_name: str, heuristic_only: bool = False) -> AIProvider:
    if heuristic_only or provider_name == "heuristic":
        settings = get_settings()
        return HeuristicProvider(
            toxicity_threshold=settings.toxicity_threshold, spam_threshold=settings.spam_threshold
        )
    if provider_name == "openai":
        from app.providers.openai_provider import OpenAIProvider

        return OpenAIProvider()
    if provider_name == "huggingface":
        from app.providers.huggingface import HuggingFaceProvider

        return HuggingFaceProvider()
    raise ProviderError(f"unknown provider '{provider_name}'")


def get_provider() -> AIProvider:
    settings = get_settings()
    try:
        return _build(settings.provider)
    except ProviderError as exc:
        logger.error(
            "configured provider unavailable, using heuristic",
            extra={"event": "provider.init.fallback", "provider": settings.provider, "error": str(exc)},
        )
        return _build("heuristic", heuristic_only=True)


def reset_provider_cache() -> None:
    _build.cache_clear()


async def run_with_fallback(
    primary: Callable[[], Awaitable[T]], fallback: Callable[[], Awaitable[T]], *, event: str
) -> tuple[T, bool]:
    """Run `primary`; on provider failure run `fallback`. Returns (result, degraded)."""
    try:
        return await primary(), False
    except ProviderError as exc:
        if not get_settings().allow_heuristic_fallback:
            raise
        logger.warning(
            "degrading to heuristic provider",
            extra={"event": f"{event}.degraded", "error": str(exc)},
        )
        return await fallback(), True
