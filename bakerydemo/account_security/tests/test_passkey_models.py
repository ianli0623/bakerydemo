from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from bakerydemo.account_security.models import (
    PasskeyAuditEvent,
    PasskeyCredential,
    PasskeyEnrolment,
)


def credential_factory(user, *, credential_id):
    return PasskeyCredential.objects.create(
        user=user,
        credential_id=credential_id,
        credential_public_key=b"public-key",
        user_handle=b"opaque-user-handle",
    )


class PasskeyCredentialTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="passkey-user")
        self.other_user = get_user_model().objects.create_user(username="other-user")

    def test_user_can_own_two_active_credentials(self):
        first = credential_factory(self.user, credential_id="first")
        second = credential_factory(self.user, credential_id="second")

        self.assertNotEqual(first.pk, second.pk)
        self.assertIsNone(first.revoked_at)
        self.assertIsNone(second.revoked_at)

    def test_credential_id_is_globally_unique(self):
        credential_factory(self.user, credential_id="duplicate")

        with self.assertRaises(IntegrityError), transaction.atomic():
            credential_factory(self.other_user, credential_id="duplicate")

    def test_deleting_user_deletes_credentials_and_enrolments(self):
        credential_factory(self.user, credential_id="cascade")
        PasskeyEnrolment.objects.create(
            user=self.user,
            created_by=self.other_user,
            code_digest="a" * 64,
            expires_at="2026-09-14T08:00:00Z",
        )

        self.user.delete()

        self.assertFalse(PasskeyCredential.objects.exists())
        self.assertFalse(PasskeyEnrolment.objects.exists())

    def test_deleting_credential_preserves_audit_event(self):
        credential = credential_factory(self.user, credential_id="audited")
        event = PasskeyAuditEvent.objects.create(
            event_type="credential_revoked",
            success=True,
            user=self.user,
            credential=credential,
        )

        credential.delete()

        event.refresh_from_db()
        self.assertIsNone(event.credential)
