from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from bakerydemo.account_security.models import (
    FastIdUserLink,
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


class FastIdUserLinkTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="fast-id-user")
        self.other_user = get_user_model().objects.create_user(
            username="other-fast-id-user"
        )

    def test_link_belongs_to_one_user_and_registration_is_initially_unset(self):
        link = FastIdUserLink.objects.create(
            user=self.user,
            tenant_key="tenant-a",
            external_user_id="external-1",
        )

        self.assertEqual(self.user.fast_id_link, link)
        self.assertIsNone(link.registered_at)
        self.assertIsNotNone(link.created_at)
        self.assertIsNotNone(link.updated_at)

    def test_user_can_have_only_one_fast_id_link(self):
        FastIdUserLink.objects.create(
            user=self.user,
            tenant_key="tenant-a",
            external_user_id="external-1",
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            FastIdUserLink.objects.create(
                user=self.user,
                tenant_key="tenant-b",
                external_user_id="external-2",
            )

    def test_external_user_is_unique_within_tenant(self):
        FastIdUserLink.objects.create(
            user=self.user,
            tenant_key="tenant-a",
            external_user_id="external-1",
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            FastIdUserLink.objects.create(
                user=self.other_user,
                tenant_key="tenant-a",
                external_user_id="external-1",
            )

        other_tenant = FastIdUserLink.objects.create(
            user=self.other_user,
            tenant_key="tenant-b",
            external_user_id="external-1",
        )
        self.assertEqual(other_tenant.tenant_key, "tenant-b")

    def test_deleting_user_deletes_fast_id_link(self):
        FastIdUserLink.objects.create(
            user=self.user,
            tenant_key="tenant-a",
            external_user_id="external-1",
        )

        self.user.delete()

        self.assertFalse(FastIdUserLink.objects.exists())
