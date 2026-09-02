import re

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from bakerydemo.account_security.services import set_user_password


class SecurityPasswordChangeViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="Current-Password-1!",
        )
        self.url = reverse("account_security:password_change")

    def test_anonymous_user_is_sent_to_wagtail_login(self):
        response = self.client.get(self.url)

        self.assertRedirects(
            response,
            f"{reverse('wagtailadmin_login')}?next={self.url}",
        )

    def test_wrong_current_password_does_not_change_password(self):
        self.client.force_login(self.user)

        response = self.client.post(
            self.url,
            {
                "old_password": "Wrong-Password-1!",
                "new_password1": "Replacement-Password-2!",
                "new_password2": "Replacement-Password-2!",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Current-Password-1!"))

    def test_recent_password_is_rejected(self):
        set_user_password(
            self.user,
            "Temporary-Password-2!",
            must_change_password=True,
        )
        self.client.force_login(self.user)

        response = self.client.post(
            self.url,
            {
                "old_password": "Temporary-Password-2!",
                "new_password1": "Current-Password-1!",
                "new_password2": "Current-Password-1!",
            },
        )

        form_errors = response.context["form"].errors.as_data()
        self.assertEqual(
            form_errors["new_password1"][0].code,
            "password_used_recently",
        )
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Temporary-Password-2!"))

    def test_success_updates_session_and_returns_to_original_admin(self):
        set_user_password(
            self.user,
            "Temporary-Password-2!",
            must_change_password=True,
        )
        self.client.force_login(self.user)
        session = self.client.session
        session["account_security_return_to"] = reverse("admin:index")
        session.save()

        response = self.client.post(
            self.url,
            {
                "old_password": "Temporary-Password-2!",
                "new_password1": "Replacement-Password-3!",
                "new_password2": "Replacement-Password-3!",
            },
        )

        self.assertRedirects(response, reverse("admin:index"))
        self.assertIn("_auth_user_id", self.client.session)
        self.user.refresh_from_db()
        self.assertFalse(self.user.account_security_state.must_change_password)

    def test_external_return_url_is_not_used(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["account_security_return_to"] = "https://attacker.example/"
        session.save()

        response = self.client.post(
            self.url,
            {
                "old_password": "Current-Password-1!",
                "new_password1": "Replacement-Password-2!",
                "new_password2": "Replacement-Password-2!",
            },
        )

        self.assertRedirects(response, reverse("wagtailadmin_home"))

    def test_password_inputs_do_not_render_values(self):
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        content = response.content.decode()
        password_inputs = re.findall(
            r"<input\b[^>]*\btype=[\"']password[\"'][^>]*>",
            content,
            flags=re.IGNORECASE,
        )
        self.assertEqual(len(password_inputs), 3)
        for password_input in password_inputs:
            self.assertNotRegex(password_input, r"\bvalue\s*=")
