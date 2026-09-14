import hashlib
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from bakerydemo.account_security.models import PasskeyAuditEvent
from bakerydemo.account_security.passkeys import (
    create_enrolment,
    record_passkey_event,
    validate_enrolment,
)


@override_settings(ACCOUNT_SECURITY_WEBAUTHN_ENROLMENT_TTL_SECONDS=900)
class PasskeyEnrolmentServiceTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="Admin-Password-1!",
        )
        self.user = get_user_model().objects.create_user(
            username="hello-user",
            is_staff=True,
        )

    def test_create_enrolment_returns_raw_code_but_stores_only_digest(self):
        enrolment, raw_code = create_enrolment(
            self.user,
            self.admin,
            disable_password_on_success=True,
        )

        self.assertNotEqual(enrolment.code_digest, raw_code)
        self.assertEqual(
            enrolment.code_digest,
            hashlib.sha256(raw_code.encode()).hexdigest(),
        )
        self.assertNotIn(raw_code, repr(enrolment.__dict__))
        self.assertEqual(len(enrolment.code_digest), 64)

    def test_create_enrolment_revokes_previous_unused_code(self):
        first, _ = create_enrolment(
            self.user,
            self.admin,
            disable_password_on_success=True,
        )

        second, _ = create_enrolment(
            self.user,
            self.admin,
            disable_password_on_success=True,
        )

        first.refresh_from_db()
        self.assertIsNotNone(first.revoked_at)
        self.assertIsNone(second.revoked_at)

    def test_database_allows_only_one_unconsumed_unrevoked_code_per_user(self):
        create_enrolment(
            self.user,
            self.admin,
            disable_password_on_success=True,
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            self.user.passkey_enrolments.create(
                created_by=self.admin,
                code_digest="f" * 64,
                disable_password_on_success=True,
                expires_at=timezone.now() + timedelta(minutes=15),
            )

    def test_validate_enrolment_returns_active_matching_row(self):
        enrolment, raw_code = create_enrolment(
            self.user,
            self.admin,
            disable_password_on_success=True,
        )

        result = validate_enrolment(self.user.username, raw_code)

        self.assertEqual(result, enrolment)

    def test_validate_enrolment_rejects_expired_code(self):
        enrolment, raw_code = create_enrolment(
            self.user,
            self.admin,
            disable_password_on_success=True,
        )

        result = validate_enrolment(
            self.user.username,
            raw_code,
            at=enrolment.expires_at,
        )

        self.assertIsNone(result)

    def test_validate_enrolment_rejects_consumed_or_revoked_code(self):
        consumed, consumed_code = create_enrolment(
            self.user,
            self.admin,
            disable_password_on_success=True,
        )
        consumed.consumed_at = timezone.now()
        consumed.save(update_fields=["consumed_at"])

        self.assertIsNone(validate_enrolment(self.user.username, consumed_code))

        revoked, revoked_code = create_enrolment(
            self.user,
            self.admin,
            disable_password_on_success=True,
        )
        revoked.revoked_at = timezone.now()
        revoked.save(update_fields=["revoked_at"])

        self.assertIsNone(validate_enrolment(self.user.username, revoked_code))

    def test_validate_enrolment_rejects_wrong_user_or_code(self):
        _, raw_code = create_enrolment(
            self.user,
            self.admin,
            disable_password_on_success=True,
        )

        self.assertIsNone(validate_enrolment("missing-user", raw_code))
        self.assertIsNone(validate_enrolment(self.user.username, "wrong-code"))

    def test_expiry_uses_configured_ttl(self):
        before = timezone.now()

        enrolment, _ = create_enrolment(
            self.user,
            self.admin,
            disable_password_on_success=True,
        )

        self.assertGreaterEqual(enrolment.expires_at, before + timedelta(seconds=899))
        self.assertLessEqual(
            enrolment.expires_at,
            timezone.now() + timedelta(seconds=901),
        )


class PasskeyAuditServiceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="audited-user")

    def test_event_records_bounded_request_metadata(self):
        request = type(
            "Request",
            (),
            {
                "META": {
                    "REMOTE_ADDR": "192.0.2.1",
                    "HTTP_USER_AGENT": "x" * 300,
                }
            },
        )()

        event = record_passkey_event(
            "login_failed",
            success=False,
            user=self.user,
            request=request,
            reason="invalid_assertion",
        )

        self.assertEqual(event.ip_address, "192.0.2.1")
        self.assertEqual(len(event.user_agent), 255)
        self.assertEqual(event.reason, "invalid_assertion")
        self.assertEqual(PasskeyAuditEvent.objects.count(), 1)
