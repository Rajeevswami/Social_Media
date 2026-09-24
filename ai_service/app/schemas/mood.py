from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

MoodSignal = Literal["positive", "neutral", "negative"]


class MoodCheckRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    texts: list[str] = Field(..., min_length=1, description="The user's last N post texts, newest first.")
    user_id: int | None = Field(default=None, ge=1)

    @field_validator("texts")
    @classmethod
    def _clean(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values if value and value.strip()]
        if not cleaned:
            raise ValueError("at least one non-empty text is required")
        return cleaned


class MoodCheckResponse(BaseModel):
    """A coarse tone signal. Explicitly NOT a diagnosis — see `disclaimer`."""

    mood_signal: MoodSignal
    suggestion: str
    posts_analyzed: int = Field(..., ge=0)
    positive_ratio: float = Field(..., ge=0.0, le=1.0)
    negative_ratio: float = Field(..., ge=0.0, le=1.0)
    provider: str
    degraded: bool = False
    disclaimer: str = (
        "Aggregated tone estimate from public post text. Not a diagnosis and not medical advice."
    )
