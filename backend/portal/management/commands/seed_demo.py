from decimal import Decimal

from django.core.management.base import BaseCommand
from rest_framework.authtoken.models import Token

from portal.models import AuditLog, Course, Grade, User

DEMO_USERS = [
    # username, password, role, first, last, reg number
    ("sysadmin", "Admin@2026", "admin", "Peter", "Njoroge", "STAFF-001"),
    ("registrar", "Registrar@2026", "registrar", "Grace", "Mutua", "STAFF-002"),
    ("dr_otieno", "Lecturer@2026", "lecturer", "James", "Otieno", "STAFF-101"),
    ("dr_wanjiku", "Lecturer@2026", "lecturer", "Mary", "Wanjiku", "STAFF-102"),
    ("bkamau", "Student@2026", "student", "Brian", "Kamau", "SCS/2023/001"),
    ("amohamed", "Student@2026", "student", "Aisha", "Mohamed", "SCS/2023/002"),
    ("kodhiambo", "Student@2026", "student", "Kevin", "Odhiambo", "SCS/2023/003"),
]

COURSES = [
    ("ISC 3101", "Information Security", "dr_otieno"),
    ("ISC 3105", "Network Security", "dr_otieno"),
    ("CSC 3102", "Database Systems", "dr_wanjiku"),
]

SCORES = {
    "bkamau":    [Decimal("64"), Decimal("58"), Decimal("71")],
    "amohamed":  [Decimal("82"), Decimal("77"), Decimal("69")],
    "kodhiambo": [Decimal("47"), Decimal("53"), Decimal("38")],
}


class Command(BaseCommand):
    help = "Reset the database to the classroom demo data."

    def add_arguments(self, parser):
        parser.add_argument("--if-empty", action="store_true",
                            help="Only load demo data when there are no users yet (used on Render).")

    def handle(self, *args, **options):
        if options["if_empty"] and User.objects.exists():
            self.stdout.write("Users already exist; demo data left unchanged.")
            return
        Token.objects.all().delete()
        Grade.objects.all().delete()
        Course.objects.all().delete()
        AuditLog.objects.all().delete()
        User.objects.all().delete()

        # Explicit ids keep the demo identical every time it is reset.
        users = {}
        for i, (username, pw, role, first, last, reg) in enumerate(DEMO_USERS, start=1):
            u = User(id=i, username=username, role=role, first_name=first, last_name=last, reg_number=reg)
            u.set_password(pw)
            u.save()
            users[username] = u

        courses = [Course.objects.create(id=i, code=c, title=t, lecturer=users[lec])
                   for i, (c, t, lec) in enumerate(COURSES, start=1)]

        gid = 0
        for student, scores in SCORES.items():
            for course, score in zip(courses, scores):
                gid += 1
                g = Grade(id=gid, student=users[student], course=course, score=score,
                          status=Grade.Status.PUBLISHED, entered_by=course.lecturer,
                          approved_by=users["registrar"])
                g.sign()
                g.save()

        self.stdout.write(self.style.SUCCESS("Demo data loaded. Accounts:"))
        for username, pw, role, *_ in DEMO_USERS:
            self.stdout.write(f"  {role:<10} {username:<12} {pw}")