from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from bakerydemo.account_security.services import sync_password_change


class TemporaryPasswordUserCreationTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="Current-Password-1!",
        )
        sync_password_change(self.admin, must_change_password=False)
        self.client.force_login(self.admin)

    def test_creator_receives_one_time_random_password_for_new_user(self):
        response = self.client.post(
            reverse("wagtailusers_users:add"),
            {
                "username": "new-editor",
                "email": "new-editor@example.com",
                "first_name": "New",
                "last_name": "Editor",
            },
        )

        self.assertTrue(get_user_model().objects.filter(username="new-editor").exists())
        user = get_user_model().objects.get(username="new-editor")
        temporary_password = response.context["temporary_password"]

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "account_security/temporary_password_created.html",
        )
        self.assertTrue(user.check_password(temporary_password))
        self.assertNotEqual(user.password, temporary_password)
        self.assertTrue(user.account_security_state.must_change_password)
        self.assertGreaterEqual(len(temporary_password), 12)
        self.assertRegex(temporary_password, r"[A-Z]")
        self.assertRegex(temporary_password, r"[a-z]")
        self.assertRegex(temporary_password, r"[0-9]")
        self.assertRegex(temporary_password, r"[^A-Za-z0-9]")
        self.assertContains(response, temporary_password)
        self.assertNotIn(temporary_password, str(dict(self.client.session)))

        next_response = self.client.get(reverse("wagtailusers_users:index"))

        self.assertNotContains(next_response, temporary_password)
