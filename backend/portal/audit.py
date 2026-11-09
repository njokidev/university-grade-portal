from .models import AuditLog


def client_ip(request):
    return request.META.get("REMOTE_ADDR")


def log_event(request, action, detail="", username=None, role=None):
    """Write one entry to the audit log."""
    user = getattr(request, "user", None)
    if username is None:
        username = user.username if user and user.is_authenticated else "anonymous"
    if role is None:
        role = user.role if user and user.is_authenticated else ""
    AuditLog.objects.create(
        username=username[:150],
        role=role,
        action=action,
        detail=detail[:255],
        ip_address=client_ip(request),
    )
