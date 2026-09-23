from django.urls import path

from accounts import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("signup/", views.signup_view, name="signup"),
    path("settings/", views.profile_edit_view, name="profile_edit"),
    path("u/<str:username>/", views.profile_view, name="profile"),
]
