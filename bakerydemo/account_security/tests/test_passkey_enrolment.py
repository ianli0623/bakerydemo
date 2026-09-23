import json
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from webauthn.helpers import bytes_to_base64url

from bakerydemo.account_security.models import PasskeyAuditEvent, PasskeyCredential
from bakerydemo.account_security.passkeys import (
    build_registration_options,
    complete_registration,
    create_enrolment,
)

PASSKEY_SETTINGS = {
    "ACCOUNT_SECURITY_WEBAUTHN_RP_ID": "localhost",
    "ACCOUNT_SECURITY_WEBAUTHN_ORIGIN": "http://localhost:8000",
    "ACCOUNT_SECURITY_WEBAUTHN_RP_NAME": "SEMI E187",
    "ACCOUNT_SECURITY_WEBAUTHN_CHALLENGE_TTL_SECONDS": 300,
}


@override_settings(**PASSKEY_SETTINGS)
class PasskeyEnrolmentTemplateTests(SimpleTestCase):
    @patch(
        "wagtail.admin.templatetags.wagtailadmin_tags.Locale.objects.all",
        return_value=[],
    )
    def test_enrolment_form_submits_back_to_enrolment_view(self, _locales):
        enrol_url = reverse("account_security:passkey_enrol")

        response = self.client.get(enrol_url)

        rendered_html = response.content.decode()
        self.assertEqual(rendered_html.count("<form"), 1)
        self.assertContains(response, f'formaction="{enrol_url}"')

    @patch(
        "wagtail.admin.templatetags.wagtailadmin_tags.Locale.objects.all",
        return_value=[],
    )
    def test_enrolment_page_links_to_password_login_instead_of_itself(
        self,
        _locales,
    ):
        response = self.client.get(reverse("account_security:passkey_enrol"))

        password_login_url = reverse("wagtailadmin_login")
        self.assertContains(response, f'href="{password_login_url}"')
        self.assertContains(response, "使用 Email 及密碼登入")
        self.assertNotContains(response, "註冊 Windows Hello")


@override_settings(**PASSKEY_SETTINGS)
class PasskeyRegistrationServiceTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="Admin-Password-1!",
        )
        self.user = get_user_model().objects.create_user(
            username="hello-user",
            email="hello.user@example.com",
            first_name="Hello",
            last_name="User",
            is_staff=True,
            password="Temporary-Password-1!",
        )

    def test_options_require_windows_hello_discoverable_credential(self):
        options = json.loads(build_registration_options(self.user))

        self.assertEqual(options["rp"]["id"], "localhost")
        self.assertEqual(
            options["authenticatorSelection"]["authenticatorAttachment"],
            "platform",
        )
        self.assertEqual(
            options["authenticatorSelection"]["residentKey"],
            "required",
        )
        self.assertEqual(
            options["authenticatorSelection"]["userVerification"],
            "required",
        )
        self.assertEqual(len(options["user"]["id"]), 43)

    def test_options_use_email_as_account_id_and_alias_as_display_text(self):
        options = json.loads(build_registration_options(self.user))

        self.assertEqual(options["user"]["name"], "hello.user@example.com")
        self.assertEqual(options["user"]["displayName"], "hello-user")

    def test_options_exclude_active_existing_credentials(self):
        PasskeyCredential.objects.create(
            user=self.user,
            credential_id=bytes_to_base64url(b"existing-id"),
            credential_public_key=b"public-key",
            user_handle=b"user-handle",
        )

        options = json.loads(build_registration_options(self.user))

        self.assertEqual(options["excludeCredentials"][0]["id"], "ZXhpc3RpbmctaWQ")

    @patch("bakerydemo.account_security.passkeys.verify_registration_response")
    def test_complete_registration_stores_verified_values_and_consumes_code(
        self,
        verify,
    ):
        verify.return_value = SimpleNamespace(
            credential_id=b"credential-id",
            credential_public_key=b"verified-public-key",
            sign_count=3,
            credential_device_type=SimpleNamespace(value="single_device"),
            credential_backed_up=False,
        )
        enrolment, _ = create_enrolment(
            self.user,
            self.admin,
            disable_password_on_success=True,
        )

        credential = complete_registration(
            user=self.user,
            enrolment=enrolment,
            credential_payload={"id": "response"},
            challenge=b"challenge",
            user_handle=b"opaque-user-handle",
            transports=["internal"],
        )

        enrolment.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(credential.credential_id, "Y3JlZGVudGlhbC1pZA")
        self.assertEqual(
            bytes(credential.credential_public_key), b"verified-public-key"
        )
        self.assertEqual(credential.sign_count, 3)
        self.assertEqual(credential.transports, ["internal"])
        self.assertIsNotNone(enrolment.consumed_at)
        self.assertFalse(self.user.has_usable_password())
        self.assertFalse(self.user.account_security_state.must_change_password)
        verify.assert_called_once_with(
            credential={"id": "response"},
            expected_challenge=b"challenge",
            expected_rp_id="localhost",
            expected_origin="http://localhost:8000",
            require_user_verification=True,
        )


