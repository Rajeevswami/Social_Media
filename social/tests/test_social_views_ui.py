"""UI-level checks for the social graph pages."""
from __future__ import annotations

import pytest
from django.urls import reverse

from posts.models import Post
from social.models import Comment, Follow


@pytest.mark.django_db
class TestConnectionListPrivacy:
    def test_private_graph_page_is_404_for_strangers(self, client, user, user_factory):
        priv = user_factory("priv_user", is_private=True)
        Follow.objects.create(follower=user_factory("secret_follower"), followee=priv, is_active=True)
        client.force_login(user)
        for kind in ("followers", "following"):
            response = client.get(reverse("social:connections", args=[priv.username, kind]))
            assert response.status_code == 404, kind
            assert b"secret_follower" not in response.content

    def test_private_graph_page_visible_to_approved_follower(self, client, user, user_factory):
        priv = user_factory("priv_user", is_private=True)
        Follow.objects.create(follower=user, followee=priv, is_active=True)
        client.force_login(user)
        assert client.get(reverse("social:connections", args=[priv.username, "followers"])).status_code == 200

    def test_public_graph_page_visible(self, client, user, user_factory):
        public = user_factory("public_user", is_private=False)
        Follow.objects.create(follower=user_factory("someone"), followee=public, is_active=True)
        client.force_login(user)
        response = client.get(reverse("social:connections", args=[public.username, "followers"]))
        assert response.status_code == 200
        assert b"someone" in response.content


@pytest.mark.django_db
class TestCommentDeleteUI:
    def test_post_author_can_delete_others_comment(self, client, user, user_factory):
        post = Post.objects.create(author=user, content="my post", moderation_status="approved")
        other = user_factory("commenter")
        comment = Comment.objects.create(post=post, author=other, content="hi")
        client.force_login(user)
        assert client.post(reverse("social:comment_delete_ui", args=[comment.pk])).status_code == 302
        assert not Comment.objects.filter(pk=comment.pk).exists()

    def test_unrelated_user_cannot_delete(self, client, user_factory):
        """Refused with a redirect + flash message (not 403); comment survives.

        The security property that matters is that the row is untouched and the
        error is surfaced to the person who tried.
        """
        post = Post.objects.create(author=user_factory("poster"), content="post", moderation_status="approved")
        comment = Comment.objects.create(post=post, author=user_factory("commenter"), content="hi")
        client.force_login(user_factory("outsider"))
        response = client.post(reverse("social:comment_delete_ui", args=[comment.pk]), follow=True)
        assert Comment.objects.filter(pk=comment.pk).exists()
        assert b"You cannot delete that comment." in response.content

    def test_anonymous_user_cannot_delete(self, client, user_factory):
        post = Post.objects.create(author=user_factory("poster"), content="post", moderation_status="approved")
        comment = Comment.objects.create(post=post, author=user_factory("commenter"), content="hi")
        response = client.post(reverse("social:comment_delete_ui", args=[comment.pk]))
        assert Comment.objects.filter(pk=comment.pk).exists()
        assert response.status_code in (302, 403)

    def test_staff_can_delete(self, client, user_factory):
        post = Post.objects.create(author=user_factory("poster"), content="post", moderation_status="approved")
        comment = Comment.objects.create(post=post, author=user_factory("commenter"), content="hi")
        client.force_login(user_factory("moderator", is_staff=True))
        assert client.post(reverse("social:comment_delete_ui", args=[comment.pk])).status_code == 302
        assert not Comment.objects.filter(pk=comment.pk).exists()
