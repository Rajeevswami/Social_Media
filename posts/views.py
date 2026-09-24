"""Session-based UI views for posts."""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from ai_companion.models import WellbeingNudge
from posts.api_views import with_counts
from posts.forms import PostEditForm, PostForm
from posts.models import Post


def _nudge_context(user):
    if not user.is_authenticated:
        return {"active_nudge": None}
    nudge = (
        WellbeingNudge.objects.filter(user=user, dismissed_at__isnull=True)
        .select_related("mood_check")
        .order_by("-created_at")
        .first()
    )
    return {"active_nudge": nudge}


@login_required
def feed_view(request):
    posts = with_counts(Post.objects.feed_for(request.user))
    form = PostForm()
    form.instance.author = request.user
    return render(
        request,
        "posts/feed.html",
        {"posts": posts, "form": form, "active_tab": "feed", **_nudge_context(request.user)},
    )


def explore_view(request):
    posts = with_counts(Post.objects.public_only())
    return render(request, "posts/explore.html", {"posts": posts, "active_tab": "explore"})


@login_required
@require_http_methods(["GET", "POST"])
def compose_view(request):
    form = PostForm(request.POST or None, request.FILES or None)
    form.instance.author = request.user
    if request.method == "POST" and form.is_valid():
        post = form.save()
        messages.success(request, "Posted! Our safety check runs in the background.")
        return redirect(post.get_absolute_url())
    return render(
        request,
        "posts/compose.html",
        {"form": form, "active_tab": "feed", **_nudge_context(request.user)},
    )


def post_detail_view(request, pk: int):
    post = get_object_or_404(
        with_counts(Post.objects.all()), pk=pk, is_hidden=False
    )
    if not post.visible_to(request.user):
        return HttpResponseForbidden("This post is on a private account.")
    comments = post.comments.select_related("author").order_by("created_at")
    return render(
        request,
        "posts/detail.html",
        {"post": post, "comments": comments, "active_tab": "feed", **_nudge_context(request.user)},
    )


@login_required
@require_http_methods(["GET", "POST"])
def post_edit_view(request, pk: int):
    post = get_object_or_404(Post, pk=pk, author=request.user, is_hidden=False)
    form = PostEditForm(request.POST or None, request.FILES or None, instance=post)
    if request.method == "POST" and form.is_valid():
        from django.utils import timezone

        from ai_companion.tasks import moderate_post_task

        post = form.save()
        post.edited_at = timezone.now()
        post.moderation_status = Post.ModerationStatus.PENDING
        post.moderation_reason = ""
        post.moderation_flags = []
        post.save(
            update_fields=["edited_at", "moderation_status", "moderation_reason", "moderation_flags", "updated_at"]
        )
        moderate_post_task.delay(post.id)
        messages.info(request, "Post updated — re-running the safety check.")
        return redirect(post.get_absolute_url())
    return render(request, "posts/edit.html", {"form": form, "post": post})


@login_required
@require_http_methods(["POST"])
def post_delete_view(request, pk: int):
    post = get_object_or_404(Post, pk=pk, author=request.user)
    post.is_hidden = True
    post.save(update_fields=["is_hidden", "updated_at"])
    messages.success(request, "Post deleted.")
    return redirect("posts:feed")
