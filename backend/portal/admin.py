from django.contrib import admin

from .models import AuditLog, Course, Grade, User

admin.site.register(User)
admin.site.register(Course)
admin.site.register(Grade)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "username", "role", "action", "detail", "ip_address")

    # The audit log is append-only, even for Django superusers.
    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
