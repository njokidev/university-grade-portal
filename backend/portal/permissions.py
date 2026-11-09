"""Role-based access control (RBAC).

Every protected endpoint declares which roles may call it. The check runs
on the server, so hiding a button in the React UI is only a convenience:
a user who calls the API directly is still blocked, and the attempt is logged.
"""
from rest_framework.permissions import BasePermission

from .audit import log_event
from .models import User

STUDENT = User.Role.STUDENT
LECTURER = User.Role.LECTURER
REGISTRAR = User.Role.REGISTRAR
ADMIN = User.Role.ADMIN

# Human-readable matrix, also served to the frontend for the demo.
PERMISSION_MATRIX = {
    "View own published grades": [STUDENT],
    "Change own password": [STUDENT, LECTURER, REGISTRAR, ADMIN],
    "View & enter grades for OWN courses": [LECTURER],
    "View all courses and grades": [REGISTRAR],
    "Approve grade changes": [REGISTRAR],
    "Run grade integrity check": [REGISTRAR],
    "View audit log": [REGISTRAR, ADMIN],
    "Create users / unlock accounts / change roles": [ADMIN],
}


def role_required(*roles):
    """Build a DRF permission class that only admits the given roles."""

    class RolePermission(BasePermission):
        message = "Access denied: this action requires the role " + " or ".join(roles) + "."

        def has_permission(self, request, view):
            user = request.user
            if not (user and user.is_authenticated):
                return False
            if user.role in roles:
                return True
            log_event(request, "ACCESS_DENIED",
                      f"{request.method} {request.path} (needs {'/'.join(roles)})")
            return False

    RolePermission.__name__ = "Role_" + "_".join(roles)
    return RolePermission
