from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework import status

from notifications.models import Notification
from notifications.services import mark_all_read, notify, unread_count
from posts.models import Post


@pytest.mark.django_db
class TestNotificationService:
    def test_notify_creates_row(self, user, other_user):
        notification = notify(
            recipient=user, actor=other_user, notification_type="like", message="bob liked your post."
        )
        assert notification.pk is not None
        assert unread_count(user) == 1

    def test_notify_skips_self_notifications(self, user):
        assert notify(recipient=user, actor=user, notification_type="like", message="self") is None

    def test_mark_all_read(self, user, other_user):
        for i in range(3):
            notify(recipient=user, actor=other_user, notification_type="like", message=f"m{i}")
        assert mark_all_read(user) == 3
        assert unread_count(user) == 0

    def test_anonymous_unread_count_is_zero(self):
        from django.contrib.auth.models import AnonymousUser

        assert unread_count(AnonymousUser()) == 0


@pytest.mark.django_db
class TestNotificationAPI:
    def test_unread_count_endpoint(self, auth_client, user, other_user):
        notify(recipient=user, actor=other_user, notification_type="follow", message="bob follows you")
        response = auth_client.get(reverse("api:notifications:unread-count"))
        assert response.data == {"unread_count": 1}

    def test_list_and_filter_unread(self, auth_client, user, other_user):
        notify(recipient=user, actor=other_user, notification_type="follow", message="one")
        read_one = notify(recipient=user, actor=other_user, notification_type="like", message="two")
        read_one.mark_read()

        all_items = auth_client.get(reverse("api:notifications:list"))
        assert all_items.data["count"] == 2

        unread = auth_client.get(reverse("api:notifications:list"), {"unread": "1"})
        assert unread.data["count"] == 1

    def test_mark_single_read(self, auth_client, user, other_user):
        notification = notify(recipient=user, actor=other_user, notification_type="like", message="x")
        response = auth_client.post(reverse("api:notifications:read", args=[notification.id]))
        assert response.status_code == status.HTTP_200_OK
        assert response.data["is_read"] is True

    def test_cannot_read_someone_elses_notification(self, auth_client, user_factory, other_user):
        someone_else = user_factory(username="carol")
        notification = notify(recipient=someone_else, actor=other_user, notification_type="like", message="x")
        response = auth_client.post(reverse("api:notifications:read", args=[notification.id]))
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_mark_all_read_endpoint(self, auth_client, user, other_user):
        notify(recipient=user, actor=other_user, notification_type="like", message="x")
        response = auth_client.post(reverse("api:notifications:read-all"))
        assert response.data == {"updated": 1}
        assert Notification.objects.filter(recipient=user, is_read=True).count() == 1

    def test_like_creates_notification_with_link_to_post(self, auth_client, other_user):
        post = Post.objects.create(author=other_user, content="hi", moderation_status=Post.ModerationStatus.APPROVED)
        auth_client.post(reverse("api:social:like-toggle", args=[post.id]))
        notification = other_user.notifications.first()
        assert notification.notification_type == "like"
        assert notification.link == post.get_absolute_url()

    def test_endpoints_require_auth(self, api_client):
        assert api_client.get(reverse("api:notifications:list")).status_code == status.HTTP_401_UNAUTHORIZED
        assert api_client.get(reverse("api:notifications:unread-count")).status_code == status.HTTP_401_UNAUTHORIZED
