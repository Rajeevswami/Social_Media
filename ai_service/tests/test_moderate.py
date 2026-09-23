"""POST /moderate — behaviour, validation and auth."""
from __future__ import annotations

import pytest


@pytest.mark.parametrize(
    "text,expect_safe",
    [
        ("Had a great weekend hiking with friends", True),
        ("Shipping the new release today, feeling good", True),
        ("You are such an idiot and a loser", False),
        ("i hate you so much", False),
    ],
)
def test_moderation_verdicts(client, auth_headers, text, expect_safe):
    response = client.post("/moderate", json={"text": text}, headers=auth_headers)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["is_safe"] is expect_safe
    assert payload["provider"] == "heuristic"
    assert 0.0 <= payload["confidence"] <= 1.0
    assert payload["reason"]
    if not expect_safe:
        assert payload["flags"], "an unsafe verdict must carry at least one flag"


def test_spam_is_flagged(client, auth_headers):
    text = "FREE CASH PRIZE click the link now http://a.example http://b.example http://c.example"
    payload = client.post("/moderate", json={"text": text}, headers=auth_headers).json()
    assert "spam" in payload["flags"]
    assert payload["is_safe"] is False


def test_scores_are_per_category(client, auth_headers):
    payload = client.post(
        "/moderate", json={"text": "you idiot", "post_id": 42}, headers=auth_headers
    ).json()
    categories = {row["category"] for row in payload["scores"]}
    assert {"toxicity", "hate", "spam"} <= categories
    assert all(0.0 <= row["score"] <= 1.0 for row in payload["scores"])
    assert payload["post_id"] == 42


def test_missing_api_key_is_unauthorized(client):
    response = client.post("/moderate", json={"text": "hello"})
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "ApiKey"


def test_wrong_api_key_is_unauthorized(client):
    response = client.post("/moderate", json={"text": "hello"}, headers={"X-API-Key": "nope"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid API key."


@pytest.mark.parametrize(
    "body,expected_error_field",
    [
        ({}, "text"),
        ({"text": ""}, "text"),
        ({"text": "   "}, "text"),
        ({"text": "hi", "unknown": 1}, "unknown"),
        ({"text": "hi", "post_id": 0}, "post_id"),
    ],
)
def test_payload_validation(client, auth_headers, body, expected_error_field):
    response = client.post("/moderate", json=body, headers=auth_headers)
    assert response.status_code == 422, response.text
    payload = response.json()
    assert payload["code"] == "validation_error"
    assert any(expected_error_field in str(error.get("loc", "")) for error in payload["errors"])
