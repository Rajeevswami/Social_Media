"""Shared FastAPI dependencies: authentication + per-key rate limiting."""
from __future__ import annotations

import logging

from fastapi import Depends, HTTPException, status

from app.core.config import get_settings
from app.core.rate_limit import SlidingWindowLimiter
from app.core.security import require_api_key

logger = logging.getLogger("ai.ratelimit")

_settings = get_settings()
limiter = SlidingWindowLimiter(
    max_requests=_settings.rate_limit_requests,
    window_seconds=_settings.rate_limit_window_seconds,
)


async def rate_limited_api_key(api_key: str = Depends(require_api_key)) -> str:
    """Authenticate, then enforce the per-key sliding window.

    This is the second line of defence: Django throttles per *user*, this
    throttles per *caller*, so a leaked key or a buggy retry loop cannot blow
    up the model-provider bill.
    """
    allowed, remaining, retry_after = await limiter.check(api_key)
    if not allowed:
        logger.warning(
            "rate limit exceeded",
            extra={"event": "ratelimit.exceeded", "key_fingerprint": api_key[:4], "retry_after": retry_after},
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded for this API key.",
            headers={"Retry-After": str(retry_after)},
        )
    return api_key


def rate_limit_headers(api_key: str, remaining: int) -> dict[str, str]:
    return {
        "X-RateLimit-Limit": str(_settings.rate_limit_requests),
        "X-RateLimit-Remaining": str(remaining),
    }
