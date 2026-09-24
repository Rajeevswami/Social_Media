"""The moderation state machine, including AI-service outage behaviour."""
from __future__ import annotations

import json
from unittest import mock

import httpx
import pytest
from django.test import override_settings

from ai_companion.client import AIServiceClient
from posts.models import Post
from posts.services import create_post


def _client(handler, retries=0):
    return AIServiceClient(transport=httpx.MockTransport(handler), retries=retries, timeout=1.0)


@pytest.mark.django_db
class TestModerationVerdicts:
    def test_safe_post_is_approved(self, user, mock_ai_client):
        post = create_post(author=user, content="Had a great day at the beach")
        post.refresh_from_db()
        assert post.moderation_status == Post.ModerationStatus.APPROVED
        assert post.moderation_flags == []

    def test_unsafe_post_is_flagged_with_reason(self, user, mock_ai_client):
        post = create_post(author=user, content="I hate you all so much")
        post.refresh_from_db()
        assert post.moderation_status == Post.ModerationStatus.FLAGGED
        assert post.moderation_flags == ["toxicity"]
        assert "toxicity" in post.moderation_reason.lower()
        # Never silently blocked: the author still sees it and why.
        assert post.is_published is True

    @override_settings(MODERATION_POLICY="hold_unsafe")
    def test_hold_policy_holds_unsafe_post(self, user, mock_ai_client):
        post = create_post(author=user, content="I hate you all so much")
        post.refresh_from_db()
        assert post.moderation_status == Post.ModerationStatus.HELD
        assert post.is_published is False
        assert post.visible_to(user) is True  # author can still see + edit it

    def test_author_gets_a_moderation_notification_when_flagged(self, user, mock_ai_client):
        post = create_post(author=user, content="I hate you all so much")
        notification = user.notifications.filter(notification_type="moderation").first()
        assert notification is not None
        assert str(post.id) in notification.link
        assert "flagged" in notification.message.lower()

    def test_image_only_post_skips_moderation_call(self, user, ai_calls, mock_ai_client):
        from io import BytesIO

        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image

        buffer = BytesIO()
        Image.new("RGB", (10, 10), "red").save(buffer, format="PNG")
        image = SimpleUploadedFile("t.png", buffer.getvalue(), content_type="image/png")

        post = create_post(author=user, content="", image=image)
        post.refresh_from_db()
        assert post.moderation_status == Post.ModerationStatus.APPROVED
        assert not [c for c in ai_calls if c.url.path == "/moderate"]


@pytest.mark.django_db
class TestModerationOutage:
    def test_fail_open_publishes_but_keeps_flag_and_reason(self, user):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, json={"detail": "provider down"})

        client = _client(handler)
        with mock.patch("ai_companion.tasks.get_client", return_value=client):
            post = create_post(author=user, content="hello there")

        post.refresh_from_db()
        assert post.moderation_status == Post.ModerationStatus.FLAGGED
        assert "could not run" in post.moderation_reason
        assert post.is_published is True

    @override_settings(MODERATION_FAILURE_POLICY="fail_closed")
    def test_fail_closed_holds_the_post(self, user):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, json={"detail": "provider down"})

        client = _client(handler)
        with mock.patch("ai_companion.tasks.get_client", return_value=client):
            post = create_post(author=user, content="hello there")

        post.refresh_from_db()
        assert post.moderation_status == Post.ModerationStatus.HELD
        assert post.is_published is False

    def test_timeout_is_treated_as_an_outage(self, user):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("slow provider", request=request)

        client = _client(handler)
        with mock.patch("ai_companion.tasks.get_client", return_value=client):
            post = create_post(author=user, content="hello there")

        post.refresh_from_db()
        assert post.moderation_status == Post.ModerationStatus.FLAGGED

    def test_invalid_json_from_service_is_an_error_not_a_crash(self, user):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="<html>not json</html>", headers={"content-type": "text/html"})

        client = _client(handler)
        with mock.patch("ai_companion.tasks.get_client", return_value=client):
            post = create_post(author=user, content="hello there")

        post.refresh_from_db()
        assert post.moderation_status == Post.ModerationStatus.FLAGGED
        assert json.loads(json.dumps(post.moderation_flags)) == ["safety_check_unavailable"]
