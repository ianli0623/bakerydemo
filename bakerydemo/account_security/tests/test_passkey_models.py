from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

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

    def test_deleting_user_with_self_created_enrolment_succeeds(self):
        user_id = self.user.pk
        enrolment = PasskeyEnrolment.objects.create(
            user=self.user,
            created_by=self.user,
            code_digest="b" * 64,
            expires_at=timezone.now() + timedelta(minutes=15),
        )

        get_user_model().objects.filter(pk=user_id).delete()

        self.assertFalse(get_user_model().objects.filter(pk=user_id).exists())
        self.assertFalse(PasskeyEnrolment.objects.filter(pk=enrolment.pk).exists())

    def test_deleting_creator_revokes_pending_enrolment_and_preserves_record(self):
        enrolment = PasskeyEnrolment.objects.create(
            user=self.user,
            created_by=self.other_user,
            code_digest="c" * 64,
            expires_at=timezone.now() + timedelta(minutes=15),
        )

        self.other_user.delete()

        enrolment.refresh_from_db()
        self.assertIsNone(enrolment.created_by)
        self.assertIsNotNone(enrolment.revoked_at)

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
