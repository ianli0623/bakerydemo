from datetime import timedelta
from unittest.mock import patch

from axes.models import AccessAttempt
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import DatabaseError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone


class AdminLoginLockoutTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="Correct-Password-1!",
        )

    def _post_wagtail_login(
        self,
        password,
        remote_addr="192.0.2.10",
        username="admin",
    ):
        return self.client.post(
            reverse("wagtailadmin_login"),
            {"username": username, "password": password},
            REMOTE_ADDR=remote_addr,
            HTTP_ACCEPT_LANGUAGE="en",
        )

    def test_fifth_failure_locks_the_username_across_ip_addresses(self):
        for attempt in range(4):
            response = self._post_wagtail_login(
                "Wrong-Password-1!",
                remote_addr=f"192.0.2.{attempt + 1}",
            )
            self.assertNotEqual(response.status_code, 429)

        response = self._post_wagtail_login(
            "Wrong-Password-1!",
            remote_addr="198.51.100.9",
        )

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers["Retry-After"], "900")

    def test_username_matching_is_case_insensitive(self):
        for _ in range(4):
            self._post_wagtail_login(
                "Wrong-Password-1!",
                username="Admin",
            )

        response = self._post_wagtail_login("Wrong-Password-1!")

        self.assertEqual(response.status_code, 429)

    def test_locking_one_username_does_not_lock_another_on_same_ip(self):
        get_user_model().objects.create_superuser(
            username="second-admin",
            email="second@example.com",
            password="Second-Admin-Password-1!",
        )
        for _ in range(5):
            self._post_wagtail_login("Wrong-Password-1!")

        response = self._post_wagtail_login(
            "Second-Admin-Password-1!",
            username="second-admin",
        )

        self.assertNotEqual(response.status_code, 429)
        self.assertIn("_auth_user_id", self.client.session)

    def test_successful_login_resets_failures(self):
        for _ in range(4):
            self._post_wagtail_login("Wrong-Password-1!")
        self._post_wagtail_login("Correct-Password-1!")
        self.client.logout()

        for _ in range(4):
            response = self._post_wagtail_login("Wrong-Password-1!")

        self.assertNotEqual(response.status_code, 429)

    def test_django_admin_uses_the_same_username_lock(self):
        for _ in range(5):
            self._post_wagtail_login("Wrong-Password-1!")

        response = self.client.post(
            reverse("admin:login"),
            {"username": "admin", "password": "Correct-Password-1!"},
            REMOTE_ADDR="203.0.113.8",
        )

        self.assertEqual(response.status_code, 429)
        self.assertTrue(AccessAttempt.objects.filter(username="admin").exists())

    def test_invalid_and_locked_responses_use_the_same_generic_message(self):
        message = (
            "The username or password is incorrect, or this account is "
            "temporarily unavailable."
        )
        invalid = self._post_wagtail_login("Wrong-Password-1!")
        self.assertContains(invalid, message)

        for _ in range(4):
            locked = self._post_wagtail_login("Wrong-Password-1!")

        self.assertContains(locked, message, status_code=429)

    def test_attempt_storage_failure_does_not_authenticate(self):
        with patch(
            "axes.handlers.database.AxesDatabaseHandler.get_failures",
            side_effect=DatabaseError("attempt storage unavailable"),
        ):
            with self.assertRaises(DatabaseError):
                self._post_wagtail_login("Correct-Password-1!")

        self.assertNotIn("_auth_user_id", self.client.session)

    def test_lock_expires_after_fifteen_minutes(self):
        for _ in range(5):
            self._post_wagtail_login("Wrong-Password-1!")
        AccessAttempt.objects.filter(username="admin").update(
            attempt_time=timezone.now() - timedelta(minutes=16)
        )

        response = self._post_wagtail_login("Correct-Password-1!")

        self.assertNotEqual(response.status_code, 429)
        self.assertIn("_auth_user_id", self.client.session)

    def test_axes_username_command_unlocks_exact_account(self):
        for _ in range(5):
            self._post_wagtail_login("Wrong-Password-1!")

        call_command("axes_reset_username", "admin", verbosity=0)

        self.assertFalse(AccessAttempt.objects.filter(username="admin").exists())
