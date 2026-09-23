"""Typed errors for AI service interaction.

Callers branch on these instead of parsing HTTP bodies, which keeps the
fail-open/fail-closed policy in one place.
"""
from __future__ import annotations


class AIServiceError(Exception):
    """Base class for anything that went wrong talking to the AI service."""

    def __init__(self, message: str, *, status_code: int | None = None, code: str = "ai_service_error") -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"


class AIServiceTimeout(AIServiceError):
    def __init__(self, message: str = "AI service timed out") -> None:
        super().__init__(message, status_code=504, code="ai_service_timeout")


class AIServiceUnavailable(AIServiceError):
    def __init__(self, message: str = "AI service is unreachable") -> None:
        super().__init__(message, status_code=503, code="ai_service_unavailable")


class AIServiceRejected(AIServiceError):
    """The service answered, but refused / rate-limited the request."""

    def __init__(self, message: str = "AI service rejected the request", status_code: int = 400) -> None:
        super().__init__(message, status_code=status_code, code="ai_service_rejected")


class AIServiceBadResponse(AIServiceError):
    def __init__(self, message: str = "AI service returned an unexpected payload") -> None:
        super().__init__(message, status_code=502, code="ai_service_bad_response")
