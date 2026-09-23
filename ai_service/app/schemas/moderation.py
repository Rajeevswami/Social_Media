"""Pydantic models — the contract between Django and the AI service.

Every constraint here is also enforced by DRF on the Django side; duplicating
them is deliberate (defence in depth at a service boundary).
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ModerationRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    text: str = Field(..., min_length=1, description="Post text to review.")
    post_id: int | None = Field(default=None, ge=1, description="Optional correlation id.")
    language: str = Field(default="en", max_length=8)

    @field_validator("text")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text must not be blank")
        return value


class ModerationFlag(BaseModel):
    category: Literal["toxicity", "hate", "spam", "violence", "sexual", "pii", "other"]
    score: float = Field(..., ge=0.0, le=1.0)


class ModerationResponse(BaseModel):
    """The Django side stores `flags` verbatim and never deletes a post on it."""

    is_safe: bool
    flags: list[str] = Field(default_factory=list)
    scores: list[ModerationFlag] = Field(default_factory=list)
    confidence: float = Field(..., ge=0.0, le=1.0)
    reason: str = ""
    provider: str
    degraded: bool = Field(
        default=False, description="True when the configured provider failed and a fallback answered."
    )
    post_id: int | None = None
