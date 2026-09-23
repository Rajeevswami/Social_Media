"""Provider abstraction.

Three interchangeable backends behind one async interface:

* `openai`       — Chat Completions with JSON responses (best quality)
* `huggingface`  — HF Inference API (classification + generation)
* `heuristic`    — local lexicon model (no network, always available)

Every provider returns the same dataclasses, so routers never branch on
provider and a failure can transparently degrade to the heuristic model.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Protocol

from app.schemas.mood import MoodSignal


class ProviderError(Exception):
    """Raised when the remote model call fails (timeout, 5xx, bad payload)."""


@dataclass
class ModerationVerdict:
    is_safe: bool
    flags: list[str]
    scores: dict[str, float] = field(default_factory=dict)
    confidence: float = 1.0
    reason: str = ""


@dataclass
class CaptionSuggestions:
    suggestions: list[str]


@dataclass
class MoodVerdict:
    signal: MoodSignal
    suggestion: str
    positive_ratio: float
    negative_ratio: float


class AIProvider(ABC):
    name: str = "abstract"

    @abstractmethod
    async def moderate(self, text: str) -> ModerationVerdict:
        """Classify a single post."""

    @abstractmethod
    async def captions(self, idea: str, tone: str | None, count: int) -> CaptionSuggestions:
        """Return 1-3 caption options."""

    @abstractmethod
    async def mood(self, texts: list[str]) -> MoodVerdict:
        """Aggregate tone over a user's recent posts."""


class ProviderFactory(Protocol):
    def __call__(self) -> AIProvider: ...
