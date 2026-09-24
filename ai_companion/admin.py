from django.contrib import admin

from ai_companion.models import MoodCheck, WellbeingNudge


class SuperuserOnlyAdmin(admin.ModelAdmin):
    """Wellbeing data is sensitive personal data.

    Mood signals and nudges describe how a user has been feeling. Restricting
    this to superusers keeps ordinary staff accounts (moderators, support) from
    browsing them, which the default `is_staff` check would otherwise allow.
    """

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(MoodCheck)
class MoodCheckAdmin(SuperuserOnlyAdmin):
    list_display = ("id", "user", "signal", "negative_streak", "posts_analyzed", "provider", "created_at")
    list_filter = ("signal", "provider")
    search_fields = ("user__username",)
    date_hierarchy = "created_at"
    readonly_fields = ("raw",)


@admin.register(WellbeingNudge)
class WellbeingNudgeAdmin(SuperuserOnlyAdmin):
    list_display = ("id", "user", "created_at", "dismissed_at")
    search_fields = ("user__username",)
    date_hierarchy = "created_at"
