from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class BootstrapExistingUsersMigrationTests(TransactionTestCase):
    migrate_from = [("account_security", "0001_initial")]
    migrate_to = [("account_security", "0002_bootstrap_existing_users")]

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        old_apps = executor.loader.project_state(self.migrate_from).apps
        User = old_apps.get_model("auth", "User")
        self.user = User.objects.create(
            username="existing-editor",
            password="pbkdf2_sha256$test$current-encoded-hash",
            is_staff=True,
        )

        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        self.apps = executor.loader.project_state(self.migrate_to).apps

    def test_existing_user_gets_non_forced_state_and_current_history(self):
        State = self.apps.get_model("account_security", "UserSecurityState")
        History = self.apps.get_model("account_security", "PasswordHistory")
        state = State.objects.get(user_id=self.user.pk)

        self.assertFalse(state.must_change_password)
        self.assertIsNotNone(state.password_changed_at)
        self.assertEqual(
            History.objects.get(user_id=self.user.pk).encoded_password,
            "pbkdf2_sha256$test$current-encoded-hash",
        )
