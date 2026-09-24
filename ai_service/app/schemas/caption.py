from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CaptionRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    idea: str = Field(..., min_length=2, max_length=300, description="Short idea or keyword list.")
    tone: Literal["casual", "witty", "inspirational", "professional"] | None = None
    count: int = Field(default=3, ge=1, le=3)

    @field_validator("idea")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("idea must not be blank")
        return value


class CaptionResponse(BaseModel):
    suggestions: list[str] = Field(..., min_length=1, max_length=3)
    provider: str
    degraded: bool = False
