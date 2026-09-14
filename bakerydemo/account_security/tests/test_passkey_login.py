import json
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from webauthn.helpers import bytes_to_base64url
from webauthn.helpers.exceptions import InvalidAuthenticationResponse

from bakerydemo.account_security.models import (
    PasskeyAuditEvent,
    PasskeyCredential,
)
from bakerydemo.account_security.passkey_views import GENERIC_LOGIN_ERROR
from bakerydemo.account_security.passkeys import (
    PasskeyCeremonyError,
    build_authentication_options,
    verify_login_credential,
)

PASSKEY_SETTINGS = {
    "ACCOUNT_SECURITY_WEBAUTHN_RP_ID": "localhost",
    "ACCOUNT_SECURITY_WEBAUTHN_ORIGIN": "http://localhost:8000",
    "ACCOUNT_SECURITY_WEBAUTHN_CHALLENGE_TTL_SECONDS": 300,
    "ACCOUNT_SECURITY_PASSKEY_FAILURE_LIMIT": 5,
    "ACCOUNT_SECURITY_PASSKEY_LOCKOUT_SECONDS": 900,
}


@override_settings(**PASSKEY_SETTINGS)
class PasskeyAuthenticationServiceTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(
            username="hello-user",
            is_staff=True,
        )
        self.credential = PasskeyCredential.objects.create(
            user=self.user,
            credential_id=bytes_to_base64url(b"credential-id"),
            credential_public_key=b"public-key",
            user_handle=b"opaque-user-handle",
            sign_count=3,
        )

    def _payload(self, *, user_handle=None):
        return {
            "id": self.credential.credential_id,
            "rawId": self.credential.credential_id,
            "type": "public-key",
            "response": {
                "authenticatorData": "authenticator-data",
                "clientDataJSON": "client-data",
                "signature": "signature",
                "userHandle": bytes_to_base64url(
                    user_handle
                    if user_handle is not None
                    else bytes(self.credential.user_handle)
                ),
            },
        }

    def test_options_are_usernameless_and_require_user_verification(self):
        options = json.loads(build_authentication_options())

        self.assertEqual(options["rpId"], "localhost")
        self.assertEqual(options["userVerification"], "required")
        self.assertNotIn("allowCredentials", options)

    @patch("bakerydemo.account_security.passkeys.verify_authentication_response")
    def test_verified_credential_updates_security_state(self, verify):
        verify.return_value = SimpleNamespace(
            new_sign_count=4,
            credential_device_type=SimpleNamespace(value="single_device"),
            credential_backed_up=False,
        )

        result = verify_login_credential(
            credential_payload=self._payload(),
            challenge=b"challenge",
        )

        self.credential.refresh_from_db()
        self.assertEqual(result, self.credential)
        self.assertEqual(self.credential.sign_count, 4)
        self.assertIsNotNone(self.credential.last_used_at)
        verify.assert_called_once_with(
            credential=self._payload(),
            expected_challenge=b"challenge",
            expected_rp_id="localhost",
            expected_origin="http://localhost:8000",
            credential_public_key=b"public-key",
            credential_current_sign_count=3,
            require_user_verification=True,
        )

    @patch("bakerydemo.account_security.passkeys.verify_authentication_response")
    def test_nonzero_sign_counter_cannot_regress(self, verify):
        verify.return_value = SimpleNamespace(
            new_sign_count=3,
            credential_device_type=SimpleNamespace(value="single_device"),
            credential_backed_up=False,
        )

        with self.assertRaisesMessage(
            PasskeyCeremonyError,
            "sign_count_regression",
        ):
            verify_login_credential(
                credential_payload=self._payload(),
                challenge=b"challenge",
            )

    def test_user_handle_must_match_credential_owner(self):
        with self.assertRaisesMessage(PasskeyCeremonyError, "unknown_credential"):
            verify_login_credential(
                credential_payload=self._payload(user_handle=b"different-user"),
                challenge=b"challenge",
            )


