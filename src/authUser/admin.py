from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    model = User
    fieldsets = UserAdmin.fieldsets + (
        ("Extra", {"fields": ("is_email_verified", "is_2fa_enabled")}),
    )
    list_display = ("username", "email", "is_staff", "is_email_verified")