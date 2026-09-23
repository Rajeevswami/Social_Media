from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError

from accounts.models import User


@pytest.mark.django_db
class TestUserModel:
    def test_create_user_normalises_email_and_hashes_password(self):
        user = User.objects.create_user(username="carol", email="CAROL@Example.COM", password="pw-12345678")
        # Django's normalize_email lower-cases the domain part only.
        assert user.email == "CAROL@example.com"
        assert user.password != "pw-12345678"
        assert user.is_staff is False

    def test_email_is_required(self):
        with pytest.raises(ValueError):
            User.objects.create_user(username="noemail", email="", password="pw-12345678")

    def test_invalid_email_fails_validation(self):
        user = User(username="bad", email="not-an-email")
        with pytest.raises(ValidationError):
            user.full_clean()

    def test_create_superuser_flags(self):
        admin = User.objects.create_superuser(username="root", email="root@example.com", password="pw-12345678")
        assert admin.is_staff and admin.is_superuser

    def test_profile_name_falls_back_to_username(self):
        user = User(username="dave", email="dave@example.com")
        assert user.profile_name == "dave"
        user.display_name = "Dave D"
        assert user.profile_name == "Dave D"
        assert user.initials == "D"


@pytest.mark.django_db
class TestFollowHelpers:
    def test_is_followed_by_respects_pending_requests(self, user, other_user):
        from social.models import Follow

        assert user.is_followed_by(other_user) is False
        Follow.objects.create(follower=other_user, followee=user, is_active=False)
        assert user.is_followed_by(other_user) is False  # pending request is not a follow
        Follow.objects.filter(follower=other_user).update(is_active=True)
        assert user.is_followed_by(other_user) is True
        assert user.followers_count == 1
        assert other_user.following_count == 1

    def test_anonymous_is_never_following(self, user):
        from django.contrib.auth.models import AnonymousUser

        assert user.is_followed_by(AnonymousUser()) is False
