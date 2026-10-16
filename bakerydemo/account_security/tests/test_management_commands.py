from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings


class ResetAdminPasswordTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="Old-Password-1!",
        )

    @override_settings(ADMIN_PASSWORD="Configured-Password-Must-Not-Be-Used-1!")
    @patch(
        "bakerydemo.base.management.commands.reset_admin_password.getpass",
        side_effect=["Temporary-Admin-2!", "Temporary-Admin-2!"],
    )
    def test_reset_uses_an_interactively_entered_temporary_password(self, _getpass):
        output = StringIO()
        call_command("reset_admin_password", stdout=output)

        self.admin.refresh_from_db()
        self.assertTrue(self.admin.check_password("Temporary-Admin-2!"))
        self.assertFalse(
            self.admin.check_password("Configured-Password-Must-Not-Be-Used-1!")
        )
        self.assertTrue(self.admin.account_security_state.must_change_password)
        self.assertNotIn("Temporary-Admin-2!", output.getvalue())

    @patch(
        "bakerydemo.base.management.commands.reset_admin_password.getpass",
        side_effect=["Temporary-Admin-2!", "Different-Admin-3!"],
    )
    def test_reset_rejects_password_confirmation_mismatch(self, _getpass):
        with self.assertRaisesMessage(CommandError, "match"):
            call_command("reset_admin_password")

        self.admin.refresh_from_db()
        self.assertTrue(self.admin.check_password("Old-Password-1!"))

    @patch(
        "bakerydemo.base.management.commands.reset_admin_password.getpass",
        side_effect=["weak", "weak"],
    )
    def test_reset_rejects_an_invalid_password(self, _getpass):
        with self.assertRaisesMessage(CommandError, "password"):
            call_command("reset_admin_password")

        self.admin.refresh_from_db()
        self.assertTrue(self.admin.check_password("Old-Password-1!"))
