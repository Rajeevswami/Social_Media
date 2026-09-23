from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView

from accounts import api_views

app_name = "accounts"

urlpatterns = [
    path("register/", api_views.RegisterView.as_view(), name="register"),
    path("login/", api_views.LoginView.as_view(), name="login"),
    path("logout/", api_views.LogoutView.as_view(), name="logout"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("token/verify/", TokenVerifyView.as_view(), name="token_verify"),
    path("me/", api_views.MeView.as_view(), name="me"),
    path("me/password/", api_views.ChangePasswordView.as_view(), name="change_password"),
    path("users/<str:username>/", api_views.UserDetailView.as_view(), name="user-detail"),
]
