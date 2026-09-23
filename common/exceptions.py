"""Uniform DRF error envelope + logging for server-side failures.

Every error response looks like::

    {"detail": "human readable message", "code": "not_found", "errors": {...}}

`errors` carries the field-level detail for validation failures, so clients can
map messages onto form fields while still having one stable top-level string.
"""
from __future__ import annotations

import logging

from django.core.exceptions import PermissionDenied, ValidationError as DjangoValidationError
from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger("django.request")

_CODE_BY_STATUS = {
    400: "bad_request",
    401: "unauthenticated",
    403: "permission_denied",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    422: "unprocessable_entity",
    429: "throttled",
}


def _split_payload(raw):
    """Return (detail_message, field_errors) from any DRF error payload."""
    if isinstance(raw, dict):
        candidate = raw.get("detail")
        if candidate is not None:
            if isinstance(candidate, (list, tuple)):
                candidate = candidate[0] if candidate else None
            errors = {key: value for key, value in raw.items() if key != "detail"}
            return (str(candidate) if candidate is not None else None), errors
        return None, raw
    if isinstance(raw, (list, tuple)):
        first = raw[0] if raw else None
        return (str(first) if first is not None else None), {}
    return None, {}


def api_exception_handler(exc, context):
    """Convert Django/DRF exceptions into a consistent JSON envelope."""
    if isinstance(exc, DjangoValidationError):
        exc = APIException(detail=getattr(exc, "messages", None) or str(exc))
        exc.status_code = status.HTTP_400_BAD_REQUEST
    elif isinstance(exc, Http404):
        exc = APIException(detail="Resource not found.")
        exc.status_code = status.HTTP_404_NOT_FOUND
    elif isinstance(exc, PermissionDenied):
        exc = APIException(detail="You do not have permission to perform this action.")
        exc.status_code = status.HTTP_403_FORBIDDEN

    response = exception_handler(exc, context)
    if response is None:
        logger.exception(
            "unhandled api exception",
            extra={"event": "api.unhandled_exception", "exception_type": type(exc).__name__},
        )
        return Response(
            {"detail": "An unexpected error occurred.", "code": "internal_error", "errors": {}},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    detail, errors = _split_payload(response.data)
    response.data = {
        "detail": detail or "Request failed.",
        "code": _CODE_BY_STATUS.get(response.status_code, "error"),
        "errors": errors,
    }
    return response
