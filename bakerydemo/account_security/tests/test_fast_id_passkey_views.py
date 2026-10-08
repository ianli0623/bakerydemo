import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from bakerydemo.account_security.fast_id import (
    FastIdAuthenticationResult,
    FastIdError,
)
from bakerydemo.account_security.models import (
    FastIdUserLink,
    PasskeyAuditEvent,
    PasskeyCredential,
)
from bakerydemo.account_security.passkey_views import (
    GENERIC_LOGIN_ERROR,
    GENERIC_REGISTRATION_ERROR,
)
from bakerydemo.account_security.passkeys import create_enrolment

FAST_ID_SETTINGS = {
    "FAST_ID_ENABLED": True,
    "FAST_ID_BASE_URL": "https://fido.example.com",
    "FAST_ID_TENANT_ID": "tenant-id",
    "FAST_ID_TENANT_KEY": "tenant-key",
    "FAST_ID_CLIENT_ID": "client-id",
    "FAST_ID_CLIENT_SECRET": "client-secret",
    "FAST_ID_MANAGEMENT_API_TOKEN": "management-token",
    "FAST_ID_TIMEOUT_SECONDS": 2.5,
    "ACCOUNT_SECURITY_WEBAUTHN_RP_ID": "example.com",
    "ACCOUNT_SECURITY_WEBAUTHN_ORIGIN": "https://example.com",
    "ACCOUNT_SECURITY_WEBAUTHN_CHALLENGE_TTL_SECONDS": 300,
    "ACCOUNT_SECURITY_PASSKEY_FAILURE_LIMIT": 5,
    "ACCOUNT_SECURITY_PASSKEY_LOCKOUT_SECONDS": 900,
}


class FakeFastIdClient:
    def __init__(
        self,
        *,
        email="person@example.com",
        external_user_id="external-1",
        users=None,
    ):
        self.external_user_id = external_user_id
        self.users = users or [
            {
                "id": external_user_id,
                "email": email,
                "enabled": True,
            }
        ]
        self.registration_payload = None
        self.authentication_payload = None
        self.registration_finalize_error = None
        self.authentication_finalize_error = None

    def list_users(self):
        return self.users

    def issue_user_token(self, user_id):
        return f"user-token-for-{user_id}"

    def registration_initialize(self, user_token):
        return {
            "challenge": "registration-challenge",
            "user": {"id": "opaque-user-handle"},
        }

    def registration_finalize(self, user_token, credential):
        if self.registration_finalize_error:
            raise self.registration_finalize_error
        self.registration_payload = credential
        return True

    def authentication_initialize(self):
        return {"challenge": "authentication-challenge"}

    def authentication_finalize(self, credential):
        if self.authentication_finalize_error:
            raise self.authentication_finalize_error
        self.authentication_payload = credential
        return FastIdAuthenticationResult(
            external_user_id=self.external_user_id,
        )


