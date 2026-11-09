from django.conf import settings

from .models import AuditLog


def client_ip(request):
    # On Render every request arrives from its proxy, so REMOTE_ADDR is the
    # proxy's address; the visitor's address is the first X-Forwarded-For entry.
    if settings.TRUST_X_FORWARDED_FOR:
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
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