from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import translation

from bakerydemo.account_security.forms import (
    SecureUserEditForm,
    TemporaryPasswordUserCreationForm,
)
from bakerydemo.account_security.models import PasskeyEnrolment
from bakerydemo.account_security.services import sync_password_change


class TemporaryPasswordUserCreationTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="Current-Password-1!",
        )
        self.editor_group, _created = Group.objects.get_or_create(name="Editors")
        sync_password_change(self.admin, must_change_password=False)
        self.client.force_login(self.admin)

    def test_user_creation_form_displays_authentication_method(self):
        response = self.client.get(reverse("wagtailusers_users:add"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="authentication_method"')
        self.assertContains(response, 'value="windows_hello"')

    def test_username_is_presented_as_display_alias_and_email_as_account_id(self):
        with translation.override("zh-hant"):
            form = TemporaryPasswordUserCreationForm(for_user=self.admin)
            alias_label = str(form.fields["username"].label)
            email_label = str(form.fields["email"].label)

        self.assertEqual(alias_label, "別名／姓名")
        self.assertEqual(email_label, "Email（帳號 ID）")

    def test_user_forms_hide_structured_name_fields(self):
        forms = (
            TemporaryPasswordUserCreationForm(for_user=self.admin),
            SecureUserEditForm(instance=self.admin, editing_self=True),
        )

        for form in forms:
            with self.subTest(form=form.__class__.__name__):
                self.assertNotIn("first_name", form.fields)
                self.assertNotIn("last_name", form.fields)

    def test_account_email_is_normalized_when_user_is_created(self):
        response = self.client.post(
            reverse("wagtailusers_users:add"),
            {
                "username": "visible-alias",
                "email": "  Staff.User@EXAMPLE.COM  ",
                "first_name": "Staff",
                "last_name": "User",
                "authentication_method": "temporary_password",
                "groups": [self.editor_group.pk],
            },
        )

        self.assertEqual(response.status_code, 200)
        user = get_user_model().objects.get(username="visible-alias")
        self.assertEqual(user.email, "staff.user@example.com")

    def test_account_email_must_be_unique_ignoring_case(self):
        get_user_model().objects.create_user(
            username="existing-alias",
            email="staff.user@example.com",
        )

        response = self.client.post(
            reverse("wagtailusers_users:add"),
            {
                "username": "different-alias",
                "email": "STAFF.USER@example.com",
                "first_name": "Different",
                "last_name": "User",
                "authentication_method": "temporary_password",
                "groups": [self.editor_group.pk],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            get_user_model().objects.filter(username="different-alias").exists()
        )
        email_errors = response.context["form"].errors.as_data()["email"]
        self.assertEqual(email_errors[0].code, "duplicate_email")

    def test_database_rejects_duplicate_nonempty_email_ignoring_case(self):
        get_user_model().objects.create_user(
            username="first-alias",
            email="account.id@example.com",
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            get_user_model().objects.create_user(
                username="second-alias",
                email="ACCOUNT.ID@example.com",
            )

    def test_user_edit_rejects_duplicate_email_ignoring_case(self):
        target = get_user_model().objects.create_user(
            username="target-alias",
            email="target@example.com",
            first_name="Target",
            last_name="User",
            is_staff=True,
        )
        target.groups.add(self.editor_group)
        get_user_model().objects.create_user(
            username="existing-alias",
            email="existing@example.com",
        )

        response = self.client.post(
            reverse("wagtailusers_users:edit", args=[target.pk]),
            {
                "username": target.username,
                "email": "EXISTING@example.com",
                "first_name": target.first_name,
                "last_name": target.last_name,
                "is_active": "on",
                "groups": [self.editor_group.pk],
            },
        )

        self.assertEqual(response.status_code, 200)
        email_errors = response.context["form"].errors.as_data()["email"]
        self.assertEqual(email_errors[0].code, "duplicate_email")
        target.refresh_from_db()
        self.assertEqual(target.email, "target@example.com")

    def test_user_edit_normalizes_account_email(self):
        target = get_user_model().objects.create_user(
            username="target-alias",
            email="target@example.com",
            first_name="Target",
            last_name="User",
            is_staff=True,
        )
        target.groups.add(self.editor_group)

        response = self.client.post(
            reverse("wagtailusers_users:edit", args=[target.pk]),
            {
                "username": target.username,
                "email": "  UPDATED@EXAMPLE.COM  ",
                "is_active": "on",
                "groups": [self.editor_group.pk],
            },
        )

        self.assertEqual(response.status_code, 302)
        target.refresh_from_db()
        self.assertEqual(target.email, "updated@example.com")
        self.assertEqual(target.first_name, "Target")
        self.assertEqual(target.last_name, "User")

    def test_user_edit_page_uses_alias_as_subtitle(self):
        target = get_user_model().objects.create_user(
            username="visible-alias",
            email="visible@example.com",
            first_name="Legacy",
            last_name="Name",
            is_staff=True,
        )

        response = self.client.get(reverse("wagtailusers_users:edit", args=[target.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["view"].get_page_subtitle(), "visible-alias")

    def test_account_profile_does_not_allow_account_id_email_changes(self):
        response = self.client.get(reverse("wagtailadmin_account"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="name_email-email"')

    def test_user_list_uses_email_as_account_id_and_username_as_alias(self):
        get_user_model().objects.create_user(
            username="visible-alias",
            email="account.id@example.com",
            first_name="Visible",
            last_name="Name",
            is_staff=True,
        )

        response = self.client.get(
            reverse("wagtailusers_users:index"),
            HTTP_ACCEPT_LANGUAGE="en",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Email (account ID)")
        self.assertContains(response, "Alias / display name")
        self.assertContains(response, "account.id@example.com")
        self.assertContains(response, "visible-alias")
        self.assertNotContains(response, ">Username<")

    def test_new_users_are_created_as_staff(self):
        for authentication_method in ("temporary_password", "windows_hello"):
            with self.subTest(authentication_method=authentication_method):
                username = f"{authentication_method}-staff-user"
                self.client.post(
                    reverse("wagtailusers_users:add"),
                    {
                        "username": username,
                        "email": f"{username}@example.com",
                        "first_name": "Staff",
                        "last_name": "User",
                        "authentication_method": authentication_method,
                        "groups": [self.editor_group.pk],
                    },
                )

                user = get_user_model().objects.get(username=username)
                self.assertTrue(user.is_staff)

    def test_creator_receives_one_time_random_password_for_new_user(self):
        response = self.client.post(
            reverse("wagtailusers_users:add"),
            {
                "username": "new-editor",
                "email": "new-editor@example.com",
                "first_name": "New",
                "last_name": "Editor",
                "authentication_method": "temporary_password",
                "groups": [self.editor_group.pk],
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
                "groups": [self.editor_group.pk],
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
                "groups": [self.editor_group.pk],
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

    def test_user_creation_requires_a_group_or_administrator_role(self):
        for authentication_method in ("temporary_password", "windows_hello"):
            with self.subTest(authentication_method=authentication_method):
                username = f"roleless-{authentication_method}"
                response = self.client.post(
                    reverse("wagtailusers_users:add"),
                    {
                        "username": username,
                        "email": f"{username}@example.com",
                        "first_name": "Roleless",
                        "last_name": "User",
                        "authentication_method": authentication_method,
                    },
                )

                self.assertEqual(response.status_code, 200)
                self.assertFalse(
                    get_user_model().objects.filter(username=username).exists()
                )
                role_errors = response.context["form"].errors.as_data()["groups"]
                self.assertEqual(role_errors[0].code, "required_role")

    def test_administrator_role_satisfies_role_requirement(self):
        response = self.client.post(
            reverse("wagtailusers_users:add"),
            {
                "username": "new-administrator",
                "email": "new-administrator@example.com",
                "first_name": "New",
                "last_name": "Administrator",
                "authentication_method": "temporary_password",
                "is_superuser": True,
            },
        )

        self.assertEqual(response.status_code, 200)
        user = get_user_model().objects.get(username="new-administrator")
        self.assertTrue(user.is_superuser)

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
