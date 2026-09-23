"""Post CRUD + feed visibility."""
from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework import status

from posts.models import Post


@pytest.mark.django_db
class TestCreatePost:
    def test_create_text_post_is_moderated(self, auth_client, mock_ai_client):
        response = auth_client.post(reverse("api:posts:post-list"), {"content": "hello world"}, format="json")
        assert response.status_code == status.HTTP_201_CREATED, response.data
        post = Post.objects.get(pk=response.data["id"])
        # Eager Celery in tests: the moderation task ran inline.
        assert post.moderation_status == Post.ModerationStatus.APPROVED
        assert post.moderation_provider == "mock"
        assert post.moderation_checked_at is not None

    def test_create_requires_content_or_image(self, auth_client):
        response = auth_client.post(reverse("api:posts:post-list"), {"content": "   "}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert Post.objects.count() == 0

    def test_create_requires_authentication(self, api_client):
        response = api_client.post(reverse("api:posts:post-list"), {"content": "anon"}, format="json")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_enforces_max_length(self, auth_client):
        response = auth_client.post(
            reverse("api:posts:post-list"), {"content": "x" * (Post.MAX_CONTENT_LENGTH + 1)}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestFeed:
    def test_feed_shows_own_and_followed_posts(self, auth_client, user, other_user, mock_ai_client):
        from social.models import Follow

        mine = Post.objects.create(author=user, content="mine", moderation_status=Post.ModerationStatus.APPROVED)
        theirs = Post.objects.create(author=other_user, content="theirs", moderation_status=Post.ModerationStatus.APPROVED)
        stranger = Post.objects.create(
            author=other_user, content="hidden from feed", moderation_status=Post.ModerationStatus.APPROVED
        )
        Follow.objects.create(follower=user, followee=other_user, is_active=True)

        response = auth_client.get(reverse("api:posts:feed"))
        ids = {row["id"] for row in response.data["results"]}
        assert {mine.id, theirs.id} <= ids
        assert stranger.id in ids  # following sees all their posts
        assert response.data["results"][0]["author"]["username"] in (user.username, other_user.username)

    def test_feed_excludes_held_posts(self, auth_client, user):
        held = Post.objects.create(
            author=user, content="held back", moderation_status=Post.ModerationStatus.HELD,
            moderation_reason="pending review",
        )
        response = auth_client.get(reverse("api:posts:feed"))
        assert held.id not in {row["id"] for row in response.data["results"]}

    def test_feed_requires_auth(self, api_client):
        assert api_client.get(reverse("api:posts:feed")).status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestPrivacy:
    def test_private_posts_hidden_from_explore_and_others(self, api_client, user_factory):
        private_user = user_factory(username="private_pete", is_private=True)
        secret = Post.objects.create(
            author=private_user, content="secret", moderation_status=Post.ModerationStatus.APPROVED
        )
        explore = api_client.get(reverse("api:posts:post-list"))
        assert secret.id not in {row["id"] for row in explore.data["results"]}

        detail = api_client.get(reverse("api:posts:post-detail", args=[secret.id]))
        assert detail.status_code == status.HTTP_404_NOT_FOUND

    def test_follower_can_see_private_post(self, auth_client, user, user_factory):
        from social.models import Follow

        private_user = user_factory(username="private_pete", is_private=True)
        secret = Post.objects.create(
            author=private_user, content="for followers", moderation_status=Post.ModerationStatus.APPROVED
        )
        Follow.objects.create(follower=user, followee=private_user, is_active=True)
        assert auth_client.get(reverse("api:posts:post-detail", args=[secret.id])).status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestEditAndDelete:
    def test_edit_re_triggers_moderation(self, auth_client, user, mock_ai_client):
        post = Post.objects.create(
            author=user, content="original", moderation_status=Post.ModerationStatus.APPROVED
        )
        response = auth_client.patch(
            reverse("api:posts:post-detail", args=[post.id]), {"content": "edited text"}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        post.refresh_from_db()
        assert post.content == "edited text"
        assert post.edited_at is not None
        assert post.moderation_status == Post.ModerationStatus.APPROVED  # re-checked inline

    def test_only_owner_can_edit(self, auth_client, other_user, mock_ai_client):
        post = Post.objects.create(
            author=other_user, content="not yours", moderation_status=Post.ModerationStatus.APPROVED
        )
        response = auth_client.patch(
            reverse("api:posts:post-detail", args=[post.id]), {"content": "pwned"}, format="json"
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_is_soft_and_hides_from_feed(self, auth_client, user, mock_ai_client):
        post = Post.objects.create(author=user, content="bye", moderation_status=Post.ModerationStatus.APPROVED)
        response = auth_client.delete(reverse("api:posts:post-detail", args=[post.id]))
        assert response.status_code == status.HTTP_200_OK
        post.refresh_from_db()
        assert post.is_hidden is True
        assert Post.objects.filter(pk=post.id).exists()  # row kept for audit
        feed = auth_client.get(reverse("api:posts:feed"))
        assert post.id not in {row["id"] for row in feed.data["results"]}

    def test_moderation_endpoint_is_owner_only(self, auth_client, user, other_user):
        post = Post.objects.create(author=user, content="mine", moderation_status=Post.ModerationStatus.FLAGGED)
        assert auth_client.get(reverse("api:posts:post-moderation", args=[post.id])).status_code == status.HTTP_200_OK

        other_post = Post.objects.create(author=other_user, content="theirs", moderation_status=Post.ModerationStatus.FLAGGED)
        assert auth_client.get(reverse("api:posts:post-moderation", args=[other_post.id])).status_code == status.HTTP_403_FORBIDDEN

    def test_moderation_reason_hidden_from_others(self, auth_client, user_factory):
        author = user_factory(username="author_a")
        post = Post.objects.create(
            author=author, content="x", moderation_status=Post.ModerationStatus.FLAGGED,
            moderation_reason="toxicity detected",
        )
        response = auth_client.get(reverse("api:posts:post-detail", args=[post.id]))
        assert response.data["moderation_status"] == "flagged"
        assert response.data["moderation_reason"] == ""  # not leaked to non-owners
