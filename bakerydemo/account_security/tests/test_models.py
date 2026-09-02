from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import TestCase

from bakerydemo.account_security.models import PasswordHistory, UserSecurityState


class AccountSecurityModelTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="editor", password="Initial-Password-1!"
        )
        UserSecurityState.objects.filter(user=self.user).delete()
        PasswordHistory.objects.filter(user=self.user).delete()

    def test_security_state_defaults_fail_closed(self):
        state = UserSecurityState.objects.create(user=self.user)

        self.assertTrue(state.must_change_password)
        self.assertIsNone(state.password_changed_at)

    def test_password_history_is_newest_first(self):
        older = PasswordHistory.objects.create(
            user=self.user, encoded_password="older-hash"
        )
        newer = PasswordHistory.objects.create(
            user=self.user, encoded_password="newer-hash"
        )

        self.assertEqual(
            list(self.user.password_history.values_list("pk", flat=True)),
            [newer.pk, older.pk],
        )

    def test_password_history_is_not_exposed_in_django_admin(self):
        self.assertFalse(admin.site.is_registered(PasswordHistory))
