from django.contrib import admin

from social.models import Comment, Follow, Like


@admin.register(Follow)
class FollowAdmin(admin.ModelAdmin):
    list_display = ("id", "follower", "followee", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("follower__username", "followee__username")


@admin.register(Like)
class LikeAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "post", "created_at")
    search_fields = ("user__username",)


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("id", "author", "post", "created_at", "content_preview")
    search_fields = ("content", "author__username")

    @admin.display(description="Comment")
    def content_preview(self, obj) -> str:
        return obj.content[:60]
