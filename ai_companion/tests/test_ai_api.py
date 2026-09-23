"""AI companion endpoints: caption, moderation preview, mood summary, nudges."""
from __future__ import annotations

from unittest import mock

import httpx
import pytest
from django.core.cache import cache
from django.urls import reverse
from rest_framework import status

from ai_companion.client import AIServiceClient
from ai_companion.models import MoodCheck, WellbeingNudge
from posts.models import Post


@pytest.mark.django_db
class TestCaptionEndpoint:
    def test_returns_three_suggestions(self, auth_client, mock_ai_client, ai_calls):
        response = auth_client.post(reverse("api:ai_companion:caption"), {"idea": "monsoon chai"}, format="json")
        assert response.status_code == status.HTTP_200_OK, response.data
        assert len(response.data["suggestions"]) == 3
        assert all("monsoon chai" in s for s in response.data["suggestions"])
        assert response.data["provider"] == "mock"
        assert ai_calls[0].url.path == "/caption"

    def test_rejects_too_short_idea(self, auth_client):
        response = auth_client.post(reverse("api:ai_companion:caption"), {"idea": "x"}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_caps_count_at_three(self, auth_client):
        response = auth_client.post(
            reverse("api:ai_companion:caption"), {"idea": "sunset", "count": 9}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_service_429_is_surfaced_as_429(self, auth_client):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, json={"detail": "quota exhausted"})

        client = AIServiceClient(transport=httpx.MockTransport(handler), retries=0, timeout=1.0)
        with mock.patch("ai_companion.api_views.get_client", return_value=client):
            response = auth_client.post(reverse("api:ai_companion:caption"), {"idea": "sunset"}, format="json")

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert response.data["code"] == "ai_rate_limited"

    def test_service_outage_returns_503_not_a_crash(self, auth_client):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("down", request=request)

        client = AIServiceClient(transport=httpx.MockTransport(handler), retries=0, timeout=1.0)
        with mock.patch("ai_companion.api_views.get_client", return_value=client):
            response = auth_client.post(reverse("api:ai_companion:caption"), {"idea": "sunset"}, format="json")

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert "unavailable" in response.data["detail"].lower()

    def test_requires_authentication(self, api_client):
        assert api_client.post(reverse("api:ai_companion:caption"), {"idea": "x"}, format="json").status_code == (
            status.HTTP_401_UNAUTHORIZED
        )

    def test_ai_throttle_limits_calls_per_user(self, auth_client, mock_ai_client):
        """The Django-side budget protects the model-provider bill.

        DRF binds THROTTLE_RATES onto the throttle class at import time, so the
        rate is patched on the class instead of via override_settings.
        """
        from common.throttles import AIRateThrottle

        url = reverse("api:ai_companion:caption")
        cache.clear()
        with mock.patch.object(AIRateThrottle, "rate", "2/hour", create=True):
            first = auth_client.post(url, {"idea": "sunset"}, format="json")
            second = auth_client.post(url, {"idea": "sunrise"}, format="json")
            third = auth_client.post(url, {"idea": "moon"}, format="json")
        cache.clear()

        assert first.status_code == status.HTTP_200_OK
        assert second.status_code == status.HTTP_200_OK
        assert third.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert third.data["code"] == "throttled"


@pytest.mark.django_db
class TestModerationPreview:
    def test_preview_does_not_create_a_post(self, auth_client, mock_ai_client):
        response = auth_client.post(
            reverse("api:ai_companion:moderate"), {"text": "I hate you"}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["is_safe"] is False
        assert response.data["flags"] == ["toxicity"]
        assert Post.objects.count() == 0


@pytest.mark.django_db
class TestMoodSummary:
    def test_returns_only_own_history(self, auth_client, user, other_user):
        MoodCheck.objects.create(user=user, signal="negative", posts_analyzed=5)
        MoodCheck.objects.create(user=other_user, signal="positive", posts_analyzed=5)

        response = auth_client.get(reverse("api:ai_companion:mood"))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["checks"]) == 1
        assert response.data["latest"]["signal"] == "negative"
        assert "not a diagnosis" in response.data["disclaimer"].lower()


@pytest.mark.django_db
class TestNudgeEndpoints:
    def test_no_active_nudge_by_default(self, auth_client):
        response = auth_client.get(reverse("api:ai_companion:nudge"))
        assert response.data == {"nudge": None}

    def test_active_nudge_and_dismiss(self, auth_client, user):
        nudge = WellbeingNudge.objects.create(user=user, message="Kaise ho?")
        active = auth_client.get(reverse("api:ai_companion:nudge"))
        assert active.data["nudge"]["id"] == nudge.id
        assert active.data["nudge"]["is_active"] is True

        dismissed = auth_client.post(reverse("api:ai_companion:nudge-dismiss", args=[nudge.id]))
        assert dismissed.status_code == status.HTTP_200_OK
        nudge.refresh_from_db()
        assert nudge.dismissed_at is not None
        assert auth_client.get(reverse("api:ai_companion:nudge")).data["nudge"] is None

    def test_cannot_dismiss_another_users_nudge(self, auth_client, user_factory):
        other = user_factory(username="other_nudged")
        nudge = WellbeingNudge.objects.create(user=other, message="x")
        response = auth_client.post(reverse("api:ai_companion:nudge-dismiss", args=[nudge.id]))
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_nudge_appears_in_ui_context(self, client, user):

        WellbeingNudge.objects.create(user=user, message="Kaise ho?")
        client.force_login(user)
        response = client.get(reverse("posts:feed"))
        assert response.status_code == status.HTTP_200_OK
        assert "Kaise ho?" in response.content.decode()
