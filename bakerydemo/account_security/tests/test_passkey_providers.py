from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase, override_settings
from django.utils import timezone

from bakerydemo.account_security.fast_id import FastIdAuthenticationResult, FastIdError
from bakerydemo.account_security.models import (
    FastIdUserLink,
    PasskeyCredential,
    PasskeyEnrolment,
)
from bakerydemo.account_security.passkey_providers import (
    FastIdPasskeyProvider,
    LocalPasskeyProvider,
    get_passkey_provider,
)
from bakerydemo.account_security.passkeys import PasskeyCeremonyError

FAST_ID_SETTINGS = {
    "FAST_ID_ENABLED": True,
    "FAST_ID_TENANT_KEY": "tenant-key",
    "ACCOUNT_SECURITY_WEBAUTHN_RP_ID": "example.com",
    "ACCOUNT_SECURITY_WEBAUTHN_RP_NAME": "SEMI E187",
}


class FakeFastIdClient:
    def __init__(self, *, users=None, external_user_id="external-1"):
        self.users = users or []
        self.external_user_id = external_user_id
        self.created_users = []
        self.deleted_user_ids = []
        self.registration_payload = None
        self.authentication_payload = None

    def list_users(self):
        return self.users

    def create_user(self, email, name):
        self.created_users.append({"email": email, "name": name})
        return {
            "id": self.external_user_id,
            "email": email,
            "name": name,
            "enabled": True,
        }

    def issue_user_token(self, user_id):
        return f"token-for-{user_id}"

    def delete_user(self, user_id):
        self.deleted_user_ids.append(user_id)
        return True

    def registration_initialize(self, user_token):
        return {
            "challenge": "registration-challenge",
            "user": {"id": "opaque-user-handle"},
        }

    def registration_finalize(self, user_token, credential):
        self.registration_payload = credential
        return True

    def authentication_initialize(self):
        return {"challenge": "authentication-challenge"}

    def authentication_finalize(self, credential):
        self.authentication_payload = credential
        return FastIdAuthenticationResult(
            external_user_id=self.external_user_id,
        )


class ProviderSelectionTests(TestCase):
    @override_settings(FAST_ID_ENABLED=False)
    def test_feature_flag_off_selects_local_provider(self):
        self.assertIsInstance(get_passkey_provider(), LocalPasskeyProvider)

    @override_settings(FAST_ID_ENABLED=True)
    def test_feature_flag_on_selects_fast_id_provider(self):
        self.assertIsInstance(
            get_passkey_provider(client=FakeFastIdClient()),
            FastIdPasskeyProvider,
        )


@override_settings(
    FAST_ID_ENABLED=False,
    ACCOUNT_SECURITY_WEBAUTHN_RP_ID="example.com",
    ACCOUNT_SECURITY_WEBAUTHN_RP_NAME="SEMI E187",
)
class LocalPasskeyProviderTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="Local User",
            email="local@example.com",
            password="Local-Password-1!",
            is_active=True,
            is_staff=True,
        )
        self.enrolment = PasskeyEnrolment.objects.create(
            user=self.user,
            code_digest="b" * 64,
            disable_password_on_success=False,
            expires_at=timezone.now() + timezone.timedelta(minutes=5),
        )

    def test_start_operations_return_provider_tagged_serializable_state(self):
        provider = LocalPasskeyProvider()

        registration = provider.start_registration(self.user)
        authentication = provider.start_authentication()

        self.assertEqual(registration.state["provider"], "local")
        self.assertEqual(
            registration.state["challenge"], registration.options["challenge"]
        )
        self.assertEqual(
            registration.state["user_handle"], registration.options["user"]["id"]
        )
        self.assertEqual(authentication.state["provider"], "local")
        self.assertEqual(
            authentication.state["challenge"], authentication.options["challenge"]
        )

    def test_registration_result_exposes_local_credential_for_audit(self):
        credential = PasskeyCredential.objects.create(
            user=self.user,
            credential_id="credential-id",
            credential_public_key=b"public-key",
            user_handle=b"user-handle",
        )
        provider = LocalPasskeyProvider()

        with patch(
            "bakerydemo.account_security.passkey_providers.complete_registration",
            return_value=credential,
        ):
            result = provider.finish_registration(
                self.user,
                self.enrolment,
                {"id": "credential-id"},
                {
                    "provider": "local",
                    "challenge": "Y2hhbGxlbmdl",
                    "user_handle": "dXNlci1oYW5kbGU",
                },
            )

        self.assertEqual(result.user, self.user)
        self.assertEqual(result.credential, credential)

    def test_authentication_result_exposes_existing_local_credential(self):
        credential = PasskeyCredential.objects.create(
            user=self.user,
            credential_id="authentication-credential-id",
            credential_public_key=b"public-key",
            user_handle=b"user-handle",
        )
        provider = LocalPasskeyProvider()

        with patch(
            "bakerydemo.account_security.passkey_providers.verify_login_credential",
            return_value=credential,
        ):
            result = provider.finish_authentication(
                {"id": credential.credential_id},
                {"provider": "local", "challenge": "Y2hhbGxlbmdl"},
            )

        self.assertEqual(result.user, self.user)
        self.assertEqual(result.credential, credential)


