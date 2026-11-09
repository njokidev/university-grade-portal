"""Automated security tests. Run with:  python manage.py test portal -v 2

Each test maps to a project objective so results can be reported as
measurable evidence in the presentation.
"""
from django.core.management import call_command
from rest_framework.test import APITestCase

from .models import AuditLog, Grade, User


class PortalTestBase(APITestCase):
    def setUp(self):
        call_command("seed_demo", stdout=open("/dev/null", "w"))

    def login(self, username, password):
        return self.client.post("/api/auth/login/", {"username": username, "password": password},
                                format="json")

    def auth_as(self, username, password):
        r = self.login(username, password)
        self.assertEqual(r.status_code, 200, r.data)
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + r.data["token"])
        return r


class LockoutTests(PortalTestBase):
    """Objective 1: lock an account after exactly 3 failed attempts."""

    def test_account_locks_on_third_failure(self):
        self.assertEqual(self.login("bkamau", "wrong1").status_code, 401)
        self.assertEqual(self.login("bkamau", "wrong2").status_code, 401)
        r = self.login("bkamau", "wrong3")
        self.assertEqual(r.status_code, 423)
        self.assertTrue(User.objects.get(username="bkamau").is_locked)

    def test_correct_password_rejected_while_locked(self):
        for _ in range(3):
            self.login("bkamau", "wrong")
        self.assertEqual(self.login("bkamau", "Student@2026").status_code, 423)

    def test_success_resets_counter(self):
        self.login("bkamau", "wrong")
        self.login("bkamau", "wrong")
        self.assertEqual(self.login("bkamau", "Student@2026").status_code, 200)
        self.assertEqual(User.objects.get(username="bkamau").failed_login_attempts, 0)

    def test_unknown_user_gets_generic_error(self):
        r = self.login("nobody", "whatever")
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.data["detail"], "Invalid username or password.")

    def test_only_admin_can_unlock(self):
        for _ in range(3):
            self.login("bkamau", "wrong")
        uid = User.objects.get(username="bkamau").id
        self.auth_as("registrar", "Registrar@2026")
        self.assertEqual(self.client.post(f"/api/users/{uid}/unlock/").status_code, 403)
        self.client.credentials()
        self.auth_as("sysadmin", "Admin@2026")
        self.assertEqual(self.client.post(f"/api/users/{uid}/unlock/").status_code, 200)
        self.client.credentials()
        self.assertEqual(self.login("bkamau", "Student@2026").status_code, 200)


class RBACTests(PortalTestBase):
    """Objective 2: each role can do only what its role allows."""

    def test_student_sees_only_own_grades(self):
        self.auth_as("bkamau", "Student@2026")
        r = self.client.get("/api/grades/mine/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 3)

    def test_student_cannot_edit_grade(self):
        self.auth_as("bkamau", "Student@2026")
        g = Grade.objects.filter(student__username="bkamau").first()
        r = self.client.patch(f"/api/grades/{g.id}/", {"score": 99}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_lecturer_cannot_edit_other_lecturers_course(self):
        self.auth_as("dr_otieno", "Lecturer@2026")
        g = Grade.objects.filter(course__code="CSC 3102").first()   # taught by dr_wanjiku
        r = self.client.patch(f"/api/grades/{g.id}/", {"score": 99}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_lecturer_edit_goes_to_pending(self):
        self.auth_as("dr_otieno", "Lecturer@2026")
        g = Grade.objects.filter(course__code="ISC 3101", student__username="bkamau").first()
        r = self.client.patch(f"/api/grades/{g.id}/", {"score": 66}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Grade.objects.get(pk=g.id).status, "pending")

    def test_pending_grade_hidden_from_student_until_approved(self):
        g = Grade.objects.filter(course__code="ISC 3101", student__username="bkamau").first()
        self.auth_as("dr_otieno", "Lecturer@2026")
        self.client.patch(f"/api/grades/{g.id}/", {"score": 66}, format="json")
        self.client.credentials()
        self.auth_as("bkamau", "Student@2026")
        self.assertEqual(len(self.client.get("/api/grades/mine/").data), 2)
        self.client.credentials()
        self.auth_as("registrar", "Registrar@2026")
        self.assertEqual(self.client.post(f"/api/grades/{g.id}/approve/").status_code, 200)

    def test_admin_cannot_read_grades(self):
        self.auth_as("sysadmin", "Admin@2026")
        self.assertEqual(self.client.get("/api/courses/").status_code, 403)
        self.assertEqual(self.client.get("/api/grades/pending/").status_code, 403)

    def test_admin_cannot_change_own_role(self):
        r = self.auth_as("sysadmin", "Admin@2026")
        uid = r.data["user"]["id"]
        resp = self.client.post(f"/api/users/{uid}/role/", {"role": "student"}, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_unauthenticated_request_rejected(self):
        self.assertEqual(self.client.get("/api/grades/mine/").status_code, 401)


class IntegrityAndAuditTests(PortalTestBase):
    """Objectives 3 and 4: detect tampering, and log security events."""

    def test_tampered_grade_detected(self):
        call_command("tamper_grade", stdout=open("/dev/null", "w"))
        self.auth_as("registrar", "Registrar@2026")
        r = self.client.get("/api/grades/integrity/")
        self.assertEqual(len(r.data["tampered"]), 1)

    def test_events_are_logged(self):
        for _ in range(3):
            self.login("bkamau", "wrong")
        self.auth_as("amohamed", "Student@2026")
        self.client.get("/api/users/")
        actions = set(AuditLog.objects.values_list("action", flat=True))
        self.assertTrue({"LOGIN_FAILED", "ACCOUNT_LOCKED", "LOGIN_SUCCESS", "ACCESS_DENIED"} <= actions)
