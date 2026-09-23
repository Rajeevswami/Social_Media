"""Likes, comments and the follow graph."""
from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework import status

from posts.models import Post
from social.models import Comment, Follow, Like


@pytest.fixture
def post(db, other_user):
    return Post.objects.create(
        author=other_user, content="a post", moderation_status=Post.ModerationStatus.APPROVED
    )


@pytest.mark.django_db
class TestLikes:
    def test_like_is_idempotent_toggle(self, auth_client, post, user):
        url = reverse("api:social:like-toggle", args=[post.id])

        first = auth_client.post(url)
        assert first.status_code == status.HTTP_200_OK
        assert first.data == {"is_liked": True, "like_count": 1, "post_id": post.id}
        assert Like.objects.filter(user=user, post=post).exists()

        second = auth_client.post(url)
        assert second.data["is_liked"] is False
        assert second.data["like_count"] == 0
        assert not Like.objects.filter(user=user, post=post).exists()

    def test_like_requires_auth(self, api_client, post):
        assert api_client.post(reverse("api:social:like-toggle", args=[post.id])).status_code == status.HTTP_401_UNAUTHORIZED

    def test_liking_own_post_does_not_notify(self, auth_client, user):
        own = Post.objects.create(author=user, content="self", moderation_status=Post.ModerationStatus.APPROVED)
        auth_client.post(reverse("api:social:like-toggle", args=[own.id]))
        assert user.notifications.count() == 0


@pytest.mark.django_db
class TestComments:
    def test_create_and_list_comments(self, auth_client, post):
        url = reverse("api:social:comments", args=[post.id])
        created = auth_client.post(url, {"content": "  nice shot! "}, format="json")
        assert created.status_code == status.HTTP_201_CREATED, created.data
        assert created.data["content"] == "nice shot!"  # trimmed
        assert created.data["author"]["username"] == "alice"

        listed = auth_client.get(url)
        assert listed.data["count"] == 1

    def test_empty_comment_rejected(self, auth_client, post):
        response = auth_client.post(
            reverse("api:social:comments", args=[post.id]), {"content": "   "}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert Comment.objects.count() == 0

    def test_author_or_post_owner_can_delete(self, auth_client, user, post):
        comment = Comment.objects.create(post=post, author=user, content="mine")
        url = reverse("api:social:comment-detail", args=[comment.id])
        assert auth_client.delete(url).status_code == status.HTTP_204_NO_CONTENT
        assert not Comment.objects.filter(pk=comment.id).exists()

    def test_stranger_cannot_delete(self, auth_client, user_factory, post):
        stranger = user_factory(username="mallory")
        comment = Comment.objects.create(post=post, author=stranger, content="theirs")
        response = auth_client.delete(reverse("api:social:comment-detail", args=[comment.id]))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_comment_notifies_post_author(self, auth_client, post, other_user):
        auth_client.post(reverse("api:social:comments", args=[post.id]), {"content": "hello"}, format="json")
        assert other_user.notifications.filter(notification_type="comment").exists()


@pytest.mark.django_db
class TestFollow:
    def test_follow_then_unfollow(self, auth_client, other_user):
        url = reverse("api:social:follow-toggle", args=[other_user.username])

        first = auth_client.post(url)
        assert first.data["status"] == "following"
        assert first.data["followers_count"] == 1

        second = auth_client.post(url)
        assert second.data["status"] == "not_following"
        assert Follow.objects.count() == 0

    def test_self_follow_rejected(self, auth_client, user):
        response = auth_client.post(reverse("api:social:follow-toggle", args=[user.username]))
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_private_account_creates_pending_request(self, auth_client, user_factory):
        private_user = user_factory(username="private_pete", is_private=True)
        response = auth_client.post(reverse("api:social:follow-toggle", args=[private_user.username]))
        assert response.data["status"] == "requested"
        edge = Follow.objects.get(followee=private_user)
        assert edge.is_active is False
        assert private_user.followers_count == 0

    def test_accepting_request_activates_follow_and_notifies(self, auth_client, user, user_factory):
        requester = user_factory(username="requester")
        target = user_factory(username="target", is_private=True)
        Follow.objects.create(follower=requester, followee=target, is_active=False)

        auth_client.force_authenticate(user=target)
        response = auth_client.post(
            reverse("api:social:follow-request-decision", args=[requester.id, "accept"])
        )
        assert response.status_code == status.HTTP_200_OK
        Follow.objects.get(follower=requester, followee=target).refresh_from_db()
        assert Follow.objects.get(follower=requester, followee=target).is_active is True
        assert requester.notifications.filter(notification_type="follow").exists()

    def test_rejecting_request_deletes_it(self, auth_client, user, user_factory):
        requester = user_factory(username="requester2")
        Follow.objects.create(follower=requester, followee=user, is_active=False)
        auth_client.post(reverse("api:social:follow-request-decision", args=[requester.id, "reject"]))
        assert Follow.objects.count() == 0

    def test_invalid_decision_rejected(self, auth_client, user_factory):
        someone = user_factory(username="someone")
        response = auth_client.post(
            reverse("api:social:follow-request-decision", args=[someone.id, "maybe"])
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_followers_and_following_lists(self, auth_client, user, other_user):
        Follow.objects.create(follower=other_user, followee=user, is_active=True)
        followers = auth_client.get(reverse("api:social:followers", args=[user.username]))
        assert followers.data["count"] == 1
        assert followers.data["results"][0]["follower"]["username"] == other_user.username

        following = auth_client.get(reverse("api:social:following", args=[other_user.username]))
        assert following.data["count"] == 1
