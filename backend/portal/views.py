from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .audit import log_event
from .models import AuditLog, Course, Grade, User
from .permissions import (ADMIN, LECTURER, PERMISSION_MATRIX, REGISTRAR, STUDENT,
                          role_required)

# A pre-computed hash used to keep response time the same whether or not a
# username exists, so timing does not reveal valid usernames.
_DUMMY_USER = User()
_DUMMY_USER.set_password("timing-equaliser-Pa55!")


# ---------------------------------------------------------------- helpers
def user_json(u):
    return {
        "id": u.id, "username": u.username, "full_name": u.get_full_name(),
        "role": u.role, "reg_number": u.reg_number,
        "is_locked": u.is_locked, "failed_login_attempts": u.failed_login_attempts,
        "locked_at": u.locked_at,
    }


def grade_json(g, include_student=True):
    data = {
        "id": g.id, "course_code": g.course.code, "course_title": g.course.title,
        "score": float(g.score) if g.score is not None else None,
        "letter": g.letter, "status": g.status, "updated_at": g.updated_at,
    }
    if include_student:
        data.update(student=g.student.get_full_name(), reg_number=g.student.reg_number)
    return data


# ---------------------------------------------------------- authentication
@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def login(request):
    username = str(request.data.get("username", "")).strip()
    password = str(request.data.get("password", ""))
    generic_error = "Invalid username or password."

    user = User.objects.filter(username=username).first()

    if user is None or not user.is_active:
        _DUMMY_USER.check_password(password)  # equalise timing
        log_event(request, "LOGIN_FAILED", "unknown or inactive user", username=username or "-")
        return Response({"detail": generic_error}, status=status.HTTP_401_UNAUTHORIZED)

    if user.is_locked:
        log_event(request, "LOGIN_BLOCKED", "login attempt on locked account",
                  username=user.username, role=user.role)
        return Response(
            {"detail": "This account is locked after too many failed attempts. "
                       "Contact the system administrator.", "locked": True},
            status=status.HTTP_423_LOCKED,
        )

    if not user.check_password(password):
        just_locked = user.register_failed_login()
        if just_locked:
            log_event(request, "ACCOUNT_LOCKED",
                      f"locked after {settings.MAX_FAILED_LOGINS} failed attempts",
                      username=user.username, role=user.role)
            return Response(
                {"detail": "Too many failed attempts. This account is now locked.", "locked": True},
                status=status.HTTP_423_LOCKED,
            )
        log_event(request, "LOGIN_FAILED",
                  f"wrong password (attempt {user.failed_login_attempts}/{settings.MAX_FAILED_LOGINS})",
                  username=user.username, role=user.role)
        body = {"detail": generic_error}
        if settings.SHOW_REMAINING_ATTEMPTS:
            body["attempts_left"] = settings.MAX_FAILED_LOGINS - user.failed_login_attempts
        return Response(body, status=status.HTTP_401_UNAUTHORIZED)

    # Success: reset counter, issue a fresh token (old sessions are revoked).
    user.reset_failed_logins()
    Token.objects.filter(user=user).delete()
    token = Token.objects.create(user=user)
    log_event(request, "LOGIN_SUCCESS", "", username=user.username, role=user.role)
    return Response({"token": token.key, "user": user_json(user),
                     "expires_in_minutes": settings.SESSION_TOKEN_MINUTES})


@api_view(["POST"])
def logout(request):
    Token.objects.filter(user=request.user).delete()
    log_event(request, "LOGOUT")
    return Response({"detail": "Logged out."})


@api_view(["GET"])
def me(request):
    return Response({"user": user_json(request.user), "permission_matrix": PERMISSION_MATRIX})


@api_view(["POST"])
def change_password(request):
    user = request.user
    if not user.check_password(str(request.data.get("current_password", ""))):
        log_event(request, "PASSWORD_CHANGE_FAILED", "wrong current password")
        return Response({"detail": "Current password is incorrect."}, status=400)
    new = str(request.data.get("new_password", ""))
    try:
        validate_password(new, user)
    except ValidationError as e:
        return Response({"detail": " ".join(e.messages)}, status=400)
    user.set_password(new)
    user.save()
    Token.objects.filter(user=user).delete()
    log_event(request, "PASSWORD_CHANGED")
    return Response({"detail": "Password changed. Please log in again."})


# ----------------------------------------------------------------- student
@api_view(["GET"])
@permission_classes([IsAuthenticated, role_required(STUDENT)])
def my_grades(request):
    # Students only ever see their OWN, PUBLISHED grades.
    grades = Grade.objects.filter(student=request.user, status=Grade.Status.PUBLISHED) \
        .select_related("course")
    return Response([grade_json(g, include_student=False) for g in grades])


# ---------------------------------------------------------------- lecturer
@api_view(["GET"])
@permission_classes([IsAuthenticated, role_required(LECTURER, REGISTRAR)])
def courses(request):
    qs = Course.objects.select_related("lecturer")
    if request.user.role == LECTURER:
        qs = qs.filter(lecturer=request.user)          # least privilege
    return Response([{"id": c.id, "code": c.code, "title": c.title,
                      "lecturer": c.lecturer.get_full_name()} for c in qs])


def _lecturer_owns(request, course):
    if request.user.role == LECTURER and course.lecturer_id != request.user.id:
        log_event(request, "ACCESS_DENIED", f"lecturer tried to access {course.code} (not their course)")
        return False
    return True


