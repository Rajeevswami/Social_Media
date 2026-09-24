"""Reusable DRF permissions."""
from __future__ import annotations

from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsOwnerOrReadOnly(BasePermission):
    """Object must expose `user` (or `author`) to be editable only by its owner."""

    def has_object_permission(self, request, view, obj) -> bool:
        if request.method in SAFE_METHODS:
            return True
        owner = getattr(obj, "user", None) or getattr(obj, "author", None)
        return bool(owner and owner == request.user)


class IsOwner(BasePermission):
    def has_object_permission(self, request, view, obj) -> bool:
        owner = getattr(obj, "user", None) or getattr(obj, "author", None)
        return bool(owner and owner == request.user)


class IsPostVisible(BasePermission):
    """Private accounts: only the author and approved followers may read a post."""

    def has_object_permission(self, request, view, obj) -> bool:
        post = getattr(obj, "post", obj)
        author = post.author
        if request.user.is_authenticated and (request.user == author or request.user.is_staff):
            return True
        if not getattr(author, "is_private", False):
            return True
        if not request.user.is_authenticated:
            return False
        return author.followers.filter(follower=request.user, is_active=True).exists()