@override_settings(**FAST_ID_SETTINGS)
class FastIdPasskeyProviderTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="Display Name",
            email="Person@Example.com",
            password="Still-Usable-Password-1!",
            is_active=True,
            is_staff=True,
        )
        self.enrolment = PasskeyEnrolment.objects.create(
            user=self.user,
            code_digest="a" * 64,
            disable_password_on_success=True,
            expires_at=timezone.now() + timezone.timedelta(minutes=5),
        )

    def provider(self, users=None, *, external_user_id="external-1"):
        client = FakeFastIdClient(
            users=users,
            external_user_id=external_user_id,
        )
        return FastIdPasskeyProvider(client=client), client

    def test_provision_user_creates_missing_tenant_user_and_link(self):
        provider, client = self.provider(users=[])

        link = provider.provision_user(self.user)

        self.assertEqual(
            client.created_users,
            [
                {
                    "email": "person@example.com",
                    "name": "Display Name",
                }
            ],
        )
        self.assertEqual(link.user, self.user)
        self.assertEqual(link.tenant_key, "tenant-key")
        self.assertEqual(link.external_user_id, "external-1")

    def test_provision_user_rejects_mismatched_created_email(self):
        class MismatchedCreationClient(FakeFastIdClient):
            def create_user(self, email, name):
                created = super().create_user(email, name)
                created["email"] = "different@example.com"
                return created

        client = MismatchedCreationClient(users=[])
        provider = FastIdPasskeyProvider(client=client)

        with self.assertRaises(PasskeyCeremonyError) as caught:
            provider.provision_user(self.user)

        self.assertEqual(str(caught.exception), "fast_id_user_mismatch")
        self.assertEqual(client.deleted_user_ids, [])
        self.assertFalse(FastIdUserLink.objects.filter(user=self.user).exists())

    def test_provision_user_rejects_pre_existing_remote_user(self):
        provider, client = self.provider(
            users=[
                {
                    "id": "existing-external-user",
                    "email": "person@example.com",
                    "enabled": True,
                }
            ]
        )

        with self.assertRaises(PasskeyCeremonyError) as caught:
            provider.provision_user(self.user)

        self.assertEqual(str(caught.exception), "fast_id_user_exists")
        self.assertEqual(client.created_users, [])
        self.assertFalse(FastIdUserLink.objects.filter(user=self.user).exists())

    def test_provision_user_removes_remote_user_if_link_cannot_be_saved(self):
        provider, client = self.provider(users=[])

        with (
            patch.object(
                FastIdUserLink.objects,
                "create",
                side_effect=IntegrityError("link could not be saved"),
            ),
            self.assertRaises(PasskeyCeremonyError) as caught,
        ):
            provider.provision_user(self.user)

        self.assertEqual(str(caught.exception), "fast_id_link_conflict")
        self.assertEqual(client.deleted_user_ids, ["external-1"])

    def test_provisioning_cleanup_log_does_not_include_remote_exception(self):
        class FailingCleanupClient(FakeFastIdClient):
            def delete_user(self, user_id):
                try:
                    raise RuntimeError("client-secret management-token")
                except RuntimeError as exc:
                    raise FastIdError("remote_unavailable") from exc

        client = FailingCleanupClient(users=[])
        provider = FastIdPasskeyProvider(client=client)

        with (
            patch.object(
                FastIdUserLink.objects,
                "create",
                side_effect=IntegrityError("link could not be saved"),
            ),
            self.assertLogs(
                "bakerydemo.account_security.passkey_providers",
                level="ERROR",
            ) as captured,
            self.assertRaises(PasskeyCeremonyError),
        ):
            provider.provision_user(self.user)

        log_output = "\n".join(captured.output)
        self.assertNotIn("client-secret", log_output)
        self.assertNotIn("management-token", log_output)

    def test_registration_rejects_missing_remote_user_without_creating_one(self):
        provider, client = self.provider(users=[])

        with self.assertRaises(PasskeyCeremonyError) as caught:
            provider.start_registration(self.user)

        self.assertEqual(str(caught.exception), "fast_id_user_not_found")
        self.assertEqual(client.created_users, [])

    def test_deprovision_user_deletes_linked_tenant_user(self):
        FastIdUserLink.objects.create(
            user=self.user,
            tenant_key="tenant-key",
            external_user_id="external-1",
        )
        provider, client = self.provider()

        provider.deprovision_user(self.user)

        self.assertEqual(client.deleted_user_ids, ["external-1"])
        self.assertTrue(FastIdUserLink.objects.filter(user=self.user).exists())

    def test_deprovision_user_without_link_does_not_call_fast_id(self):
        provider, client = self.provider()

        provider.deprovision_user(self.user)

        self.assertEqual(client.deleted_user_ids, [])

    def test_deprovision_user_rejects_link_from_another_tenant(self):
        FastIdUserLink.objects.create(
            user=self.user,
            tenant_key="other-tenant",
            external_user_id="external-1",
        )
        provider, client = self.provider()

        with self.assertRaises(PasskeyCeremonyError) as caught:
            provider.deprovision_user(self.user)

        self.assertEqual(str(caught.exception), "fast_id_link_mismatch")
        self.assertEqual(client.deleted_user_ids, [])

    def test_registration_matches_normalized_email_and_preserves_password(self):
        provider, client = self.provider(
            users=[
                {
                    "id": "external-1",
                    "email": "  person@example.COM ",
                    "name": "Person",
                    "enabled": True,
                }
            ]
        )

        started = provider.start_registration(self.user)
        result = provider.finish_registration(
            self.user,
            self.enrolment,
            {
                "id": "credential-id",
                "type": "public-key",
                "token": "browser-supplied-token",
            },
            started.state,
        )

        link = FastIdUserLink.objects.get(user=self.user)
        self.enrolment.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(started.options["challenge"], "registration-challenge")
        self.assertEqual(started.state["provider"], "fast_id")
        self.assertEqual(started.state["user_token"], "token-for-external-1")
        self.assertEqual(result.user, self.user)
        self.assertEqual(link.external_user_id, "external-1")
        self.assertIsNotNone(link.registered_at)
        self.assertIsNotNone(self.enrolment.consumed_at)
        self.assertTrue(self.user.has_usable_password())
        self.assertEqual(client.created_users, [])
        self.assertNotIn("token", client.registration_payload)

    def test_registration_rejects_ambiguous_or_invalid_email_match(self):
        cases = (
            (
                [
                    {"id": "external-1", "email": "person@example.com"},
                    {"id": "external-2", "email": "PERSON@example.com"},
                ],
                "fast_id_user_ambiguous",
            ),
            (
                [{"id": "", "email": "person@example.com"}],
                "fast_id_user_invalid",
            ),
            (
                [
                    {
                        "id": "external-1",
                        "email": "person@example.com",
                        "enabled": False,
                    }
                ],
                "fast_id_user_inactive",
            ),
        )

        for users, expected_reason in cases:
            with self.subTest(reason=expected_reason):
                provider, _client = self.provider(users=users)
                with self.assertRaises(PasskeyCeremonyError) as caught:
                    provider.start_registration(self.user)
                self.assertEqual(str(caught.exception), expected_reason)

    def test_registration_rejects_link_from_another_tenant(self):
        FastIdUserLink.objects.create(
            user=self.user,
            tenant_key="other-tenant",
            external_user_id="external-1",
        )
        provider, _client = self.provider()

        with self.assertRaises(PasskeyCeremonyError) as caught:
            provider.start_registration(self.user)

        self.assertEqual(str(caught.exception), "fast_id_link_mismatch")

    def test_registration_rejects_link_that_no_longer_matches_remote_email(self):
        FastIdUserLink.objects.create(
            user=self.user,
            tenant_key="tenant-key",
            external_user_id="stale-external-id",
        )
        provider, client = self.provider(
            users=[
                {
                    "id": "external-1",
                    "email": "person@example.com",
                    "enabled": True,
                }
            ]
        )

        with self.assertRaises(PasskeyCeremonyError) as caught:
            provider.start_registration(self.user)

        self.assertEqual(str(caught.exception), "fast_id_link_mismatch")
        self.assertEqual(client.created_users, [])

    def test_provisioning_does_not_create_duplicate_for_stale_link(self):
        FastIdUserLink.objects.create(
            user=self.user,
            tenant_key="tenant-key",
            external_user_id="stale-external-id",
        )
        provider, client = self.provider(
            users=[
                {
                    "id": "external-2",
                    "email": "other@example.com",
                    "enabled": True,
                }
            ]
        )

        with self.assertRaises(PasskeyCeremonyError) as caught:
            provider.provision_user(self.user)

        self.assertEqual(str(caught.exception), "fast_id_link_mismatch")
        self.assertEqual(client.created_users, [])

    def test_finish_registration_rejects_provider_mismatch(self):
        provider, _client = self.provider()

        with self.assertRaises(PasskeyCeremonyError) as caught:
            provider.finish_registration(
                self.user,
                self.enrolment,
                {"id": "credential-id"},
                {"provider": "local"},
            )

        self.assertEqual(str(caught.exception), "provider_mismatch")

    def test_authentication_maps_verified_subject_and_ignores_browser_token(self):
        FastIdUserLink.objects.create(
            user=self.user,
            tenant_key="tenant-key",
            external_user_id="external-1",
            registered_at=timezone.now(),
        )
        provider, client = self.provider()

        started = provider.start_authentication()
        result = provider.finish_authentication(
            {
                "id": "credential-id",
                "type": "public-key",
                "token": "browser-supplied-token",
            },
            started.state,
        )

        self.assertEqual(started.state, {"provider": "fast_id"})
        self.assertEqual(result.user, self.user)
        self.assertIsNone(result.credential)
        self.assertNotIn("token", client.authentication_payload)

    def test_authentication_rejects_unknown_or_ineligible_local_user(self):
        cases = (
            ("missing", True, True, "fast_id_user_not_found"),
            ("external-1", False, True, "inactive_user"),
            ("external-1", True, False, "inactive_user"),
        )

        for external_id, is_active, is_staff, expected_reason in cases:
            with self.subTest(reason=expected_reason, external_id=external_id):
                self.user.is_active = is_active
                self.user.is_staff = is_staff
                self.user.save(update_fields=["is_active", "is_staff"])
                FastIdUserLink.objects.update_or_create(
                    user=self.user,
                    defaults={
                        "tenant_key": "tenant-key",
                        "external_user_id": "external-1",
                        "registered_at": timezone.now(),
                    },
                )
                provider, _client = self.provider(external_user_id=external_id)

                with self.assertRaises(PasskeyCeremonyError) as caught:
                    provider.finish_authentication(
                        {"id": "credential-id"},
                        {"provider": "fast_id"},
                    )

                self.assertEqual(str(caught.exception), expected_reason)