@api_view(["GET"])
@permission_classes([IsAuthenticated, role_required(LECTURER, REGISTRAR)])
def course_grades(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    if not _lecturer_owns(request, course):
        return Response({"detail": "Access denied: you do not teach this course."}, status=403)
    grades = course.grades.select_related("student", "course")
    return Response({"course": {"id": course.id, "code": course.code, "title": course.title},
                     "grades": [grade_json(g) for g in grades]})


@api_view(["PATCH"])
@permission_classes([IsAuthenticated, role_required(LECTURER)])
def update_grade(request, grade_id):
    grade = get_object_or_404(Grade.objects.select_related("course", "student"), pk=grade_id)
    if not _lecturer_owns(request, grade.course):
        return Response({"detail": "Access denied: you do not teach this course."}, status=403)
    try:
        score = Decimal(str(request.data.get("score")))
    except (InvalidOperation, TypeError):
        return Response({"detail": "Score must be a number."}, status=400)
    if not (0 <= score <= 100):
        return Response({"detail": "Score must be between 0 and 100."}, status=400)

    old = grade.score
    grade.score = score
    grade.status = Grade.Status.PENDING                   # needs registrar approval
    grade.entered_by = request.user
    grade.approved_by = None
    grade.sign()
    grade.save()
    log_event(request, "GRADE_CHANGED",
              f"{grade.course.code} {grade.student.reg_number}: {old} -> {score} (pending approval)")
    return Response(grade_json(grade))


# --------------------------------------------------------------- registrar
@api_view(["GET"])
@permission_classes([IsAuthenticated, role_required(REGISTRAR)])
def pending_grades(request):
    grades = Grade.objects.filter(status=Grade.Status.PENDING).select_related("course", "student")
    return Response([grade_json(g) | {"entered_by": g.entered_by.username if g.entered_by else ""}
                     for g in grades])


@api_view(["POST"])
@permission_classes([IsAuthenticated, role_required(REGISTRAR)])
def approve_grade(request, grade_id):
    grade = get_object_or_404(Grade.objects.select_related("course", "student"), pk=grade_id)
    if not grade.is_intact():
        log_event(request, "INTEGRITY_FAIL", f"refused to approve tampered grade #{grade.id}")
        return Response({"detail": "Integrity check failed: this record was modified outside "
                                   "the portal. Approval refused."}, status=409)
    if grade.status == Grade.Status.PUBLISHED:
        return Response({"detail": "Already published."}, status=400)
    grade.status = Grade.Status.PUBLISHED
    grade.approved_by = request.user
    grade.sign()
    grade.save()
    log_event(request, "GRADE_APPROVED", f"{grade.course.code} {grade.student.reg_number}: {grade.score}")
    return Response(grade_json(grade))


@api_view(["GET"])
@permission_classes([IsAuthenticated, role_required(REGISTRAR)])
def integrity_check(request):
    grades = Grade.objects.select_related("course", "student")
    tampered = [grade_json(g) for g in grades if not g.is_intact()]
    log_event(request, "INTEGRITY_CHECK", f"{len(tampered)} tampered of {len(grades)}")
    return Response({"checked": len(grades), "tampered": tampered})


# ------------------------------------------------------------ audit + admin
@api_view(["GET"])
@permission_classes([IsAuthenticated, role_required(REGISTRAR, ADMIN)])
def audit_log(request):
    entries = AuditLog.objects.all()[:200]
    return Response([{"timestamp": e.timestamp, "username": e.username, "role": e.role,
                      "action": e.action, "detail": e.detail, "ip": e.ip_address}
                     for e in entries])


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated, role_required(ADMIN)])
def users(request):
    if request.method == "GET":
        return Response([user_json(u) for u in User.objects.order_by("role", "username")])

    data = request.data
    username = str(data.get("username", "")).strip()
    role = data.get("role")
    password = str(data.get("password", ""))
    if not username or role not in User.Role.values:
        return Response({"detail": "Username and a valid role are required."}, status=400)
    if User.objects.filter(username=username).exists():
        return Response({"detail": "That username is taken."}, status=400)
    new_user = User(username=username, role=role,
                    first_name=data.get("first_name", ""), last_name=data.get("last_name", ""),
                    reg_number=data.get("reg_number", ""))
    try:
        validate_password(password, new_user)
    except ValidationError as e:
        return Response({"detail": " ".join(e.messages)}, status=400)
    new_user.set_password(password)
    new_user.save()
    log_event(request, "USER_CREATED", f"{username} as {role}")
    return Response(user_json(new_user), status=201)


@api_view(["POST"])
@permission_classes([IsAuthenticated, role_required(ADMIN)])
def unlock_user(request, user_id):
    target = get_object_or_404(User, pk=user_id)
    target.unlock()
    log_event(request, "ACCOUNT_UNLOCKED", f"unlocked {target.username}")
    return Response(user_json(target))


@api_view(["POST"])
@permission_classes([IsAuthenticated, role_required(ADMIN)])
def change_role(request, user_id):
    target = get_object_or_404(User, pk=user_id)
    new_role = request.data.get("role")
    if target == request.user:
        log_event(request, "ACCESS_DENIED", "admin tried to change own role")
        return Response({"detail": "You cannot change your own role."}, status=403)
    if new_role not in User.Role.values:
        return Response({"detail": "Invalid role."}, status=400)
    old = target.role
    target.role = new_role
    target.save(update_fields=["role"])
    Token.objects.filter(user=target).delete()           # force re-login with new rights
    log_event(request, "ROLE_CHANGED", f"{target.username}: {old} -> {new_role}")
    return Response(user_json(target))
