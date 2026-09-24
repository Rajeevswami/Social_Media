from __future__ import annotations

from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User


class UserSerializer(serializers.ModelSerializer):
    """Public representation of a user — never leaks email or auth flags."""

    followers_count = serializers.IntegerField(read_only=True)
    following_count = serializers.IntegerField(read_only=True)
    posts_count = serializers.SerializerMethodField()
    avatar_url = serializers.CharField(read_only=True)
    is_following = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id", "username", "display_name", "bio", "avatar_url", "location",
            "website", "is_private", "is_verified", "date_joined",
            "followers_count", "following_count", "posts_count", "is_following",
        )
        read_only_fields = fields

    def get_posts_count(self, obj) -> int:
        if not obj.is_private or self._viewer_can_see(obj):
            return obj.posts.filter(is_hidden=False).count()
        return 0

    def get_is_following(self, obj) -> bool:
        request = self.context.get("request")
        return obj.is_followed_by(getattr(request, "user", None))

    def _viewer_can_see(self, obj) -> bool:
        request = self.context.get("request")
        user = getattr(request, "user", None)
        return bool(user and user.is_authenticated and (user == obj or obj.is_followed_by(user)))


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8, style={"input_type": "password"})
    password_confirm = serializers.CharField(write_only=True, style={"input_type": "password"})

    class Meta:
        model = User
        fields = ("id", "username", "email", "display_name", "password", "password_confirm")
        extra_kwargs = {"email": {"required": True}}

    def validate_email(self, value: str) -> str:
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate(self, attrs: dict) -> dict:
        if attrs["password"] != attrs.pop("password_confirm"):
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        try:
            validate_password(attrs["password"])
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)}) from exc
        return attrs

    def create(self, validated_data: dict) -> User:
        return User.objects.create_user(**validated_data)


class LoginSerializer(serializers.Serializer):
    """Username-or-email login; returns a JWT pair."""

    username = serializers.CharField(write_only=True, help_text="Username or email.")
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate(self, attrs: dict) -> dict:
        identifier = attrs["username"].strip()
        user = None
        if "@" in identifier:
            user = User.objects.filter(email__iexact=identifier).first()
            if user:
                user = authenticate(
                    request=self.context.get("request"),
                    username=user.username,
                    password=attrs["password"],
                )
        else:
            user = authenticate(
                request=self.context.get("request"),
                username=identifier,
                password=attrs["password"],
            )
        if user is None:
            # Identical message for bad user / bad password: no account enumeration.
            # Keyed under "detail" so the error envelope exposes it as the
            # top-level message rather than a field error.
            raise serializers.ValidationError({"detail": "Invalid credentials."})
        if not user.is_active:
            raise serializers.ValidationError({"detail": "This account is disabled."})
        attrs["user"] = user
        return attrs

    def tokens_for(self, user: User) -> dict[str, str]:
        refresh = RefreshToken.for_user(user)
        return {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        }


class LogoutRequestSerializer(serializers.Serializer):
    refresh = serializers.CharField(write_only=True, help_text="Refresh token to revoke.")


class ProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("display_name", "bio", "avatar", "location", "website", "is_private")

    def validate_avatar(self, value):
        from common.validators import validate_image

        if value:
            validate_image(value)
        return value


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_old_password(self, value: str) -> str:
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate_new_password(self, value: str) -> str:
        user = self.context["request"].user
        try:
            validate_password(value, user=user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        return value

    def save(self, **kwargs) -> User:
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save(update_fields=["password", "updated_at"] if hasattr(user, "updated_at") else ["password"])
        return user
