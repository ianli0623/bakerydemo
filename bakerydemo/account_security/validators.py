import re

from django.contrib.auth.hashers import check_password
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from .models import PasswordHistory


class PasswordComplexityValidator:
    minimum_length = 12

    def validate(self, password, user=None):
        checks = (
            (
                len(password) >= self.minimum_length,
                "short",
                _("The password must contain at least 12 characters."),
            ),
            (
                bool(re.search(r"[A-Z]", password)),
                "uppercase",
                _("The password must contain an uppercase English letter."),
            ),
            (
                bool(re.search(r"[a-z]", password)),
                "lowercase",
                _("The password must contain a lowercase English letter."),
            ),
            (
                bool(re.search(r"[0-9]", password)),
                "number",
                _("The password must contain a number."),
            ),
            (
                any(
                    not character.isalnum() and not character.isspace()
                    for character in password
                ),
                "symbol",
                _("The password must contain a symbol."),
            ),
        )
        errors = [
            ValidationError(message, code=code)
            for is_valid, code, message in checks
            if not is_valid
        ]
        if errors:
            raise ValidationError(errors)

    def get_help_text(self):
        return _(
            "Use at least 12 characters with uppercase, lowercase, number, and symbol."
        )


class PasswordHistoryValidator:
    history_limit = 3

    def validate(self, password, user=None):
        if user is None or user.pk is None:
            return

        encoded_passwords = list(
            PasswordHistory.objects.filter(user=user).values_list(
                "encoded_password", flat=True
            )[: self.history_limit]
        )
        if user.has_usable_password() and user.password not in encoded_passwords:
            encoded_passwords.insert(0, user.password)
            encoded_passwords = encoded_passwords[: self.history_limit]

        if any(check_password(password, encoded) for encoded in encoded_passwords):
            raise ValidationError(
                _("This password was recently used. Choose a different password."),
                code="password_used_recently",
            )

    def get_help_text(self):
        return _(
            "The new password cannot match any of your 3 most recent passwords."
        )
