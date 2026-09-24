"""Session-based UI views (Django templates + Bootstrap 5).

The UI and the JSON API share models and permissions; only the transport
differs (CSRF-protected session vs. Bearer JWT).
"""
from __future__ import annotations

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView as DjangoLoginView
from django.contrib.auth.views import LogoutView as DjangoLogoutView
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from accounts.forms import LoginForm, ProfileEditForm, SignUpForm
from accounts.models import User


class LoginView(DjangoLoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True


class LogoutView(DjangoLogoutView):
    next_page = "accounts:login"


@require_http_methods(["GET", "POST"])
def signup_view(request):
    if request.user.is_authenticated:
        return redirect("posts:feed")
    form = SignUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        messages.success(request, f"Welcome to {settings.SITE_NAME}, {user.username}!")
        return redirect("posts:feed")
    return render(request, "accounts/signup.html", {"form": form})


def profile_view(request, username: str):
    profile = get_object_or_404(User, username=username)
    viewer = request.user
    is_owner = viewer.is_authenticated and viewer == profile
    can_view = is_owner or profile.can_view(viewer)

    posts = (
        profile.posts.select_related("author").prefetch_related("likes", "comments__author")
        if can_view
        else profile.posts.none()
    )
    posts = posts.filter(is_hidden=False).order_by("-created_at")

    return render(
        request,
        "accounts/profile.html",
        {
            "profile": profile,
            "posts": posts,
            "is_owner": is_owner,
            "can_view": can_view,
            "is_following": profile.is_followed_by(viewer),
            "active_tab": "profile",
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def profile_edit_view(request):
    form = ProfileEditForm(request.POST or None, request.FILES or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profile updated.")
        return redirect("accounts:profile", username=request.user.username)
    return render(request, "accounts/profile_edit.html", {"form": form, "active_tab": "profile"})
