"""Simulate an attacker who gains direct database access and edits a mark,
bypassing the portal (and therefore the HMAC signature and audit log)."""
from django.core.management.base import BaseCommand

from portal.models import Grade


class Command(BaseCommand):
    help = "DEMO ONLY: change a grade directly in the database, bypassing the portal."

    def add_arguments(self, parser):
        parser.add_argument("--student", default="kodhiambo")
        parser.add_argument("--course", default="CSC 3102")
        parser.add_argument("--score", default="95")

    def handle(self, *args, **opts):
        qs = Grade.objects.filter(student__username=opts["student"], course__code=opts["course"])
        if not qs.exists():
            self.stderr.write("No such grade.")
            return
        old = qs.first().score
        qs.update(score=opts["score"])  # .update() skips sign() -- just like raw SQL would
        self.stdout.write(self.style.WARNING(
            f"Tampered: {opts['student']} {opts['course']} {old} -> {opts['score']} "
            "(no signature update, no audit entry)"))
