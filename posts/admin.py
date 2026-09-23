from django.contrib import admin

from posts.models import Post


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("id", "author", "moderation_status", "is_hidden", "created_at", "content_preview")
    list_filter = ("moderation_status", "is_hidden", "created_at")
    search_fields = ("content", "author__username")
    date_hierarchy = "created_at"
    readonly_fields = (
        "moderation_status", "moderation_flags", "moderation_confidence",
        "moderation_reason", "moderation_provider", "moderation_checked_at",
    )

    @admin.display(description="Content")
    def content_preview(self, obj) -> str:
        return (obj.content or "")[:60]

    @admin.action(description="Approve selected posts")
    def approve(self, request, queryset):
        from django.utils import timezone

        queryset.update(
            moderation_status=Post.ModerationStatus.APPROVED,
            moderation_checked_at=timezone.now(),
            moderation_reason="Approved by a human moderator.",
        )
        self.message_user(request, f"{queryset.count()} post(s) approved.")

    actions = ("approve",)
