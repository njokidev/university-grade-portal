import re

from django.core.exceptions import ValidationError


class ComplexityValidator:
    """Require at least one uppercase letter, lowercase letter, digit and symbol."""

    rules = [
        (r"[A-Z]", "an uppercase letter"),
        (r"[a-z]", "a lowercase letter"),
        (r"\d", "a digit"),
        (r"[^A-Za-z0-9]", "a symbol"),
    ]

    def validate(self, password, user=None):
        missing = [label for pattern, label in self.rules if not re.search(pattern, password)]
        if missing:
            raise ValidationError(
                "Password must contain " + ", ".join(missing) + ".",
                code="password_too_simple",
            )

    def get_help_text(self):
        return "Your password must contain an uppercase letter, a lowercase letter, a digit and a symbol."
