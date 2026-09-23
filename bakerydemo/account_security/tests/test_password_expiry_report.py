import json
import re
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bakerydemo.account_security.services import sync_password_change


class PasswordExpiryReportTests(TestCase):
    def setUp(self):
        self.superuser = get_user_model().objects.create_superuser(
            username="security-admin",
            email="security-admin@example.com",
            password="Current-Password-1!",
        )
        sync_password_change(self.superuser, must_change_password=False)
        self.client.force_login(self.superuser)

    def create_staff_user(self, username, password_age_days):
        user = get_user_model().objects.create_user(
            username=username,
            email=f"{username}@example.com",
            password="Current-Password-1!",
            is_staff=True,
        )
        state = user.account_security_state
        state.must_change_password = False
        state.password_changed_at = timezone.now() - timedelta(days=password_age_days)
        state.save()
        user.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="wagtailadmin",
                codename="access_admin",
            )
        )
        return user

    def get_sidebar_menu_names(self):
        response = self.client.get(reverse("wagtailadmin_home"))
        match = re.search(
            r'<script id="wagtail-sidebar-props" type="application/json">(.*?)</script>',
            response.content.decode(),
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        sidebar = json.loads(match.group(1))
        names = []

        def collect_names(value):
            if isinstance(value, dict):
                if "name" in value:
                    names.append(value["name"])
                for child in value.values():
                    collect_names(child)
            elif isinstance(value, list):
                for child in value:
                    collect_names(child)

        collect_names(sidebar)
        return names

    def test_report_lists_only_active_admin_users_expiring_within_30_days(self):
        expiring_user = self.create_staff_user("expiring-editor", 75)
        safe_user = self.create_staff_user("safe-editor", 20)
        inactive_user = self.create_staff_user("inactive-editor", 75)
        inactive_user.is_active = False
        inactive_user.save(update_fields=["is_active"])

        response = self.client.get(reverse("account_security_password_expiry_report"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "密碼到期提醒")
        self.assertContains(response, expiring_user.username)
        self.assertNotContains(response, safe_user.username)
        self.assertNotContains(response, inactive_user.username)
        self.assertContains(response, "15 天")

    def test_report_identifies_accounts_by_email_and_keeps_alias_visible(self):
        user = self.create_staff_user("expiring-alias", 75)
        user.first_name = "Legacy"
        user.last_name = "Name"
        user.save(update_fields=["first_name", "last_name"])

        response = self.client.get(
            reverse("account_security_password_expiry_report"),
            HTTP_ACCEPT_LANGUAGE="en",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Email (account ID)")
        self.assertContains(response, "Alias / display name")
        self.assertContains(response, user.email)
        self.assertContains(response, user.username)
        self.assertNotContains(response, "Legacy Name")
        self.assertNotContains(response, ">Username<")

    def test_report_rejects_non_superusers(self):
        editor = self.create_staff_user("regular-editor", 75)
        self.client.force_login(editor)

        response = self.client.get(
            reverse("account_security_password_expiry_report"),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 403)

    def test_report_menu_is_visible_to_superusers(self):
        menu_names = self.get_sidebar_menu_names()

        self.assertIn("password-expiry-reminders", menu_names)

    def test_report_menu_is_hidden_from_non_superusers(self):
        editor = self.create_staff_user("regular-editor", 20)
        self.client.force_login(editor)

        menu_names = self.get_sidebar_menu_names()

        self.assertNotIn("password-expiry-reminders", menu_names)