@override_settings(**FAST_ID_SETTINGS)
class FastIdPasskeyViewTests(TestCase):
    def setUp(self):
        cache.clear()
        self.admin = get_user_model().objects.create_superuser(
            username="Admin",
            email="admin@example.com",
            password="Admin-Password-1!",
        )
        self.user = get_user_model().objects.create_user(
            username="Person",
            email="person@example.com",
            password="Recovery-Password-1!",
            is_active=True,
            is_staff=True,
        )
        self.enrolment, self.raw_code = create_enrolment(
            self.user,
            self.admin,
            disable_password_on_success=True,
        )
        self.enrol_url = reverse("account_security:passkey_enrol")
        self.registration_options_url = reverse(
            "account_security:passkey_registration_options"
        )
        self.registration_verify_url = reverse(
            "account_security:passkey_registration_verify"
        )
        self.authentication_options_url = reverse(
            "account_security:passkey_authentication_options"
        )
        self.authentication_verify_url = reverse(
            "account_security:passkey_authentication_verify"
        )

    def _authorize_registration(self):
        response = self.client.post(
            self.enrol_url,
            {"email": self.user.email, "enrolment_code": self.raw_code},
        )
        self.assertTrue(response.context["registration_ready"])

    def _client_patch(self, fake):
        return patch(
            "bakerydemo.account_security.passkey_providers.FastIdClient.from_settings",
            return_value=fake,
        )

    def test_registration_uses_existing_urls_and_preserves_recovery_password(self):
        fake = FakeFastIdClient()
        self._authorize_registration()

        with self._client_patch(fake):
            options = self.client.post(self.registration_options_url)
            response = self.client.post(
                self.registration_verify_url,
                data=json.dumps(
                    {
                        "credential": {
                            "id": "credential-id",
                            "type": "public-key",
                            "token": "browser-controlled-token",
                        }
                    }
                ),
                content_type="application/json",
            )

        self.assertEqual(options.status_code, 200)
        self.assertEqual(options.json()["challenge"], "registration-challenge")
        self.assertEqual(response.status_code, 200)
        self.enrolment.refresh_from_db()
        self.user.refresh_from_db()
        link = FastIdUserLink.objects.get(user=self.user)
        self.assertIsNotNone(link.registered_at)
        self.assertIsNotNone(self.enrolment.consumed_at)
        self.assertTrue(self.user.has_usable_password())
        self.assertEqual(PasskeyCredential.objects.count(), 0)
        self.assertNotIn("token", fake.registration_payload)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)
        self.assertTrue(
            PasskeyAuditEvent.objects.filter(
                event_type="registration_succeeded",
                success=True,
                user=self.user,
                credential__isnull=True,
            ).exists()
        )

    def test_authentication_uses_verified_subject_and_ignores_browser_token(self):
        FastIdUserLink.objects.create(
            user=self.user,
            tenant_key="tenant-key",
            external_user_id="external-1",
            registered_at=timezone.now(),
        )
        fake = FakeFastIdClient()

        with self._client_patch(fake):
            options = self.client.post(self.authentication_options_url)
            response = self.client.post(
                self.authentication_verify_url,
                data=json.dumps(
                    {
                        "credential": {
                            "id": "credential-id",
                            "type": "public-key",
                            "token": "browser-controlled-token",
                        }
                    }
                ),
                content_type="application/json",
            )

        self.assertEqual(options.status_code, 200)
        self.assertEqual(options.json()["challenge"], "authentication-challenge")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("token", fake.authentication_payload)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)
        self.assertNotIn(
            "account_security_passkey_authentication_challenge",
            self.client.session,
        )
        self.assertTrue(
            PasskeyAuditEvent.objects.filter(
                event_type="login_succeeded",
                success=True,
                user=self.user,
                credential__isnull=True,
            ).exists()
        )

    def test_provider_mismatch_is_generic_and_state_is_single_use(self):
        fake = FakeFastIdClient()
        with self._client_patch(fake):
            self.client.post(self.authentication_options_url)

        with override_settings(FAST_ID_ENABLED=False):
            first = self.client.post(
                self.authentication_verify_url,
                data=json.dumps({"credential": {"id": "credential-id"}}),
                content_type="application/json",
            )
            replay = self.client.post(
                self.authentication_verify_url,
                data=json.dumps({"credential": {"id": "credential-id"}}),
                content_type="application/json",
            )

        self.assertEqual(first.status_code, 403)
        self.assertEqual(first.json(), {"error": str(GENERIC_LOGIN_ERROR)})
        self.assertEqual(replay.json(), first.json())
        self.assertNotIn(
            "account_security_passkey_authentication_challenge",
            self.client.session,
        )

    def test_malformed_credential_payload_is_generic_and_consumes_state(self):
        fake = FakeFastIdClient()
        with self._client_patch(fake):
            self.client.post(self.authentication_options_url)
            response = self.client.post(
                self.authentication_verify_url,
                data=json.dumps({"credential": []}),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {"error": str(GENERIC_LOGIN_ERROR)})
        self.assertNotIn(
            "account_security_passkey_authentication_challenge",
            self.client.session,
        )

    def test_remote_failures_are_generic_safe_and_do_not_leak_secrets(self):
        FastIdUserLink.objects.create(
            user=self.user,
            tenant_key="tenant-key",
            external_user_id="external-1",
            registered_at=timezone.now(),
        )
        cases = (
            ("remote_timeout", 503),
            ("remote_unavailable", 503),
            ("remote_http_error", 503),
            ("invalid_response", 403),
            ("remote_rejected", 403),
        )
        for reason, expected_status in cases:
            with self.subTest(reason=reason):
                PasskeyAuditEvent.objects.all().delete()
                fake = FakeFastIdClient()
                fake.authentication_finalize_error = FastIdError(reason)

                with self._client_patch(fake):
                    self.client.post(self.authentication_options_url)
                    response = self.client.post(
                        self.authentication_verify_url,
                        data=json.dumps({"credential": {"id": "credential-id"}}),
                        content_type="application/json",
                    )

                event = PasskeyAuditEvent.objects.get(event_type="login_failed")
                response_text = response.content.decode()
                self.assertEqual(response.status_code, expected_status)
                self.assertEqual(response.json(), {"error": str(GENERIC_LOGIN_ERROR)})
                self.assertEqual(event.reason, reason)
                self.assertNotIn("client-secret", response_text)
                self.assertNotIn("management-token", response_text)
                self.assertNotIn("_auth_user_id", self.client.session)

    def test_ambiguous_remote_registration_users_are_generic(self):
        cases = (
            (
                [
                    {"id": "external-1", "email": "person@example.com"},
                    {"id": "external-2", "email": "PERSON@example.com"},
                ],
                "fast_id_user_ambiguous",
            ),
        )
        for users, expected_reason in cases:
            with self.subTest(reason=expected_reason):
                PasskeyAuditEvent.objects.all().delete()
                self._authorize_registration()
                fake = FakeFastIdClient(users=users)

                with self._client_patch(fake):
                    response = self.client.post(self.registration_options_url)

                event = PasskeyAuditEvent.objects.get(event_type="registration_failed")
                self.assertEqual(response.status_code, 403)
                self.assertEqual(
                    response.json(), {"error": str(GENERIC_REGISTRATION_ERROR)}
                )
                self.assertEqual(event.reason, expected_reason)
                self.assertNotIn("client-secret", response.content.decode())
                self.assertNotIn("management-token", response.content.decode())

    def test_failed_registration_cannot_be_replayed_or_disable_password(self):
        fake = FakeFastIdClient()
        fake.registration_finalize_error = FastIdError("invalid_registration")
        self._authorize_registration()

        with self._client_patch(fake):
            self.client.post(self.registration_options_url)
            first = self.client.post(
                self.registration_verify_url,
                data=json.dumps({"credential": {"id": "credential-id"}}),
                content_type="application/json",
            )
            replay = self.client.post(
                self.registration_verify_url,
                data=json.dumps({"credential": {"id": "credential-id"}}),
                content_type="application/json",
            )

        link = FastIdUserLink.objects.get(user=self.user)
        self.enrolment.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(first.status_code, 403)
        self.assertEqual(first.json(), {"error": str(GENERIC_REGISTRATION_ERROR)})
        self.assertEqual(replay.json(), first.json())
        self.assertIsNone(link.registered_at)
        self.assertIsNone(self.enrolment.consumed_at)
        self.assertTrue(self.user.has_usable_password())
