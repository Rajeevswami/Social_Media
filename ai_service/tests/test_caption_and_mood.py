"""POST /caption and POST /mood-check."""
from __future__ import annotations

import pytest


@pytest.mark.parametrize("count", [1, 2, 3])
def test_caption_returns_requested_number(client, auth_headers, count):
    payload = client.post(
        "/caption", json={"idea": "monsoon chai", "count": count}, headers=auth_headers
    ).json()
    assert len(payload["suggestions"]) == count
    assert all("monsoon chai" in suggestion for suggestion in payload["suggestions"])
    assert payload["provider"] == "heuristic"


def test_caption_tone_changes_output(client, auth_headers):
    casual = client.post("/caption", json={"idea": "gym day", "tone": "casual"}, headers=auth_headers).json()
    witty = client.post("/caption", json={"idea": "gym day", "tone": "witty"}, headers=auth_headers).json()
    assert casual["suggestions"] != witty["suggestions"]


def test_caption_rejects_bad_tone_and_count(client, auth_headers):
    responses = [
        client.post("/caption", json={"idea": "sunsets", "tone": "angry"}, headers=auth_headers),
        client.post("/caption", json={"idea": "sunsets", "count": 9}, headers=auth_headers),
        client.post("/caption", json={"idea": "x"}, headers=auth_headers),  # idea too short
    ]
    assert [response.status_code for response in responses] == [422, 422, 422]


def test_mood_negative_batch(client, auth_headers):
    texts = ["so tired today", "feeling hopeless", "nothing works", "another lonely night"]
    payload = client.post("/mood-check", json={"texts": texts, "user_id": 7}, headers=auth_headers).json()
    assert payload["mood_signal"] == "negative"
    assert payload["posts_analyzed"] == 4
    assert payload["negative_ratio"] > payload["positive_ratio"]
    assert payload["suggestion"]
    assert "not a diagnosis" in payload["disclaimer"].lower()


def test_mood_positive_batch(client, auth_headers):
    texts = ["feeling grateful", "great progress today", "so happy", "amazing week"]
    payload = client.post("/mood-check", json={"texts": texts}, headers=auth_headers).json()
    assert payload["mood_signal"] == "positive"


def test_mood_mixed_batch_is_neutral(client, auth_headers):
    texts = ["great progress today", "so tired", "grateful for friends", "feeling hopeless"]
    payload = client.post("/mood-check", json={"texts": texts}, headers=auth_headers).json()
    assert payload["mood_signal"] == "neutral"


@pytest.mark.parametrize("texts", [[], [""], ["   "], ["", "  "]])
def test_mood_requires_non_empty_texts(client, auth_headers, texts):
    response = client.post("/mood-check", json={"texts": texts}, headers=auth_headers)
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_mood_endpoints_require_auth(client):
    assert client.post("/mood-check", json={"texts": ["hi"]}).status_code == 401
    assert client.post("/caption", json={"idea": "sunset"}).status_code == 401
