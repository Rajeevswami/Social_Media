"""JWT auth flows: register, login, refresh, logout, profile."""
from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework import status

from accounts.models import User

PASSWORD = "Str0ngPass!234"


@pytest.mark.django_db
class TestRegister:
    def test_register_returns_tokens_and_user(self, api_client):
        response = api_client.post(
            reverse("api:accounts:register"),
            {
                "username": "newbie",
                "email": "Newbie@Example.com",
                "password": PASSWORD,
                "password_confirm": PASSWORD,
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED, response.data
        assert response.data["access"]
        assert response.data["refresh"]
        assert response.data["user"]["username"] == "newbie"
        user = User.objects.get(username="newbie")
        assert user.email == "newbie@example.com"  # normalised to lower case
        assert user.check_password(PASSWORD)

    def test_register_rejects_mismatched_passwords(self, api_client):
        response = api_client.post(
            reverse("api:accounts:register"),
            {"username": "x1", "email": "x1@example.com", "password": PASSWORD, "password_confirm": "other"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["code"] == "bad_request"
        assert not User.objects.filter(username="x1").exists()

    def test_register_rejects_weak_password(self, api_client):
        response = api_client.post(
            reverse("api:accounts:register"),
            {"username": "x2", "email": "x2@example.com", "password": "12345678", "password_confirm": "12345678"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "password" in response.data["errors"]

    def test_register_rejects_duplicate_email(self, api_client, user):
        response = api_client.post(
            reverse("api:accounts:register"),
            {"username": "copycat", "email": user.email.upper(), "password": PASSWORD, "password_confirm": PASSWORD},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestLogin:
    def test_login_with_username(self, api_client, user):
        response = api_client.post(
            reverse("api:accounts:login"), {"username": user.username, "password": PASSWORD}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["access"]

    def test_login_with_email(self, api_client, user):
        response = api_client.post(
            reverse("api:accounts:login"), {"username": user.email, "password": PASSWORD}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK

    def test_login_rejects_wrong_password_without_enumeration(self, api_client, user):
        response = api_client.post(
            reverse("api:accounts:login"), {"username": user.username, "password": "nope-nope-1"}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        # Same message for unknown user and wrong password: no account enumeration.
        assert response.data["detail"] == "Invalid credentials."
        assert response.data["code"] == "bad_request"

    def test_access_token_grants_access_to_me(self, api_client, user):
        login = api_client.post(
            reverse("api:accounts:login"), {"username": user.username, "password": PASSWORD}, format="json"
        )
        token = login.data["access"]
        me = api_client.get(reverse("api:accounts:me"), HTTP_AUTHORIZATION=f"Bearer {token}")
        assert me.status_code == status.HTTP_200_OK
        assert me.data["username"] == user.username
        assert me.data["email"] == user.email  # owner sees own email

    def test_me_requires_auth(self, api_client):
        response = api_client.get(reverse("api:accounts:me"))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestTokenLifecycle:
    def test_refresh_rotates_access_token(self, api_client, user):
        login = api_client.post(
            reverse("api:accounts:login"), {"username": user.username, "password": PASSWORD}, format="json"
        )
        refresh_token = login.data["refresh"]
        response = api_client.post(reverse("api:accounts:token_refresh"), {"refresh": refresh_token}, format="json")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["access"]
        assert response.data["access"] != login.data["access"]

    def test_logout_blacklists_refresh_token(self, api_client, user):
        login = api_client.post(
            reverse("api:accounts:login"), {"username": user.username, "password": PASSWORD}, format="json"
        )
        refresh_token = login.data["refresh"]
        api_client.force_authenticate(user=user)

        logout = api_client.post(reverse("api:accounts:logout"), {"refresh": refresh_token}, format="json")
        assert logout.status_code == status.HTTP_200_OK

        reused = api_client.post(reverse("api:accounts:token_refresh"), {"refresh": refresh_token}, format="json")
        assert reused.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestProfile:
    def test_update_profile(self, auth_client, user):
        response = auth_client.patch(
            reverse("api:accounts:me"), {"display_name": "Alice A.", "bio": "hi", "is_private": True}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        user.refresh_from_db()
        assert user.display_name == "Alice A."
        assert user.is_private is True

    def test_change_password(self, auth_client, user):
        response = auth_client.post(
            reverse("api:accounts:change_password"),
            {"old_password": PASSWORD, "new_password": "An0therStr0ng!pass"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        user.refresh_from_db()
        assert user.check_password("An0therStr0ng!pass")

    def test_change_password_requires_correct_old_password(self, auth_client):
        response = auth_client.post(
            reverse("api:accounts:change_password"),
            {"old_password": "wrong-old-pass", "new_password": "An0therStr0ng!pass"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_public_user_detail_hides_email(self, auth_client, other_user):
        response = auth_client.get(reverse("api:accounts:user-detail", args=[other_user.username]))
        assert response.status_code == status.HTTP_200_OK
        assert "email" not in response.data
        assert response.data["username"] == other_user.username
