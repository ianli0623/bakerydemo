from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from bakerydemo.account_security.models import PasswordHistory, UserSecurityState
from bakerydemo.account_security.services import (
    password_is_expired,
    set_user_password,
)


@override_settings(ACCOUNT_SECURITY_PASSWORD_MAX_AGE_DAYS=90)
class PasswordServiceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="editor", password="Initial-Password-1!"
        )

    def test_external_password_save_records_history_and_requires_change(self):
        self.user.set_password("Temporary-Password-2!")
        self.user.save(update_fields=["password"])

        state = self.user.account_security_state
        self.assertTrue(state.must_change_password)
        self.assertTrue(
            self.user.password_history.filter(
                encoded_password=self.user.password
            ).exists()
        )

    def test_self_service_password_change_clears_flag_and_keeps_three_hashes(self):
        for password in (
            "Second-Password-2!",
            "Third-Password-3!",
            "Fourth-Password-4!",
        ):
            set_user_password(self.user, password, must_change_password=False)

        state_from_database = UserSecurityState.objects.get(user=self.user)
        self.assertFalse(state_from_database.must_change_password)
        self.assertFalse(self.user.account_security_state.must_change_password)
        self.assertEqual(self.user.password_history.count(), 3)

    def test_password_expires_at_the_90_day_boundary(self):
        state = self.user.account_security_state
        now = timezone.now()
        state.password_changed_at = now - timedelta(days=90)
        state.must_change_password = False
        state.save()

        self.assertTrue(password_is_expired(self.user, at=now))

    def test_history_failure_rolls_back_password(self):
        original_hash = self.user.password
        with patch(
            "bakerydemo.account_security.services.PasswordHistory.objects.create",
            side_effect=RuntimeError("history unavailable"),
        ):
            with self.assertRaises(RuntimeError):
                set_user_password(
                    self.user,
                    "Replacement-Password-2!",
                    must_change_password=False,
                )

        self.user.refresh_from_db()
        self.assertEqual(self.user.password, original_hash)

    def test_unusable_password_is_not_added_to_history(self):
        self.user.set_unusable_password()
        self.user.save(update_fields=["password"])

        self.assertFalse(
            PasswordHistory.objects.filter(
                user=self.user, encoded_password=self.user.password
            ).exists()
        )
