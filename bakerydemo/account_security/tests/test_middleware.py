from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bakerydemo.account_security.services import sync_password_change


class PasswordPolicyMiddlewareTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="Temporary-Password-1!",
        )
        self.client.force_login(self.user)
        self.change_url = reverse("account_security:password_change")

    def test_temporary_password_redirects_both_admins(self):
        for url in (reverse("wagtailadmin_home"), reverse("admin:index")):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertRedirects(
                    response,
                    self.change_url,
                    fetch_redirect_response=False,
                )

    def test_compliant_password_allows_both_admins(self):
        sync_password_change(self.user, must_change_password=False)

        for url in (reverse("wagtailadmin_home"), reverse("admin:index")):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)

    def test_frontend_page_is_not_blocked(self):
        response = self.client.get("/")

        redirect_url = response.url if response.status_code in {301, 302} else ""
        self.assertNotEqual(redirect_url, self.change_url)

    def test_password_at_90_days_is_redirected(self):
        state = self.user.account_security_state
        state.must_change_password = False
        state.password_changed_at = timezone.now() - timedelta(days=90)
        state.save()

        response = self.client.get(reverse("wagtailadmin_home"))

        self.assertRedirects(
            response,
            self.change_url,
            fetch_redirect_response=False,
        )

    def test_logout_remains_available(self):
        response = self.client.post(reverse("wagtailadmin_logout"))

        redirect_url = response.url if response.status_code in {301, 302} else ""
        self.assertNotEqual(redirect_url, self.change_url)

    def test_missing_state_fails_closed(self):
        self.user.account_security_state.delete()

        response = self.client.get(reverse("wagtailadmin_home"))

        self.assertRedirects(
            response,
            self.change_url,
            fetch_redirect_response=False,
        )
        self.user.refresh_from_db()
        self.assertTrue(self.user.account_security_state.must_change_password)

    def test_django_password_change_route_uses_shared_flow(self):
        sync_password_change(self.user, must_change_password=False)

        response = self.client.get(reverse("admin:password_change"))

        self.assertRedirects(
            response,
            self.change_url,
            fetch_redirect_response=False,
        )

    def test_wagtail_builtin_password_editor_is_disabled(self):
        sync_password_change(self.user, must_change_password=False)

        response = self.client.get(reverse("wagtailadmin_account"))

        self.assertFalse(settings.WAGTAIL_PASSWORD_MANAGEMENT_ENABLED)
        self.assertNotContains(response, 'name="password-old_password"')
