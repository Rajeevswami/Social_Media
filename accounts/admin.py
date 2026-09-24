from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from accounts.models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ("username", "email", "display_name", "is_private", "is_verified", "is_staff", "date_joined")
    list_filter = ("is_private", "is_verified", "is_staff", "is_active")
    search_fields = ("username", "email", "display_name")
    fieldsets = DjangoUserAdmin.fieldsets + (
        ("Profile", {"fields": ("display_name", "bio", "avatar", "location", "website", "is_private", "is_verified")}),
    )
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (("Profile", {"fields": ("email", "display_name")}),)
