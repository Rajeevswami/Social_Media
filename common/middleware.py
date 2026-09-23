"""Request-scoped middleware: correlation id, user context, access log."""
from __future__ import annotations

import time
import uuid

from django.http import HttpRequest, HttpResponse

from common.logging import request_id_var, request_path_var, request_user_var, get_logger

logger = get_logger("http.access")

_HEADER = "X-Request-ID"
_SKIP_PREFIXES = ("/static/", "/media/", "/healthz")


class RequestLogMiddleware:
    """Give every request an id and log one structured line per request."""

    def __init__(self, get_response) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request_id = request.headers.get(_HEADER) or uuid.uuid4().hex[:12]
        request.request_id = request_id  # type: ignore[attr-defined]

        tokens = [
            request_id_var.set(request_id),
            request_path_var.set(request.path),
            request_user_var.set(getattr(getattr(request, "user", None), "username", None)),
        ]
        started = time.perf_counter()
        try:
            response = self.get_response(request)
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            if not request.path.startswith(_SKIP_PREFIXES):
                logger.info(
                    "request completed",
                    extra={
                        "event": "http.request",
                        "request_id": request_id,
                        "method": request.method,
                        "status": getattr(locals().get("response"), "status_code", 500),
                        "duration_ms": duration_ms,
                    },
                )
            for token in reversed(tokens):
                token.var.reset(token)

        response[_HEADER] = request_id
        return response
