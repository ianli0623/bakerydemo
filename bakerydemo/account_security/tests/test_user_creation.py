from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from bakerydemo.account_security.models import PasskeyEnrolment
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
                "authentication_method": "temporary_password",
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

    def test_secret_responses_are_not_cached(self):
        response = self.client.post(
            reverse("wagtailusers_users:add"),
            {
                "username": "no-cache-editor",
                "email": "no-cache-editor@example.com",
                "first_name": "No Cache",
                "last_name": "Editor",
                "authentication_method": "windows_hello",
            },
        )

        self.assertIn("no-store", response["Cache-Control"])

    def test_creator_receives_one_time_windows_hello_enrolment_code(self):
        response = self.client.post(
            reverse("wagtailusers_users:add"),
            {
                "username": "hello-editor",
                "email": "hello-editor@example.com",
                "first_name": "Hello",
                "last_name": "Editor",
                "authentication_method": "windows_hello",
            },
        )

        user = get_user_model().objects.get(username="hello-editor")
        enrolment = PasskeyEnrolment.objects.get(user=user)
        raw_code = response.context["enrolment_code"]

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "account_security/passkey_enrolment_created.html",
        )
        self.assertFalse(user.has_usable_password())
        self.assertFalse(user.account_security_state.must_change_password)
        self.assertIsNone(user.account_security_state.password_changed_at)
        self.assertContains(response, "Windows Hello")
        self.assertContains(response, raw_code)
        self.assertNotEqual(enrolment.code_digest, raw_code)
        self.assertNotIn(raw_code, str(dict(self.client.session)))

    def test_delegated_user_administrator_cannot_issue_windows_hello_code(self):
        delegated_admin = get_user_model().objects.create_user(
            username="delegated-admin",
            is_staff=True,
            password="Delegated-Password-1!",
        )
        delegated_admin.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="wagtailadmin",
                codename="access_admin",
            ),
            Permission.objects.get(
                content_type__app_label="auth",
                codename="add_user",
            ),
        )
        sync_password_change(delegated_admin, must_change_password=False)
        self.client.force_login(delegated_admin)

        get_response = self.client.get(reverse("wagtailusers_users:add"))
        post_response = self.client.post(
            reverse("wagtailusers_users:add"),
            {
                "username": "unauthorised-hello-editor",
                "email": "unauthorised@example.com",
                "first_name": "Unauthorised",
                "last_name": "Editor",
                "authentication_method": "windows_hello",
            },
        )

        self.assertEqual(get_response.status_code, 200)
        self.assertNotContains(get_response, 'value="windows_hello"')
        self.assertEqual(post_response.status_code, 200)
        self.assertFalse(
            get_user_model()
            .objects.filter(username="unauthorised-hello-editor")
            .exists()
        )
        self.assertFalse(PasskeyEnrolment.objects.exists())
