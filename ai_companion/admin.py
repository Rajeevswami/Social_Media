from django.contrib import admin

from ai_companion.models import MoodCheck, WellbeingNudge


@admin.register(MoodCheck)
class MoodCheckAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "signal", "negative_streak", "posts_analyzed", "provider", "created_at")
    list_filter = ("signal", "provider")
    search_fields = ("user__username",)
    date_hierarchy = "created_at"
    readonly_fields = ("raw",)


@admin.register(WellbeingNudge)
class WellbeingNudgeAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "created_at", "dismissed_at")
    search_fields = ("user__username",)
    date_hierarchy = "created_at"
