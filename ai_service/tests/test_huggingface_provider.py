"""Hugging Face Inference API provider.

This provider had no test coverage at all (only OpenAI was exercised), so its
label mapping, payload-shape handling and JSON extraction were unverified. Every
test here stubs the HTTP layer (`post_json`) so no real HF key or network call is
needed -- but note this means the wire format is asserted against our *reading*
of the HF API, not against a live model response.
"""
from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.providers.base import ProviderError
from app.providers.factory import reset_provider_cache
from app.providers.huggingface import HuggingFaceProvider, _extract_json_list, _extract_json_object

KEY = {"X-API-Key": "test-api-key"}


@pytest.fixture
def hf(monkeypatch):
    """Configure the HF provider and stub its HTTP layer.

    `respond_with(payload)` sets what the next call returns; every call is
    recorded so tests can assert on the URL, headers and request body.
    """
    monkeypatch.setenv("PROVIDER", "huggingface")
    monkeypatch.setenv("HF_API_TOKEN", "hf_test_token")
    get_settings.cache_clear()
    reset_provider_cache()

    class _Handle:
        def __init__(self):
            self.calls: list[dict] = []
            self._payload: dict | list = {}

        def respond_with(self, payload):
            self._payload = payload

            calls = self.calls
            holder = self

            async def fake_post_json(url, *, headers, payload=None, event=None):
                calls.append({"url": url, "headers": headers, "payload": payload, "event": event})
                return holder._payload

            monkeypatch.setattr("app.providers.huggingface.post_json", fake_post_json)

        @property
        def last(self):
            return self.calls[-1]

    yield _Handle()
    get_settings.cache_clear()
    reset_provider_cache()


def test_moderation_maps_hf_labels_onto_our_vocabulary(client, hf):
    """HF returns raw classifier labels; we must normalise them."""
    hf.respond_with(
        [
            {"label": "toxic", "score": 0.93},
            {"label": "hate_speech", "score": 0.81},
            {"label": "severe_toxic", "score": 0.40},  # below threshold, still folded in
            {"label": "identity_hate", "score": 0.10},
        ]
    )
    payload = client.post("/moderate", json={"text": "you are trash"}, headers=KEY).json()

    assert payload["provider"] == "huggingface"
    assert payload["degraded"] is False
    assert payload["is_safe"] is False
    assert payload["flags"] == ["hate", "toxicity"]  # sorted, deduped, mapped
    assert payload["confidence"] == 0.93  # max across mapped labels


def test_moderation_flags_nothing_when_scores_are_low(client, hf):
    hf.respond_with([{"label": "toxic", "score": 0.05}, {"label": "hate", "score": 0.02}])
    payload = client.post("/moderate", json={"text": "lovely weather today"}, headers=KEY).json()
    assert payload["is_safe"] is True
    assert payload["flags"] == []
    assert payload["reason"] == "Below all safety thresholds."


def test_moderation_handles_nested_payload_shape(client, hf):
    """HF wraps multi-label output as [[...]] for some models."""
    hf.respond_with([[{"label": "toxic", "score": 0.95}]])
    payload = client.post("/moderate", json={"text": "x"}, headers=KEY).json()
    assert payload["is_safe"] is False
    assert payload["flags"] == ["toxicity"]


def test_moderation_ignores_unmapped_labels(client, hf):
    hf.respond_with([{"label": "some_unknown_label", "score": 0.99}, {"label": "toxic", "score": 0.7}])
    payload = client.post("/moderate", json={"text": "x"}, headers=KEY).json()
    assert payload["flags"] == ["toxicity"]


def test_moderation_sends_bearer_token_and_model_url(client, hf):
    hf.respond_with([{"label": "toxic", "score": 0.1}])
    client.post("/moderate", json={"text": "x"}, headers=KEY)
    settings = get_settings()
    assert hf.last["headers"]["Authorization"] == "Bearer hf_test_token"
    assert hf.last["url"].endswith(settings.hf_moderation_model)
    assert hf.last["payload"]["options"] == {"wait_for_model": True}


