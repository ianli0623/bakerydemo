from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core.exceptions import ValidationError
from django.test import TestCase

from bakerydemo.account_security.models import PasswordHistory
from bakerydemo.account_security.validators import (
    PasswordComplexityValidator,
    PasswordHistoryValidator,
)


class PasswordComplexityValidatorTests(TestCase):
    def test_requires_each_character_class(self):
        invalid_passwords = {
            "short": "Aa1!short",
            "uppercase": "lowercase-123!",
            "lowercase": "UPPERCASE-123!",
            "number": "NoNumbersHere!",
            "symbol": "NoSymbols1234",
        }
        validator = PasswordComplexityValidator()

        for expected_code, password in invalid_passwords.items():
            with self.subTest(expected_code=expected_code):
                with self.assertRaises(ValidationError) as error:
                    validator.validate(password)
                self.assertIn(
                    expected_code,
                    {item.code for item in error.exception.error_list},
                )

    def test_accepts_a_valid_password(self):
        PasswordComplexityValidator().validate("Valid-Password-1!")


class PasswordHistoryValidatorTests(TestCase):
    def test_rejects_any_of_the_three_most_recent_passwords(self):
        user = get_user_model().objects.create_user(username="editor")
        for password in (
            "History-One-1!",
            "History-Two-2!",
            "History-Three-3!",
        ):
            PasswordHistory.objects.create(
                user=user, encoded_password=make_password(password)
            )

        with self.assertRaisesMessage(ValidationError, "recently used"):
            PasswordHistoryValidator().validate("History-Two-2!", user)

    def test_ignores_a_fourth_older_password(self):
        user = get_user_model().objects.create_user(username="editor")
        PasswordHistory.objects.create(
            user=user, encoded_password=make_password("Old-Enough-Password-1!")
        )
        for password in (
            "Recent-One-1!",
            "Recent-Two-2!",
            "Recent-Three-3!",
        ):
            PasswordHistory.objects.create(
                user=user, encoded_password=make_password(password)
            )

        PasswordHistoryValidator().validate("Old-Enough-Password-1!", user)
