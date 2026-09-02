from io import StringIO

from django.conf import settings
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

    @override_settings(ADMIN_PASSWORD="Temporary-Admin-2!")
    def test_reset_marks_password_as_temporary(self):
        output = StringIO()
        call_command("reset_admin_password", stdout=output)

        self.admin.refresh_from_db()
        self.assertTrue(self.admin.check_password("Temporary-Admin-2!"))
        self.assertTrue(self.admin.account_security_state.must_change_password)
        self.assertNotIn(settings.ADMIN_PASSWORD, output.getvalue())

    @override_settings(ADMIN_PASSWORD="weak")
    def test_reset_rejects_an_invalid_password(self):
        with self.assertRaisesMessage(CommandError, "password"):
            call_command("reset_admin_password")
