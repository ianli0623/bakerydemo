from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from webauthn.helpers import bytes_to_base64url

from bakerydemo.account_security.models import (
    PasskeyAuditEvent,
    PasskeyCredential,
    PasskeyEnrolment,
)
from bakerydemo.account_security.services import sync_password_change


class PasskeyManagementTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="Admin-Password-1!",
        )
        self.staff = get_user_model().objects.create_user(
            username="staff",
            is_staff=True,
            password="Staff-Password-1!",
        )
        self.user = get_user_model().objects.create_user(
            username="hello-user",
            is_staff=True,
        )
        sync_password_change(self.admin, must_change_password=False)
        sync_password_change(self.staff, must_change_password=False)
        self.staff.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="wagtailadmin",
                codename="access_admin",
            )
        )
        self.credential = PasskeyCredential.objects.create(
            user=self.user,
            credential_id=bytes_to_base64url(b"credential-id"),
            credential_public_key=b"public-key",
            user_handle=b"user-handle",
        )
        self.report_url = reverse("account_security_passkey_management")
        self.enrolment_url = reverse(
            "account_security_passkey_generate_enrolment",
            args=[self.user.pk],
        )
        self.revoke_url = reverse(
            "account_security_passkey_revoke",
            args=[self.credential.pk],
        )

    def test_superuser_can_view_credentials_and_pending_enrolments(self):
        self.client.force_login(self.admin)

        response = self.client.get(self.report_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "hello-user")
        self.assertContains(response, "Windows Hello 管理")

    def test_staff_user_cannot_view_or_mutate_passkeys(self):
        self.client.force_login(self.staff)

        for url in (self.report_url, self.enrolment_url, self.revoke_url):
            with self.subTest(url=url):
                response = (
                    self.client.get(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
                    if url == self.report_url
                    else self.client.post(
                        url,
                        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
                    )
                )
                self.assertEqual(response.status_code, 403)

    def test_generate_enrolment_displays_raw_code_only_on_post_response(self):
        self.client.force_login(self.admin)

        response = self.client.post(self.enrolment_url)

        enrolment = PasskeyEnrolment.objects.get(user=self.user)
        raw_code = response.context["enrolment_code"]
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, raw_code)
        self.assertNotEqual(enrolment.code_digest, raw_code)
        self.assertNotIn(raw_code, str(dict(self.client.session)))
        self.assertTrue(
            PasskeyAuditEvent.objects.filter(
                event_type="enrolment_created",
                success=True,
                user=self.user,
                actor=self.admin,
            ).exists()
        )

        next_response = self.client.get(self.report_url)

        self.assertNotContains(next_response, raw_code)

    def test_revoke_credential_records_actor_target_and_ip(self):
        self.client.force_login(self.admin)

        response = self.client.post(self.revoke_url, REMOTE_ADDR="127.0.0.9")

        self.assertRedirects(response, self.report_url)
        self.credential.refresh_from_db()
        self.assertIsNotNone(self.credential.revoked_at)
        event = PasskeyAuditEvent.objects.get(event_type="credential_revoked")
        self.assertTrue(event.success)
        self.assertEqual(event.actor, self.admin)
        self.assertEqual(event.user, self.user)
        self.assertEqual(event.credential, self.credential)
        self.assertEqual(str(event.ip_address), "127.0.0.9")
