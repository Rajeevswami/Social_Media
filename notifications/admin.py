from django.contrib import admin

from notifications.models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("id", "recipient", "notification_type", "is_read", "created_at", "message")
    list_filter = ("notification_type", "is_read")
    search_fields = ("message", "recipient__username")
    date_hierarchy = "created_at"
