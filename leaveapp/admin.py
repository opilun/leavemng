from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

from .models import Holiday, Leave_Detail, Profile


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False


class CustomUserAdmin(UserAdmin):
    inlines = [ProfileInline]


admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display = ("name", "date")
    search_fields = ("name",)


@admin.register(Leave_Detail)
class LeaveDetailAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "submit_date",
        "leave_date_from",
        "leave_date_to",
        "leave_days_count",
        "reason",
        "status",
    )
    search_fields = ("name", "reason", "status")
