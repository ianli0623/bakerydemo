from unittest.mock import patch
from urllib.parse import urlencode

from django.contrib.auth import get_user_model
from django.db import DatabaseError
from django.test import TestCase, override_settings
from django.urls import reverse

from bakerydemo.account_security.fast_id import FastIdError
from bakerydemo.account_security.models import FastIdUserLink
from bakerydemo.account_security.services import sync_password_change

PASSKEY_CLEANUP_REMINDER = (
    "刪除帳號後，請至 Windows「設定 → 帳戶 → Passkeys」刪除 "
    "lularm.com 金鑰，避免日後出現重複金鑰。"
)
FAST_ID_REMOTE_DELETION_WARNING = (
    "刪除此帳號也會永久刪除 Fast-ID Tenant User 與伺服器端憑證。"
)


class DeletionClient:
    def __init__(self, *, error=None):
        self.error = error
        self.deleted_user_ids = []

    def delete_user(self, user_id):
        self.deleted_user_ids.append(user_id)
        if self.error is not None:
            raise self.error
        return True


class UserDeletionTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="Current-Password-1!",
        )
        sync_password_change(self.admin, must_change_password=False)
        self.client.force_login(self.admin)

    def create_target(self, *, linked=True, username="target"):
        user = get_user_model().objects.create_user(
            username=username,
            email=f"{username}@example.com",
            is_staff=True,
        )
        if linked:
            FastIdUserLink.objects.create(
                user=user,
                tenant_key="tenant-key",
                external_user_id=f"external-{username}",
            )
        return user

    @override_settings(FAST_ID_ENABLED=True, FAST_ID_TENANT_KEY="tenant-key")
    def test_single_delete_confirmation_reminds_about_device_passkey(self):
        target = self.create_target()

        response = self.client.get(
            reverse("wagtailusers_users:delete", args=[target.pk])
        )

        self.assertContains(response, PASSKEY_CLEANUP_REMINDER)
        self.assertContains(response, FAST_ID_REMOTE_DELETION_WARNING)

    @override_settings(FAST_ID_ENABLED=True, FAST_ID_TENANT_KEY="tenant-key")
    def test_single_delete_success_reminds_about_device_passkey(self):
        target = self.create_target()
        fast_id_client = DeletionClient()

        with patch(
            "bakerydemo.account_security.passkey_providers.FastIdClient.from_settings",
            return_value=fast_id_client,
        ):
            response = self.client.post(
                reverse("wagtailusers_users:delete", args=[target.pk]),
                follow=True,
            )

        self.assertContains(response, PASSKEY_CLEANUP_REMINDER)

    @override_settings(FAST_ID_ENABLED=True, FAST_ID_TENANT_KEY="tenant-key")
    def test_single_delete_confirmation_omits_passkey_reminder_for_local_user(self):
        target = self.create_target(linked=False)

        response = self.client.get(
            reverse("wagtailusers_users:delete", args=[target.pk])
        )

        self.assertNotContains(response, PASSKEY_CLEANUP_REMINDER)

    @override_settings(FAST_ID_ENABLED=True, FAST_ID_TENANT_KEY="tenant-key")
    def test_single_delete_removes_fast_id_user_before_local_user(self):
        target = self.create_target()
        fast_id_client = DeletionClient()

        with patch(
            "bakerydemo.account_security.passkey_providers.FastIdClient.from_settings",
            return_value=fast_id_client,
        ):
            response = self.client.post(
                reverse("wagtailusers_users:delete", args=[target.pk])
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(fast_id_client.deleted_user_ids, ["external-target"])
        self.assertFalse(get_user_model().objects.filter(pk=target.pk).exists())
        self.assertFalse(FastIdUserLink.objects.filter(user_id=target.pk).exists())

    @override_settings(FAST_ID_ENABLED=True, FAST_ID_TENANT_KEY="tenant-key")
    def test_single_delete_keeps_local_user_when_fast_id_fails(self):
        target = self.create_target()
        fast_id_client = DeletionClient(error=FastIdError("remote_unavailable"))

        with patch(
            "bakerydemo.account_security.passkey_providers.FastIdClient.from_settings",
            return_value=fast_id_client,
        ):
            response = self.client.post(
                reverse("wagtailusers_users:delete", args=[target.pk])
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "無法刪除 Fast-ID 帳號，本機使用者已保留。",
        )
        self.assertTrue(get_user_model().objects.filter(pk=target.pk).exists())
        self.assertTrue(FastIdUserLink.objects.filter(user_id=target.pk).exists())

    @override_settings(FAST_ID_ENABLED=True, FAST_ID_TENANT_KEY="tenant-key")
    def test_single_delete_without_fast_id_link_uses_local_delete(self):
        target = self.create_target(linked=False)

        with patch(
            "bakerydemo.account_security.passkey_providers.FastIdClient.from_settings"
        ) as client_factory:
            response = self.client.post(
                reverse("wagtailusers_users:delete", args=[target.pk])
            )

        self.assertEqual(response.status_code, 302)
        client_factory.assert_not_called()
        self.assertFalse(get_user_model().objects.filter(pk=target.pk).exists())

    @override_settings(FAST_ID_ENABLED=False, FAST_ID_TENANT_KEY="tenant-key")
    def test_single_delete_with_feature_disabled_keeps_linked_user(self):
        target = self.create_target()

        with patch(
            "bakerydemo.account_security.passkey_providers.FastIdClient.from_settings"
        ) as client_factory:
            response = self.client.post(
                reverse("wagtailusers_users:delete", args=[target.pk])
            )

        self.assertEqual(response.status_code, 200)
        client_factory.assert_not_called()
        self.assertContains(
            response,
            "Fast-ID 已停用，無法安全刪除已連結的帳號。請先啟用 Fast-ID。",
        )
        self.assertTrue(get_user_model().objects.filter(pk=target.pk).exists())

    @override_settings(FAST_ID_ENABLED=False, FAST_ID_TENANT_KEY="tenant-key")
    def test_single_delete_with_feature_disabled_hides_delete_button(self):
        target = self.create_target()

        response = self.client.get(
            reverse("wagtailusers_users:delete", args=[target.pk])
        )

        self.assertContains(
            response,
            "Fast-ID 已停用，無法安全刪除已連結的帳號。請先啟用 Fast-ID。",
        )
        self.assertNotContains(
            response,
            '<button type="submit" class="button serious">',
        )

    @override_settings(FAST_ID_ENABLED=True, FAST_ID_TENANT_KEY="tenant-key")
    def test_local_delete_failure_leaves_linked_user_inactive_for_safe_retry(self):
        target = self.create_target()
        fast_id_client = DeletionClient()

        with (
            patch(
                "bakerydemo.account_security.passkey_providers.FastIdClient.from_settings",
                return_value=fast_id_client,
            ),
            patch(
                "wagtail.admin.views.generic.models.DeleteView.delete_action",
                side_effect=DatabaseError("local delete failed"),
            ),
        ):
            response = self.client.post(
                reverse("wagtailusers_users:delete", args=[target.pk])
            )

        target.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(fast_id_client.deleted_user_ids, ["external-target"])
        self.assertFalse(target.is_active)
        self.assertTrue(FastIdUserLink.objects.filter(user=target).exists())
        self.assertContains(
            response,
            "Fast-ID 帳號已刪除，但本機帳號未能移除，並已停用。請再試一次。",
        )

    def bulk_delete_url(self, users):
        user_model = get_user_model()
        query = urlencode(
            {
                "id": [user.pk for user in users],
                "next": reverse("wagtailusers_users:index"),
            },
            doseq=True,
        )
        return (
            reverse(
                "wagtail_bulk_action",
                args=(
                    user_model._meta.app_label,
                    user_model._meta.model_name,
                    "delete",
                ),
            )
            + f"?{query}"
        )

    @override_settings(FAST_ID_ENABLED=True, FAST_ID_TENANT_KEY="tenant-key")
    def test_bulk_delete_is_blocked_when_selection_contains_fast_id_user(self):
        linked = self.create_target(username="linked")
        local = self.create_target(linked=False, username="local")
        url = self.bulk_delete_url([linked, local])

        confirmation = self.client.get(url)

        self.assertEqual(confirmation.status_code, 200)
        self.assertContains(
            confirmation,
            "已連結 Fast-ID 的使用者無法批次刪除，請逐一刪除。",
        )
        self.assertNotContains(
            confirmation,
            '<button type="submit" class="button serious">',
        )

        response = self.client.post(url, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(get_user_model().objects.filter(pk=linked.pk).exists())
        self.assertTrue(get_user_model().objects.filter(pk=local.pk).exists())

    @override_settings(FAST_ID_ENABLED=True, FAST_ID_TENANT_KEY="tenant-key")
    def test_bulk_delete_checks_fast_id_users_without_delete_permission(self):
        FastIdUserLink.objects.create(
            user=self.admin,
            tenant_key="tenant-key",
            external_user_id="external-admin",
        )
        local = self.create_target(linked=False, username="local")
        url = self.bulk_delete_url([self.admin, local])

        confirmation = self.client.get(url)

        self.assertContains(
            confirmation,
            "已連結 Fast-ID 的使用者無法批次刪除，請逐一刪除。",
        )
        self.assertNotContains(
            confirmation,
            '<button type="submit" class="button serious">',
        )

        self.client.post(url)

        self.assertTrue(get_user_model().objects.filter(pk=local.pk).exists())

    @override_settings(FAST_ID_ENABLED=True, FAST_ID_TENANT_KEY="tenant-key")
    def test_bulk_delete_still_deletes_unlinked_users(self):
        first = self.create_target(linked=False, username="first")
        second = self.create_target(linked=False, username="second")

        response = self.client.post(self.bulk_delete_url([first, second]))

        self.assertEqual(response.status_code, 302)
        self.assertFalse(get_user_model().objects.filter(pk=first.pk).exists())
        self.assertFalse(get_user_model().objects.filter(pk=second.pk).exists())

    @override_settings(FAST_ID_ENABLED=False, FAST_ID_TENANT_KEY="tenant-key")
    def test_bulk_delete_is_blocked_for_linked_user_when_feature_is_disabled(self):
        linked = self.create_target(username="linked-disabled")
        response = self.client.post(self.bulk_delete_url([linked]))

        self.assertEqual(response.status_code, 302)
        self.assertTrue(get_user_model().objects.filter(pk=linked.pk).exists())