@override_settings(**PASSKEY_SETTINGS)
class PasskeyEnrolmentViewTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="Admin-Password-1!",
        )
        self.user = get_user_model().objects.create_user(
            username="hello-user",
            email="hello.user@example.com",
            is_staff=True,
        )
        self.enrolment, self.raw_code = create_enrolment(
            self.user,
            self.admin,
            disable_password_on_success=True,
        )
        self.enrol_url = reverse("account_security:passkey_enrol")

    def _validate_code(self):
        return self.client.post(
            self.enrol_url,
            {"email": self.user.email, "enrolment_code": self.raw_code},
        )

    def test_enrolment_code_is_bound_to_email_not_display_alias(self):
        response = self.client.post(
            self.enrol_url,
            {"email": "HELLO.USER@example.com", "enrolment_code": self.raw_code},
        )

        self.assertTrue(response.context["registration_ready"])
        self.assertEqual(
            self.client.session["account_security_passkey_enrolment_id"],
            self.enrolment.pk,
        )

    def test_enrolment_page_does_not_require_login(self):
        response = self.client.get(self.enrol_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Windows Hello")

    def test_valid_code_stores_only_enrolment_id_in_session(self):
        response = self._validate_code()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["registration_ready"])
        self.assertEqual(
            self.client.session["account_security_passkey_enrolment_id"],
            self.enrolment.pk,
        )
        self.assertNotIn(self.raw_code, str(dict(self.client.session)))

    def test_invalid_and_expired_codes_use_same_error(self):
        invalid = self.client.post(
            self.enrol_url,
            {"email": self.user.email, "enrolment_code": "wrong"},
        )
        self.enrolment.expires_at = timezone.now()
        self.enrolment.save(update_fields=["expires_at"])
        expired = self._validate_code()

        self.assertEqual(
            invalid.context["form"].non_field_errors()[0],
            expired.context["form"].non_field_errors()[0],
        )
        events = PasskeyAuditEvent.objects.filter(event_type="enrolment_rejected")
        self.assertEqual(events.count(), 2)
        self.assertEqual(
            set(events.values_list("reason", flat=True)),
            {"invalid_or_expired"},
        )
        self.assertNotIn(self.raw_code, str(list(events.values())))

    def test_registration_options_require_validated_enrolment_session(self):
        unauthorised = self.client.post(
            reverse("account_security:passkey_registration_options")
        )
        self._validate_code()
        authorised = self.client.post(
            reverse("account_security:passkey_registration_options")
        )

        self.assertEqual(unauthorised.status_code, 403)
        self.assertEqual(authorised.status_code, 200)
        options = authorised.json()
        self.assertEqual(options["authenticatorSelection"]["residentKey"], "required")
        challenge_state = self.client.session[
            "account_security_passkey_registration_challenge"
        ]
        self.assertNotIn(self.raw_code, str(challenge_state))
        self.assertIn("challenge", challenge_state)
        self.assertIn("user_handle", challenge_state)
        self.assertEqual(challenge_state["enrolment_id"], self.enrolment.pk)

    def test_new_failed_validation_clears_previous_registration_context(self):
        self._validate_code()
        self.client.post(reverse("account_security:passkey_registration_options"))

        response = self.client.post(
            self.enrol_url,
            {"email": self.user.email, "enrolment_code": "wrong"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(
            "account_security_passkey_enrolment_id",
            self.client.session,
        )
        self.assertNotIn(
            "account_security_passkey_registration_challenge",
            self.client.session,
        )

    @patch("bakerydemo.account_security.passkey_views.complete_registration")
    def test_registration_challenge_cannot_be_used_for_another_enrolment(
        self,
        complete,
    ):
        self._validate_code()
        self.client.post(reverse("account_security:passkey_registration_options"))
        other_user = get_user_model().objects.create_user(
            username="other-hello-user",
            is_staff=True,
        )
        other_enrolment, _ = create_enrolment(
            other_user,
            self.admin,
            disable_password_on_success=True,
        )
        session = self.client.session
        session["account_security_passkey_enrolment_id"] = other_enrolment.pk
        session.save()

        response = self.client.post(
            reverse("account_security:passkey_registration_verify"),
            data=json.dumps({"credential": {"id": "credential-id"}}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
        complete.assert_not_called()

    @patch("bakerydemo.account_security.passkey_views.complete_registration")
    def test_successful_verification_logs_user_in_and_consumes_challenge(
        self,
        complete,
    ):
        credential = PasskeyCredential.objects.create(
            user=self.user,
            credential_id=bytes_to_base64url(b"credential-id"),
            credential_public_key=b"public-key",
            user_handle=b"user-handle",
        )
        complete.return_value = credential
        self._validate_code()
        self.client.post(reverse("account_security:passkey_registration_options"))

        response = self.client.post(
            reverse("account_security:passkey_registration_verify"),
            data=json.dumps(
                {
                    "credential": {"id": "credential-id"},
                    "transports": ["internal"],
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)
        self.assertNotIn(
            "account_security_passkey_registration_challenge",
            self.client.session,
        )

        replay = self.client.post(
            reverse("account_security:passkey_registration_verify"),
            data=json.dumps({"credential": {"id": "credential-id"}}),
            content_type="application/json",
        )
        self.assertEqual(replay.status_code, 403)
