import hashlib
import hmac
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    """A portal user with exactly one role and lockout tracking."""

    class Role(models.TextChoices):
        STUDENT = "student", "Student"
        LECTURER = "lecturer", "Lecturer"
        REGISTRAR = "registrar", "Registrar"
        ADMIN = "admin", "System Administrator"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STUDENT)
    reg_number = models.CharField(max_length=30, blank=True)
    failed_login_attempts = models.PositiveSmallIntegerField(default=0)
    is_locked = models.BooleanField(default=False)
    locked_at = models.DateTimeField(null=True, blank=True)

    def register_failed_login(self):
        """Increment the counter; lock the account when the limit is reached.
        Returns True if this failure locked the account."""
        self.failed_login_attempts += 1
        just_locked = False
        if self.failed_login_attempts >= settings.MAX_FAILED_LOGINS:
            self.is_locked = True
            self.locked_at = timezone.now()
            just_locked = True
        self.save(update_fields=["failed_login_attempts", "is_locked", "locked_at"])
        return just_locked

    def reset_failed_logins(self):
        if self.failed_login_attempts:
            self.failed_login_attempts = 0
            self.save(update_fields=["failed_login_attempts"])

    def unlock(self):
        self.is_locked = False
        self.locked_at = None
        self.failed_login_attempts = 0
        self.save(update_fields=["is_locked", "locked_at", "failed_login_attempts"])


class Course(models.Model):
    code = models.CharField(max_length=20, unique=True)
    title = models.CharField(max_length=120)
    lecturer = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="courses_taught",
        limit_choices_to={"role": User.Role.LECTURER},
    )

    def __str__(self):
        return f"{self.code} {self.title}"


def letter_for(score):
    if score is None:
        return ""
    if score >= 70:
        return "A"
    if score >= 60:
        return "B"
    if score >= 50:
        return "C"
    if score >= 40:
        return "D"
    return "E"


class Grade(models.Model):
    """One student's mark in one course.

    Workflow: a lecturer enters or edits the mark -> status becomes PENDING ->
    the registrar approves it -> status becomes PUBLISHED and the student can
    see it. Each save stores an HMAC signature so tampering directly in the
    database can be detected.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending approval"
        PUBLISHED = "published", "Published"

    student = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="grades",
        limit_choices_to={"role": User.Role.STUDENT},
    )
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="grades")
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    entered_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    approved_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    updated_at = models.DateTimeField(auto_now=True)
    signature = models.CharField(max_length=64, blank=True)

    class Meta:
        unique_together = ("student", "course")
        ordering = ["course__code", "student__username"]

    @property
    def letter(self):
        return letter_for(self.score)

    def _payload(self):
        # Fixed 2-decimal format so 64 and 64.00 produce the same signature.
        score = "" if self.score is None else f"{Decimal(str(self.score)):.2f}"
        return f"{self.student_id}|{self.course_id}|{score}|{self.status}".encode()

    def compute_signature(self):
        key = settings.SECRET_KEY.encode()
        return hmac.new(key, self._payload(), hashlib.sha256).hexdigest()

    def sign(self):
        self.signature = self.compute_signature()

    def is_intact(self):
        return hmac.compare_digest(self.signature or "", self.compute_signature())


class AuditLog(models.Model):
    """Append-only record of security-relevant events (accountability)."""

    timestamp = models.DateTimeField(auto_now_add=True)
    username = models.CharField(max_length=150)
    role = models.CharField(max_length=20, blank=True)
    action = models.CharField(max_length=40)
    detail = models.CharField(max_length=255, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.timestamp:%Y-%m-%d %H:%M:%S} {self.username} {self.action}"
