"""Internal API-key authentication.

This service is *not* public: only the Django app (server to server) may call
it, authenticated with a shared secret in the `X-API-Key` header. Keys are
compared in constant time, and failures return an opaque 401.
"""
from __future__ import annotations

import hmac
import logging

from fastapi import Header, HTTPException, status

from app.core.config import get_settings

logger = logging.getLogger("ai.auth")


async def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> str:
    settings = get_settings()
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    for known in settings.api_keys:
        if hmac.compare_digest(x_api_key, known):
            return x_api_key

    # Log the attempt (without the secret) so abuse is visible.
    logger.warning("rejected api key", extra={"event": "auth.rejected", "key_fingerprint": x_api_key[:4]})
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API key.",
        headers={"WWW-Authenticate": "ApiKey"},
    )
