"""UI views for the social graph (follow lists, follow requests)."""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from accounts.models import User
from social.models import Comment, Follow
from social.services import accept_follow_request, reject_follow_request


def connection_list_view(request, username: str, kind: str):
    profile = get_object_or_404(User, username=username)
    # A private account's social graph is private too: without this any logged
    # in user could enumerate who follows a private account.
    if not profile.can_view(request.user):
        raise Http404
    if kind == "followers":
        people = [f.follower for f in Follow.objects.filter(followee=profile, is_active=True).select_related("follower")]
    else:
        people = [f.followee for f in Follow.objects.filter(follower=profile, is_active=True).select_related("followee")]
    return render(
        request,
        "social/connection_list.html",
        {"profile": profile, "people": people, "kind": kind},
    )


@login_required
def follow_requests_view(request):
    requests_qs = Follow.objects.filter(followee=request.user, is_active=False).select_related("follower")
    return render(request, "social/follow_requests.html", {"requests": requests_qs})


@login_required
@require_http_methods(["POST"])
def follow_request_decision_view(request, follower_id: int, decision: str):
    follower = get_object_or_404(User, pk=follower_id)
    if decision == "accept":
        accept_follow_request(request.user, follower)
        messages.success(request, f"You now follow {follower.username}.")
    elif decision == "reject":
        reject_follow_request(request.user, follower)
        messages.info(request, f"Request from {follower.username} declined.")
    else:
        messages.error(request, "Unknown action.")
    return redirect("social:follow_requests")


@login_required
@require_http_methods(["POST"])
def comment_delete_view(request, pk: int):
    """The comment author or the post author may delete a comment."""
    comment = get_object_or_404(Comment.objects.select_related("post"), pk=pk)
    post_url = comment.post.get_absolute_url()
    if request.user not in (comment.author, comment.post.author) and not request.user.is_staff:
        messages.error(request, "You cannot delete that comment.")
        return redirect(post_url)
    comment.delete()
    messages.success(request, "Comment deleted.")
    return redirect(post_url)
