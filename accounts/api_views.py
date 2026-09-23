"""JSON API views for accounts (JWT based)."""
from __future__ import annotations

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from accounts.models import User
from accounts.serializers import (
    ChangePasswordSerializer,
    LoginSerializer,
    LogoutRequestSerializer,
    ProfileUpdateSerializer,
    RegisterSerializer,
    UserSerializer,
)


class RegisterView(generics.CreateAPIView):
    """Create an account and get a JWT pair back in one round trip."""

    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = (AllowAny,)

    @extend_schema(
        responses={201: OpenApiResponse(description="Account created with access/refresh tokens")},
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "user": UserSerializer(user, context={"request": request}).data,
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(request=LoginSerializer, responses={200: OpenApiResponse(description="JWT pair")})
    def post(self, request, *args, **kwargs):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        return Response({"user": UserSerializer(user, context={"request": request}).data, **serializer.tokens_for(user)})


@extend_schema(
    request=LogoutRequestSerializer,
    responses={200: OpenApiResponse(description="Refresh token blacklisted")},
)
class LogoutView(APIView):
    """Blacklist the refresh token so it cannot be replayed after logout."""

    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        raw_token = request.data.get("refresh")
        if not raw_token:
            return Response({"detail": "refresh token is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            RefreshToken(raw_token).blacklist()
        except TokenError:
            # Already revoked/expired: idempotent success keeps clients simple.
            return Response({"detail": "Token already invalidated."}, status=status.HTTP_200_OK)
        return Response({"detail": "Logged out."}, status=status.HTTP_200_OK)


class MeView(generics.RetrieveUpdateAPIView):
    """GET / PATCH the authenticated user's own profile."""

    serializer_class = ProfileUpdateSerializer
    permission_classes = (IsAuthenticated,)

    def get_object(self):
        return self.request.user

    def retrieve(self, request, *args, **kwargs):
        user = request.user
        data = UserSerializer(user, context={"request": request}).data
        data["email"] = user.email  # only exposed to the owner
        return Response(data)

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(instance=request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserSerializer(request.user, context={"request": request}).data)


@extend_schema(request=ChangePasswordSerializer, responses={200: OpenApiResponse(description="Password updated")})
class ChangePasswordView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "Password updated."}, status=status.HTTP_200_OK)


class UserDetailView(generics.RetrieveAPIView):
    """Public profile payload used by the UI and by other clients."""

    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = (IsAuthenticated,)
    lookup_field = "username"


__all__ = [
    "ChangePasswordView",
    "LoginView",
    "LogoutView",
    "MeView",
    "RegisterView",
    "TokenRefreshView",
    "UserDetailView",
]