def test_moderation_rejects_unexpected_payload(client, hf):
    hf.respond_with({"error": "Model is loading"})
    payload = client.post("/moderate", json={"text": "x"}, headers=KEY).json()
    # ProviderError -> heuristic fallback (allow_heuristic_fallback defaults on).
    assert payload["degraded"] is True
    assert payload["provider"] == "heuristic"


def test_captions_parses_json_array(client, hf):
    hf.respond_with(
        [{"generated_text": '["Sunlit and simple.", "Golden hour mood.", "Just vibes."]'}]
    )
    payload = client.post(
        "/caption", json={"idea": "sunset", "count": 3}, headers=KEY
    ).json()
    assert payload["provider"] == "huggingface"
    assert len(payload["suggestions"]) == 3
    assert payload["suggestions"][0] == "Sunlit and simple."


def test_captions_falls_back_to_line_splitting(client, hf):
    hf.respond_with([{"generated_text": "- one\n- two\n- three\n"}])
    payload = client.post("/caption", json={"idea": "chai", "count": 2}, headers=KEY).json()
    assert payload["suggestions"] == ["one", "two"]  # truncated to requested count


def test_captions_empty_response_degrades(client, hf):
    hf.respond_with([{"generated_text": ""}])
    payload = client.post("/caption", json={"idea": "chai", "count": 2}, headers=KEY).json()
    assert payload["degraded"] is True  # ProviderError -> heuristic fallback
    assert len(payload["suggestions"]) >= 1


def test_mood_parses_json_object(client, hf):
    hf.respond_with(
        [{"generated_text": 'noise {"mood_signal": "negative", "suggestion": "Be kind to yourself."} noise'}]
    )
    payload = client.post(
        "/mood-check", json={"texts": ["bad day", "worse day", "awful"]}, headers=KEY
    ).json()
    assert payload["mood_signal"] == "negative"
    assert payload["suggestion"] == "Be kind to yourself."


def test_mood_invalid_signal_is_normalised_to_neutral(client, hf):
    hf.respond_with([{"generated_text": '{"mood_signal": "catastrophic", "suggestion": "x"}'}])
    payload = client.post("/mood-check", json={"texts": ["a", "b", "c"]}, headers=KEY).json()
    assert payload["mood_signal"] == "neutral"


def test_mood_unparseable_text_is_neutral_not_crash(client, hf):
    hf.respond_with([{"generated_text": "I cannot help with that."}])
    payload = client.post("/mood-check", json={"texts": ["a", "b", "c"]}, headers=KEY).json()
    assert payload["mood_signal"] == "neutral"
    assert payload["provider"] == "huggingface"  # not an error, just a conservative default


def test_provider_without_token_raises(client, monkeypatch):
    monkeypatch.setenv("PROVIDER", "huggingface")
    monkeypatch.delenv("HF_API_TOKEN", raising=False)
    get_settings.cache_clear()
    reset_provider_cache()
    with pytest.raises(ProviderError, match="HF_API_TOKEN"):
        HuggingFaceProvider()
    get_settings.cache_clear()
    reset_provider_cache()


def test_unconfigured_hf_degrades_to_heuristic(client, monkeypatch):
    """A missing token must degrade, not take the endpoint down."""
    monkeypatch.setenv("PROVIDER", "huggingface")
    monkeypatch.delenv("HF_API_TOKEN", raising=False)
    get_settings.cache_clear()
    reset_provider_cache()
    payload = client.post("/moderate", json={"text": "you idiot and a loser"}, headers=KEY).json()
    assert payload["degraded"] is True
    assert payload["provider"] == "heuristic"
    assert payload["is_safe"] is False
    get_settings.cache_clear()
    reset_provider_cache()


def test_extract_json_helpers():
    assert _extract_json_list('["a", "b"]') == ["a", "b"]
    assert _extract_json_list("prefix [\"a\"] suffix") == ["a"]
    assert _extract_json_list("no json here") == []
    assert _extract_json_list("[broken") == []
    assert _extract_json_object('{"a": 1}') == {"a": 1}
    assert _extract_json_object("text {\"a\": 1} text") == {"a": 1}
    assert _extract_json_object("nope") == {}
    assert _extract_json_object("{bad json}") == {}
