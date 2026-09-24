"""Pydantic contract tests (the service boundary schema)."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.caption import CaptionRequest, CaptionResponse
from app.schemas.moderation import ModerationRequest, ModerationResponse
from app.schemas.mood import MoodCheckRequest, MoodCheckResponse


def test_moderation_request_strips_whitespace():
    request = ModerationRequest(text="   hello world   ")
    assert request.text == "hello world"


def test_moderation_request_rejects_blank_text():
    with pytest.raises(ValidationError):
        ModerationRequest(text="    ")


def test_moderation_request_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        ModerationRequest(text="hi", injected_field="x")


def test_moderation_response_rejects_out_of_range_confidence():
    with pytest.raises(ValidationError):
        ModerationResponse(is_safe=True, flags=[], confidence=1.4, provider="heuristic")


def test_moderation_response_defaults():
    response = ModerationResponse(is_safe=True, flags=[], confidence=0.8, provider="heuristic")
    assert response.degraded is False
    assert response.scores == []
    assert response.post_id is None


def test_caption_request_defaults_to_three():
    assert CaptionRequest(idea="sunset").count == 3


@pytest.mark.parametrize("count", [0, 4, -1])
def test_caption_request_rejects_bad_count(count):
    with pytest.raises(ValidationError):
        CaptionRequest(idea="sunset", count=count)


def test_caption_response_bounds():
    with pytest.raises(ValidationError):
        CaptionResponse(suggestions=[], provider="heuristic")


def test_mood_request_drops_blank_entries():
    request = MoodCheckRequest(texts=["  tired ", "", "   ", "hopeless"])
    assert request.texts == ["tired", "hopeless"]


def test_mood_request_rejects_all_blank():
    with pytest.raises(ValidationError):
        MoodCheckRequest(texts=["", "  "])


def test_mood_response_carries_disclaimer():
    response = MoodCheckResponse(
        mood_signal="negative", suggestion="rest a bit", posts_analyzed=5,
        positive_ratio=0.1, negative_ratio=0.6, provider="heuristic",
    )
    assert "not a diagnosis" in response.disclaimer.lower()


def test_mood_response_rejects_bad_ratios():
    with pytest.raises(ValidationError):
        MoodCheckResponse(
            mood_signal="neutral", suggestion="", posts_analyzed=1,
            positive_ratio=1.5, negative_ratio=0.0, provider="heuristic",
        )