@override_settings(**PASSKEY_SETTINGS)
class PasskeyLoginViewTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(
            username="hello-user",
            is_staff=True,
        )
        self.credential = PasskeyCredential.objects.create(
            user=self.user,
            credential_id=bytes_to_base64url(b"credential-id"),
            credential_public_key=b"public-key",
            user_handle=b"opaque-user-handle",
            sign_count=3,
        )
        self.login_url = reverse("account_security:passkey_login")
        self.options_url = reverse("account_security:passkey_authentication_options")
        self.verify_url = reverse("account_security:passkey_authentication_verify")

    def _payload(self):
        return {
            "credential": {
                "id": self.credential.credential_id,
                "rawId": self.credential.credential_id,
                "type": "public-key",
                "response": {
                    "authenticatorData": "authenticator-data",
                    "clientDataJSON": "client-data",
                    "signature": "signature",
                    "userHandle": bytes_to_base64url(
                        bytes(self.credential.user_handle)
                    ),
                },
            }
        }

    def _issue_challenge(self):
        response = self.client.post(self.options_url)
        self.assertEqual(response.status_code, 200)
        return response

    def test_login_page_has_no_username_or_password_fields(self):
        response = self.client.get(self.login_url)

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="username"')
        self.assertNotContains(response, 'name="password"')
        self.assertContains(response, "使用 Windows Hello 登入")

    def test_password_login_page_links_to_windows_hello(self):
        response = self.client.get(reverse("wagtailadmin_login"))

        self.assertContains(response, self.login_url)
        self.assertContains(response, "使用 Windows Hello 登入")

    def test_options_create_a_fresh_session_challenge(self):
        response = self._issue_challenge()

        options = response.json()
        self.assertNotIn("allowCredentials", options)
        state = self.client.session["account_security_passkey_authentication_challenge"]
        self.assertEqual(state["challenge"], options["challenge"])
        self.assertIn("issued_at", state)

    @patch("bakerydemo.account_security.passkeys.verify_authentication_response")
    def test_valid_discoverable_credential_logs_staff_user_in(self, verify):
        verify.return_value = SimpleNamespace(
            new_sign_count=4,
            credential_device_type=SimpleNamespace(value="single_device"),
            credential_backed_up=False,
        )
        self._issue_challenge()

        response = self.client.post(
            self.verify_url,
            data=json.dumps(self._payload()),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)
        self.assertEqual(response.json()["redirect"], reverse("wagtailadmin_home"))
        self.assertTrue(
            PasskeyAuditEvent.objects.filter(
                event_type="login_succeeded",
                success=True,
                user=self.user,
                credential=self.credential,
            ).exists()
        )

    @patch("bakerydemo.account_security.passkeys.verify_authentication_response")
    def test_challenge_is_single_use(self, verify):
        verify.return_value = SimpleNamespace(
            new_sign_count=4,
            credential_device_type=SimpleNamespace(value="single_device"),
            credential_backed_up=False,
        )
        self._issue_challenge()
        first = self.client.post(
            self.verify_url,
            data=json.dumps(self._payload()),
            content_type="application/json",
        )
        self.client.logout()
        replay = self.client.post(
            self.verify_url,
            data=json.dumps(self._payload()),
            content_type="application/json",
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(replay.status_code, 403)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_missing_and_expired_challenge_return_same_generic_error(self):
        missing = self.client.post(
            self.verify_url,
            data=json.dumps(self._payload()),
            content_type="application/json",
        )
        self._issue_challenge()
        session = self.client.session
        state = session["account_security_passkey_authentication_challenge"]
        state["issued_at"] = (timezone.now() - timedelta(seconds=301)).timestamp()
        session["account_security_passkey_authentication_challenge"] = state
        session.save()
        expired = self.client.post(
            self.verify_url,
            data=json.dumps(self._payload()),
            content_type="application/json",
        )

        self.assertEqual(missing.status_code, 403)
        self.assertEqual(expired.status_code, 403)
        self.assertEqual(missing.json(), expired.json())

    def test_inactive_nonstaff_revoked_and_unknown_credentials_are_generic(self):
        cases = (
            ("inactive", {"is_active": False}),
            ("nonstaff", {"is_staff": False}),
            ("revoked", {"revoked_at": timezone.now()}),
            ("unknown", {"credential_id": bytes_to_base64url(b"unknown")}),
        )
        expected_error = None
        for name, changes in cases:
            with self.subTest(name=name):
                self.user.is_active = True
                self.user.is_staff = True
                self.user.save(update_fields=["is_active", "is_staff"])
                self.credential.revoked_at = None
                self.credential.save(update_fields=["revoked_at"])
                payload = self._payload()
                for field, value in changes.items():
                    if field == "credential_id":
                        payload["credential"]["id"] = value
                    elif field == "revoked_at":
                        self.credential.revoked_at = value
                        self.credential.save(update_fields=["revoked_at"])
                    else:
                        setattr(self.user, field, value)
                        self.user.save(update_fields=[field])
                self._issue_challenge()

                response = self.client.post(
                    self.verify_url,
                    data=json.dumps(payload),
                    content_type="application/json",
                )

                self.assertEqual(response.status_code, 403)
                self.assertNotIn("_auth_user_id", self.client.session)
                expected_error = expected_error or response.json()
                self.assertEqual(response.json(), expected_error)

    @patch("bakerydemo.account_security.passkeys.verify_authentication_response")
    def test_verifier_failure_is_generic_and_records_no_sensitive_details(
        self,
        verify,
    ):
        verify.side_effect = InvalidAuthenticationResponse("signature payload invalid")
        self._issue_challenge()

        response = self.client.post(
            self.verify_url,
            data=json.dumps(self._payload()),
            content_type="application/json",
        )

        event = PasskeyAuditEvent.objects.get(event_type="login_failed")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(event.reason, "invalid_authentication")
        self.assertNotIn("payload", event.reason)
        self.assertNotIn("_auth_user_id", self.client.session)

    @patch("bakerydemo.account_security.passkeys.verify_authentication_response")
    def test_fifth_failed_verification_is_rate_limited_for_fifteen_minutes(
        self,
        verify,
    ):
        verify.side_effect = InvalidAuthenticationResponse("invalid signature")
        responses = []

        for _ in range(5):
            self._issue_challenge()
            responses.append(
                self.client.post(
                    self.verify_url,
                    data=json.dumps(self._payload()),
                    content_type="application/json",
                    REMOTE_ADDR="127.0.0.20",
                )
            )

        self.assertEqual(
            [response.status_code for response in responses[:4]], [403] * 4
        )
        self.assertEqual(responses[4].status_code, 429)
        self.assertEqual(responses[4]["Retry-After"], "900")
        self.assertTrue(
            PasskeyAuditEvent.objects.filter(
                event_type="login_rate_limited",
                reason="failure_limit_reached",
            ).exists()
        )

    @patch("bakerydemo.account_security.passkeys.verify_authentication_response")
    def test_successful_verification_clears_previous_failures(self, verify):
        verify.side_effect = InvalidAuthenticationResponse("invalid signature")
        for _ in range(4):
            self._issue_challenge()
            response = self.client.post(
                self.verify_url,
                data=json.dumps(self._payload()),
                content_type="application/json",
                REMOTE_ADDR="127.0.0.21",
            )
            self.assertEqual(response.status_code, 403)

        verify.side_effect = None
        verify.return_value = SimpleNamespace(
            new_sign_count=4,
            credential_device_type=SimpleNamespace(value="single_device"),
            credential_backed_up=False,
        )
        self._issue_challenge()
        success = self.client.post(
            self.verify_url,
            data=json.dumps(self._payload()),
            content_type="application/json",
            REMOTE_ADDR="127.0.0.21",
        )
        self.assertEqual(success.status_code, 200)
        self.client.logout()

        verify.side_effect = InvalidAuthenticationResponse("invalid signature")
        for _ in range(4):
            self._issue_challenge()
            response = self.client.post(
                self.verify_url,
                data=json.dumps(self._payload()),
                content_type="application/json",
                REMOTE_ADDR="127.0.0.21",
            )
            self.assertEqual(response.status_code, 403)

    @patch("bakerydemo.account_security.passkey_views.cache.get", return_value=None)
    @patch("bakerydemo.account_security.passkey_views.verify_login_credential")
    def test_cache_read_failure_rejects_login_without_server_error(
        self,
        verify,
        _cache_get,
    ):
        self._issue_challenge()

        response = self.client.post(
            self.verify_url,
            data=json.dumps(self._payload()),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"error": str(GENERIC_LOGIN_ERROR)})
        self.assertNotIn("_auth_user_id", self.client.session)
        verify.assert_not_called()

    @patch("bakerydemo.account_security.passkey_views.cache.incr", return_value=None)
    @patch("bakerydemo.account_security.passkey_views.cache.add", return_value=None)
    @patch("bakerydemo.account_security.passkeys.verify_authentication_response")
    def test_cache_write_failure_rejects_login_without_server_error(
        self,
        verify,
        _cache_add,
        _cache_incr,
    ):
        verify.side_effect = InvalidAuthenticationResponse("invalid signature")
        self._issue_challenge()

        response = self.client.post(
            self.verify_url,
            data=json.dumps(self._payload()),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"error": str(GENERIC_LOGIN_ERROR)})
        self.assertNotIn("_auth_user_id", self.client.session)
