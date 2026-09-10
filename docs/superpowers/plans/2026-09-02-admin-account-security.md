# 後台帳號與密碼安全 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 為 Wagtail 與 Django 兩個後台入口加入首次強制改密碼、HTTPS 傳輸、5 次失敗鎖定 15 分鐘、12 字元複雜度、90 天效期及最近 3 組密碼不可重複。

**Architecture:** 使用 `django-axes` 的資料庫 handler 統一追蹤兩個登入入口的帳號失敗次數；新增獨立 `bakerydemo.account_security` app 管理安全狀態、密碼歷程、驗證器、交易式改密碼服務、共用頁面與攔截 middleware。保留 Django 內建 User，不修改 Wagtail 或 Django 核心程式。

**Tech Stack:** Python 3.12+、Django 6.0、Wagtail 7.4、django-axes 8.3、Django ORM／middleware／password validators、Django TestCase。

**Spec:** `docs/superpowers/specs/2026-09-02-admin-account-security-design.md`

## Global Constraints

- 保留 `Django>=6.0,<6.1` 與 `wagtail>=7.4,<7.5`；新增 `django-axes[ipware]>=8.3.1,<9`，不可降級 Django 或 Wagtail。
- 同一正規化帳號名稱連續失敗 5 次鎖定 15 分鐘，跨 IP 累積，成功登入後清零。
- 密碼至少 12 字元，且包含 ASCII 英文大寫、ASCII 英文小寫、數字及至少一個非字母數字、非空白的符號。
- 密碼效期固定 90 天；新帳號與管理員重設後 `must_change_password=True`。
- 每位使用者最多保留最近 3 組編碼密碼雜湊，候選密碼不得與其中任一相同。
- 正式環境強制 HTTPS、Secure session Cookie、Secure CSRF Cookie 與 HSTS；dev/test 的 localhost 保留 HTTP。
- 密碼明文不可寫入資料庫、log、錯誤訊息、表單回顯或管理介面；PasswordHistory 不註冊後台。
- 自訂訊息以英文作為 gettext source，提供 `zh_Hant` 翻譯。
- 現有工作樹含其他使用者修改；每次只 stage 本任務列出的檔案，不可把既有 Nuxt／API 修改帶入提交。
- 所有 render 測試使用 `DJANGO_SETTINGS_MODULE=bakerydemo.settings.test`，避免 dev manifest-staticfiles 問題。

---

## File Map

新增 app 的責任分界：

- `bakerydemo/account_security/models.py`：只定義安全狀態與密碼歷程資料。
- `bakerydemo/account_security/validators.py`：只做候選密碼的複雜度與歷程驗證。
- `bakerydemo/account_security/services.py`：交易式設定密碼、歷程裁切、效期判斷與安全狀態建立。
- `bakerydemo/account_security/signals.py`：偵測 Wagtail／Django 管理表單造成的 User 密碼雜湊變更，標示臨時密碼並記錄歷程。
- `bakerydemo/account_security/forms.py`：共用改密碼表單與兩種後台登入表單的通用錯誤訊息。
- `bakerydemo/account_security/views.py`：共用改密碼與 Axes 鎖定回應。
- `bakerydemo/account_security/middleware.py`：限制臨時／過期密碼使用者，並把既有後台改密碼入口導向共用頁。
- `bakerydemo/account_security/checks.py`：正式環境初始密碼與 HTTPS 設定檢查。
- `bakerydemo/account_security/urls.py`：安全改密碼 URL。
- `bakerydemo/account_security/templates/account_security/`：獨立、安全且可翻譯的改密碼與鎖定頁。
- `bakerydemo/account_security/locale/zh_Hant/LC_MESSAGES/`：繁體中文翻譯。
- `bakerydemo/account_security/tests/`：依責任拆開的單元、整合、migration 與設定測試。

---

### Task 1: 建立安全狀態與密碼歷程資料模型

**Files:**
- Create: `bakerydemo/account_security/__init__.py`
- Create: `bakerydemo/account_security/apps.py`
- Create: `bakerydemo/account_security/models.py`
- Create: `bakerydemo/account_security/migrations/__init__.py`
- Create: `bakerydemo/account_security/migrations/0001_initial.py`
- Create: `bakerydemo/account_security/tests/__init__.py`
- Create: `bakerydemo/account_security/tests/test_models.py`
- Modify: `bakerydemo/settings/base.py:39-77`

**Interfaces:**
- Consumes: `settings.AUTH_USER_MODEL` 與 Django ORM。
- Produces: `UserSecurityState`, `PasswordHistory`, related names `account_security_state` 與 `password_history`。

- [ ] **Step 1: 寫出模型預設值與排序的失敗測試**

```python
# bakerydemo/account_security/tests/test_models.py
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
```

- [ ] **Step 2: 執行測試並確認因 app／模型不存在而失敗**

Run: `env DJANGO_SETTINGS_MODULE=bakerydemo.settings.test ./manage.py test bakerydemo.account_security.tests.test_models`

Expected: FAIL，錯誤包含 `ModuleNotFoundError: No module named 'bakerydemo.account_security'`。

- [ ] **Step 3: 建立 app、模型與初始 migration**

```python
# bakerydemo/account_security/apps.py
from django.apps import AppConfig


class AccountSecurityConfig(AppConfig):
    default_auto_field = "django.db.models.AutoField"
    name = "bakerydemo.account_security"
    verbose_name = "Account security"
```

```python
# bakerydemo/account_security/models.py
from django.conf import settings
from django.db import models


class UserSecurityState(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="account_security_state",
    )
    must_change_password = models.BooleanField(default=True)
    password_changed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class PasswordHistory(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="password_history",
    )
    encoded_password = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        indexes = [models.Index(fields=["user", "-created_at"])]
```

在 `INSTALLED_APPS` 的專案 app 區加入：

```python
"bakerydemo.account_security.apps.AccountSecurityConfig",
```

Run: `./manage.py makemigrations account_security`

Expected: 產生 `0001_initial.py`，含 swappable user dependency、兩個 model 與 user/created_at index。

- [ ] **Step 4: 執行 migration 檢查與模型測試**

Run: `./manage.py makemigrations --check --dry-run`

Expected: `No changes detected`。

Run: `env DJANGO_SETTINGS_MODULE=bakerydemo.settings.test ./manage.py test bakerydemo.account_security.tests.test_models`

Expected: PASS，2 tests。

- [ ] **Step 5: 提交模型基礎**

```bash
git add bakerydemo/account_security/__init__.py bakerydemo/account_security/apps.py bakerydemo/account_security/models.py bakerydemo/account_security/migrations bakerydemo/account_security/tests/__init__.py bakerydemo/account_security/tests/test_models.py bakerydemo/settings/base.py
git commit -m "feat: add account security models"
```

---

### Task 2: 加入密碼複雜度與最近三組歷程驗證器

**Files:**
- Create: `bakerydemo/account_security/validators.py`
- Create: `bakerydemo/account_security/tests/test_validators.py`
- Modify: `bakerydemo/settings/base.py:142-157`

**Interfaces:**
- Consumes: `PasswordHistory`, Django `check_password`, `validate_password` user argument。
- Produces: `PasswordComplexityValidator.validate(password, user=None)`, `PasswordHistoryValidator.validate(password, user=None)`。

- [ ] **Step 1: 寫出複雜度與歷程的參數化失敗測試**

```python
# bakerydemo/account_security/tests/test_validators.py
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core.exceptions import ValidationError
from django.test import TestCase

from bakerydemo.account_security.models import PasswordHistory
from bakerydemo.account_security.validators import (
    PasswordComplexityValidator,
    PasswordHistoryValidator,
)


class PasswordComplexityValidatorTests(TestCase):
    def test_requires_each_character_class(self):
        invalid_passwords = {
            "short": "Aa1!short",
            "uppercase": "lowercase-123!",
            "lowercase": "UPPERCASE-123!",
            "number": "NoNumbersHere!",
            "symbol": "NoSymbols1234",
        }
        validator = PasswordComplexityValidator()

        for expected_code, password in invalid_passwords.items():
            with self.subTest(expected_code=expected_code):
                with self.assertRaises(ValidationError) as error:
                    validator.validate(password)
                self.assertIn(expected_code, {item.code for item in error.exception.error_list})

    def test_accepts_a_valid_password(self):
        PasswordComplexityValidator().validate("Valid-Password-1!")


class PasswordHistoryValidatorTests(TestCase):
    def test_rejects_any_of_the_three_most_recent_passwords(self):
        user = get_user_model().objects.create_user(username="editor")
        for password in ("History-One-1!", "History-Two-2!", "History-Three-3!"):
            PasswordHistory.objects.create(
                user=user, encoded_password=make_password(password)
            )

        with self.assertRaisesMessage(ValidationError, "recently used"):
            PasswordHistoryValidator().validate("History-Two-2!", user)

    def test_ignores_a_fourth_older_password(self):
        user = get_user_model().objects.create_user(username="editor")
        PasswordHistory.objects.create(
            user=user, encoded_password=make_password("Old-Enough-Password-1!")
        )
        for password in ("Recent-One-1!", "Recent-Two-2!", "Recent-Three-3!"):
            PasswordHistory.objects.create(
                user=user, encoded_password=make_password(password)
            )

        PasswordHistoryValidator().validate("Old-Enough-Password-1!", user)
```

- [ ] **Step 2: 執行測試並確認 validators 尚不存在**

Run: `env DJANGO_SETTINGS_MODULE=bakerydemo.settings.test ./manage.py test bakerydemo.account_security.tests.test_validators`

Expected: FAIL，錯誤包含 `No module named 'bakerydemo.account_security.validators'`。

- [ ] **Step 3: 實作兩個 validator 並提供穩定錯誤碼**

```python
# bakerydemo/account_security/validators.py
import re

from django.contrib.auth.hashers import check_password
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from .models import PasswordHistory


class PasswordComplexityValidator:
    minimum_length = 12

    def validate(self, password, user=None):
        errors = []
        checks = (
            (len(password) >= self.minimum_length, "short", _("The password must contain at least 12 characters.")),
            (bool(re.search(r"[A-Z]", password)), "uppercase", _("The password must contain an uppercase English letter.")),
            (bool(re.search(r"[a-z]", password)), "lowercase", _("The password must contain a lowercase English letter.")),
            (bool(re.search(r"[0-9]", password)), "number", _("The password must contain a number.")),
            (any(not char.isalnum() and not char.isspace() for char in password), "symbol", _("The password must contain a symbol.")),
        )
        for is_valid, code, message in checks:
            if not is_valid:
                errors.append(ValidationError(message, code=code))
        if errors:
            raise ValidationError(errors)

    def get_help_text(self):
        return _(
            "Use at least 12 characters with uppercase, lowercase, number, and symbol."
        )


class PasswordHistoryValidator:
    history_limit = 3

    def validate(self, password, user=None):
        if user is None or user.pk is None:
            return
        encoded_passwords = list(
            PasswordHistory.objects.filter(user=user)
            .values_list("encoded_password", flat=True)[: self.history_limit]
        )
        if user.has_usable_password() and user.password not in encoded_passwords:
            encoded_passwords.insert(0, user.password)
            encoded_passwords = encoded_passwords[: self.history_limit]
        if any(check_password(password, encoded) for encoded in encoded_passwords):
            raise ValidationError(
                _("This password was recently used. Choose a different password."),
                code="password_used_recently",
            )

    def get_help_text(self):
        return _("The new password cannot match any of your 3 most recent passwords.")
```

- [ ] **Step 4: 把 validator 加入全域 Django 密碼政策**

將 `AUTH_PASSWORD_VALIDATORS` 的最小長度項目與新 validators 設為：

```python
{
    "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    "OPTIONS": {"min_length": 12},
},
{
    "NAME": "bakerydemo.account_security.validators.PasswordComplexityValidator",
},
{
    "NAME": "bakerydemo.account_security.validators.PasswordHistoryValidator",
},
```

保留 `UserAttributeSimilarityValidator`、`CommonPasswordValidator`、`NumericPasswordValidator`。

- [ ] **Step 5: 執行 validator 測試與 Django system check**

Run: `env DJANGO_SETTINGS_MODULE=bakerydemo.settings.test ./manage.py test bakerydemo.account_security.tests.test_validators`

Expected: PASS。

Run: `./manage.py check`

Expected: `System check identified no issues`。

- [ ] **Step 6: 提交密碼政策**

```bash
git add bakerydemo/account_security/validators.py bakerydemo/account_security/tests/test_validators.py bakerydemo/settings/base.py
git commit -m "feat: enforce admin password complexity"
```

---

### Task 3: 建立交易式密碼服務、效期判斷與雜湊變更訊號

**Files:**
- Create: `bakerydemo/account_security/services.py`
- Create: `bakerydemo/account_security/signals.py`
- Create: `bakerydemo/account_security/tests/test_services.py`
- Modify: `bakerydemo/account_security/apps.py`

**Interfaces:**
- Consumes: Task 1 models、Task 2 validators 與 Django password hash API。
- Produces: `get_security_state(user)`, `password_is_expired(user, at=None)`, `set_user_password(user, raw_password, *, must_change_password)`, User pre/post-save signal。

- [ ] **Step 1: 寫出服務與訊號的失敗測試**

```python
# bakerydemo/account_security/tests/test_services.py
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from bakerydemo.account_security.models import PasswordHistory, UserSecurityState
from bakerydemo.account_security.services import password_is_expired, set_user_password


@override_settings(ACCOUNT_SECURITY_PASSWORD_MAX_AGE_DAYS=90)
class PasswordServiceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="editor", password="Initial-Password-1!"
        )

    def test_external_password_save_records_history_and_requires_change(self):
        self.user.set_password("Temporary-Password-2!")
        self.user.save(update_fields=["password"])

        state = self.user.account_security_state
        self.assertTrue(state.must_change_password)
        self.assertTrue(
            self.user.password_history.filter(encoded_password=self.user.password).exists()
        )

    def test_self_service_password_change_clears_flag_and_keeps_three_hashes(self):
        for password in (
            "Second-Password-2!",
            "Third-Password-3!",
            "Fourth-Password-4!",
        ):
            set_user_password(self.user, password, must_change_password=False)

        self.assertFalse(self.user.account_security_state.must_change_password)
        self.assertEqual(self.user.password_history.count(), 3)

    def test_password_expires_at_the_90_day_boundary(self):
        state = self.user.account_security_state
        now = timezone.now()
        state.password_changed_at = now - timedelta(days=90)
        state.must_change_password = False
        state.save()

        self.assertTrue(password_is_expired(self.user, at=now))

    def test_history_failure_rolls_back_password(self):
        original_hash = self.user.password
        with patch(
            "bakerydemo.account_security.services.PasswordHistory.objects.create",
            side_effect=RuntimeError("history unavailable"),
        ):
            with self.assertRaises(RuntimeError):
                set_user_password(
                    self.user,
                    "Replacement-Password-2!",
                    must_change_password=False,
                )

        self.user.refresh_from_db()
        self.assertEqual(self.user.password, original_hash)

    def test_unusable_password_is_not_added_to_history(self):
        self.user.set_unusable_password()
        self.user.save(update_fields=["password"])

        self.assertFalse(
            self.user.password_history.filter(encoded_password=self.user.password).exists()
        )
```

- [ ] **Step 2: 執行測試並確認 services 尚不存在**

Run: `env DJANGO_SETTINGS_MODULE=bakerydemo.settings.test ./manage.py test bakerydemo.account_security.tests.test_services`

Expected: FAIL，錯誤包含 `No module named 'bakerydemo.account_security.services'`。

- [ ] **Step 3: 實作交易服務與三筆裁切**

```python
# bakerydemo/account_security/services.py
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.utils import timezone

from .models import PasswordHistory, UserSecurityState

PASSWORD_HISTORY_LIMIT = 3


def get_security_state(user):
    state, _ = UserSecurityState.objects.get_or_create(
        user=user,
        defaults={"must_change_password": True, "password_changed_at": None},
    )
    return state


def password_is_expired(user, at=None):
    state = get_security_state(user)
    if state.password_changed_at is None:
        return True
    at = at or timezone.now()
    max_age = timedelta(
        days=getattr(settings, "ACCOUNT_SECURITY_PASSWORD_MAX_AGE_DAYS", 90)
    )
    return state.password_changed_at <= at - max_age


def _record_current_hash(user):
    if not user.has_usable_password():
        return
    latest = user.password_history.first()
    if latest is None or latest.encoded_password != user.password:
        PasswordHistory.objects.create(user=user, encoded_password=user.password)
    stale_ids = list(
        user.password_history.values_list("pk", flat=True)[PASSWORD_HISTORY_LIMIT:]
    )
    if stale_ids:
        PasswordHistory.objects.filter(pk__in=stale_ids).delete()


@transaction.atomic
def sync_password_change(user, *, must_change_password):
    _record_current_hash(user)
    state = get_security_state(user)
    state.must_change_password = must_change_password
    state.password_changed_at = timezone.now()
    state.save(
        update_fields=["must_change_password", "password_changed_at", "updated_at"]
    )
    return state


@transaction.atomic
def set_user_password(user, raw_password, *, must_change_password):
    validate_password(raw_password, user=user)
    user.set_password(raw_password)
    user.save(update_fields=["password"])
    sync_password_change(user, must_change_password=must_change_password)
    return user
```

- [ ] **Step 4: 實作 User 密碼雜湊變更偵測並載入 signal**

```python
# bakerydemo/account_security/signals.py
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .services import sync_password_change

User = get_user_model()


@receiver(pre_save, sender=User)
def detect_password_hash_change(sender, instance, **kwargs):
    if instance.pk is None:
        instance._account_security_password_changed = instance.has_usable_password()
        return
    previous = sender._default_manager.only("password").filter(pk=instance.pk).first()
    instance._account_security_password_changed = (
        previous is not None and previous.password != instance.password
    )


@receiver(post_save, sender=User)
def secure_changed_password(sender, instance, created, **kwargs):
    password_changed = created or getattr(
        instance, "_account_security_password_changed", False
    )
    if password_changed:
        sync_password_change(instance, must_change_password=True)
```

在 `AccountSecurityConfig.ready()` 中只做註冊 import：

```python
def ready(self):
    from . import signals  # noqa: F401
```

- [ ] **Step 5: 設定 90 天並執行服務測試**

在 `bakerydemo/settings/base.py` 加入：

```python
ACCOUNT_SECURITY_PASSWORD_MAX_AGE_DAYS = 90
```

Run: `env DJANGO_SETTINGS_MODULE=bakerydemo.settings.test ./manage.py test bakerydemo.account_security.tests.test_services`

Expected: PASS；rollback test 確認舊雜湊不變。

- [ ] **Step 6: 提交密碼服務與訊號**

```bash
git add bakerydemo/account_security/apps.py bakerydemo/account_security/services.py bakerydemo/account_security/signals.py bakerydemo/account_security/tests/test_services.py bakerydemo/settings/base.py
git commit -m "feat: track admin password lifecycle"
```

---

### Task 4: 為既有帳號建立安全資料並保護重設管理員指令

**Files:**
- Create: `bakerydemo/account_security/migrations/0002_bootstrap_existing_users.py`
- Create: `bakerydemo/account_security/tests/test_migrations.py`
- Create: `bakerydemo/account_security/tests/test_management_commands.py`
- Modify: `bakerydemo/base/management/commands/reset_admin_password.py:1-15`

**Interfaces:**
- Consumes: Task 1 schema、Task 3 `set_user_password`。
- Produces: 既有帳號初始安全狀態／目前密碼歷程，以及安全的 `reset_admin_password` 行為。

- [ ] **Step 1: 寫 migration 與指令的失敗測試**

```python
# bakerydemo/account_security/tests/test_management_commands.py
from io import StringIO

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings


class ResetAdminPasswordTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username="admin", email="admin@example.com", password="Old-Password-1!"
        )

    @override_settings(ADMIN_PASSWORD="Temporary-Admin-2!")
    def test_reset_marks_password_as_temporary(self):
        output = StringIO()
        call_command("reset_admin_password", stdout=output)

        self.admin.refresh_from_db()
        self.assertTrue(self.admin.check_password("Temporary-Admin-2!"))
        self.assertTrue(self.admin.account_security_state.must_change_password)
        self.assertNotIn(settings.ADMIN_PASSWORD, output.getvalue())

    @override_settings(ADMIN_PASSWORD="weak")
    def test_reset_rejects_an_invalid_password(self):
        with self.assertRaisesMessage(CommandError, "password"):
            call_command("reset_admin_password")
```

```python
# bakerydemo/account_security/tests/test_migrations.py
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
```

- [ ] **Step 2: 執行測試並確認舊指令未建立安全狀態**

Run: `env DJANGO_SETTINGS_MODULE=bakerydemo.settings.test ./manage.py test bakerydemo.account_security.tests.test_management_commands`

Expected: FAIL，`must_change_password` 或 validator 斷言失敗。

- [ ] **Step 3: 建立可逆資料 migration**

```python
# bakerydemo/account_security/migrations/0002_bootstrap_existing_users.py
from django.conf import settings
from django.db import migrations
from django.utils import timezone


def bootstrap_existing_users(apps, schema_editor):
    app_label, model_name = settings.AUTH_USER_MODEL.split(".")
    User = apps.get_model(app_label, model_name)
    State = apps.get_model("account_security", "UserSecurityState")
    History = apps.get_model("account_security", "PasswordHistory")
    migrated_at = timezone.now()
    for user in User.objects.iterator():
        State.objects.get_or_create(
            user_id=user.pk,
            defaults={
                "must_change_password": False,
                "password_changed_at": migrated_at,
            },
        )
        if user.password and not user.password.startswith("!"):
            History.objects.get_or_create(
                user_id=user.pk,
                encoded_password=user.password,
            )


class Migration(migrations.Migration):
    dependencies = [
        ("account_security", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.RunPython(
            bootstrap_existing_users,
            reverse_code=migrations.RunPython.noop,
        )
    ]
```

- [ ] **Step 4: 讓管理指令走同一個驗證與交易服務**

```python
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError

from bakerydemo.account_security.services import set_user_password


class Command(BaseCommand):
    def handle(self, **options):
        try:
            admin_user = get_user_model().objects.get(username="admin")
        except get_user_model().DoesNotExist as err:
            raise CommandError("Cannot find admin user.") from err
        try:
            set_user_password(
                admin_user,
                settings.ADMIN_PASSWORD,
                must_change_password=True,
            )
        except ValidationError as err:
            raise CommandError("ADMIN_PASSWORD does not satisfy password policy.") from err
```

- [ ] **Step 5: 執行 migration 與指令測試**

Run: `env DJANGO_SETTINGS_MODULE=bakerydemo.settings.test ./manage.py test bakerydemo.account_security.tests.test_migrations bakerydemo.account_security.tests.test_management_commands`

Expected: PASS。

Run: `./manage.py makemigrations --check --dry-run`

Expected: `No changes detected`。

- [ ] **Step 6: 提交資料啟動與安全重設**

```bash
git add bakerydemo/account_security/migrations/0002_bootstrap_existing_users.py bakerydemo/account_security/tests/test_migrations.py bakerydemo/account_security/tests/test_management_commands.py bakerydemo/base/management/commands/reset_admin_password.py
git commit -m "feat: bootstrap admin password security state"
```

---

### Task 5: 建立共用安全改密碼頁與表單

**Files:**
- Create: `bakerydemo/account_security/forms.py`
- Create: `bakerydemo/account_security/views.py`
- Create: `bakerydemo/account_security/urls.py`
- Create: `bakerydemo/account_security/templates/account_security/password_change.html`
- Create: `bakerydemo/account_security/tests/test_password_change_view.py`
- Modify: `bakerydemo/urls.py:16-20`

**Interfaces:**
- Consumes: Task 3 `set_user_password`、Django session auth hash。
- Produces: route name `account_security:password_change`, session key `account_security_return_to`, `SecurityPasswordChangeForm(user, data=None)`。

- [ ] **Step 1: 寫登入、舊密碼、歷程、成功與安全返回網址測試**

```python
# bakerydemo/account_security/tests/test_password_change_view.py
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from bakerydemo.account_security.services import set_user_password


class SecurityPasswordChangeViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="admin", email="admin@example.com", password="Current-Password-1!"
        )
        self.url = reverse("account_security:password_change")

    def test_anonymous_user_is_sent_to_wagtail_login(self):
        response = self.client.get(self.url)
        self.assertRedirects(
            response,
            f"{reverse('wagtailadmin_login')}?next={self.url}",
        )

    def test_wrong_current_password_does_not_change_password(self):
        self.client.force_login(self.user)
        response = self.client.post(
            self.url,
            {
                "old_password": "Wrong-Password-1!",
                "new_password1": "Replacement-Password-2!",
                "new_password2": "Replacement-Password-2!",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Current-Password-1!"))

    def test_success_updates_session_and_returns_to_original_admin(self):
        set_user_password(
            self.user, "Temporary-Password-2!", must_change_password=True
        )
        self.client.force_login(self.user)
        session = self.client.session
        session["account_security_return_to"] = reverse("admin:index")
        session.save()

        response = self.client.post(
            self.url,
            {
                "old_password": "Temporary-Password-2!",
                "new_password1": "Replacement-Password-3!",
                "new_password2": "Replacement-Password-3!",
            },
        )

        self.assertRedirects(response, reverse("admin:index"))
        self.assertIn("_auth_user_id", self.client.session)
        self.user.refresh_from_db()
        self.assertFalse(self.user.account_security_state.must_change_password)
```

- [ ] **Step 2: 執行測試並確認 URL 尚不存在**

Run: `env DJANGO_SETTINGS_MODULE=bakerydemo.settings.test ./manage.py test bakerydemo.account_security.tests.test_password_change_view`

Expected: FAIL，`NoReverseMatch: 'account_security' is not a registered namespace`。

- [ ] **Step 3: 實作表單與安全改密碼 view**

```python
# bakerydemo/account_security/forms.py
from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from .services import set_user_password


class SecurityPasswordChangeForm(forms.Form):
    old_password = forms.CharField(
        label=_("Current password"),
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )
    new_password1 = forms.CharField(
        label=_("New password"),
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    new_password2 = forms.CharField(
        label=_("Confirm new password"),
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_old_password(self):
        value = self.cleaned_data["old_password"]
        if not self.user.check_password(value):
            raise ValidationError(_("The current password is incorrect."), code="invalid")
        return value

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("new_password1")
        password2 = cleaned_data.get("new_password2")
        if password1 and password2 and password1 != password2:
            self.add_error("new_password2", _("The two password fields did not match."))
        elif password1:
            try:
                validate_password(password1, user=self.user)
            except ValidationError as error:
                self.add_error("new_password1", error)
        return cleaned_data

    def save(self):
        return set_user_password(
            self.user,
            self.cleaned_data["new_password1"],
            must_change_password=False,
        )
```

```python
# bakerydemo/account_security/views.py
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import SecurityPasswordChangeForm

RETURN_TO_SESSION_KEY = "account_security_return_to"


@login_required(login_url="wagtailadmin_login")
def password_change(request):
    form = SecurityPasswordChangeForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        return_to = request.session.pop(RETURN_TO_SESSION_KEY, None)
        if not return_to or not url_has_allowed_host_and_scheme(
            return_to, allowed_hosts={request.get_host()}, require_https=request.is_secure()
        ):
            return_to = reverse("wagtailadmin_home")
        return redirect(return_to)
    return render(request, "account_security/password_change.html", {"form": form})
```

- [ ] **Step 4: 加入 URL 與 Wagtail 樣式模板**

```python
# bakerydemo/account_security/urls.py
from django.urls import path

from . import views

app_name = "account_security"

urlpatterns = [
    path("password/change/", views.password_change, name="password_change"),
]
```

在 `bakerydemo/urls.py` 的兩個 admin include 之前加入：

```python
path("account/security/", include("bakerydemo.account_security.urls")),
```

```django
{# bakerydemo/account_security/templates/account_security/password_change.html #}
{% extends "wagtailadmin/base.html" %}
{% load i18n %}

{% block titletag %}{% translate "Change password" %}{% endblock %}

{% block content %}
  <main class="nice-padding" id="main">
    <h1>{% translate "Change password" %}</h1>
    <p>{% translate "Your password must be changed before you can continue." %}</p>
    <form method="post" novalidate>
      {% csrf_token %}
      {{ form.non_field_errors }}
      {% for field in form %}
        <div class="field-content">
          {{ field.label_tag }}
          {{ field }}
          {{ field.errors }}
          {% if field.help_text %}<p class="help">{{ field.help_text }}</p>{% endif %}
        </div>
      {% endfor %}
      <button class="button" type="submit">{% translate "Save new password" %}</button>
    </form>
    <form action="{% url 'wagtailadmin_logout' %}" method="post">
      {% csrf_token %}
      <button class="button button-secondary" type="submit">{% translate "Sign out" %}</button>
    </form>
  </main>
{% endblock %}
```

確認 render 後三個 password input 都沒有 `value` 屬性；此斷言加入 `test_password_change_view.py`。

- [ ] **Step 5: 執行共用改密碼 view 測試**

Run: `env DJANGO_SETTINGS_MODULE=bakerydemo.settings.test ./manage.py test bakerydemo.account_security.tests.test_password_change_view`

Expected: PASS。

- [ ] **Step 6: 提交共用改密碼流程**

```bash
git add bakerydemo/account_security/forms.py bakerydemo/account_security/views.py bakerydemo/account_security/urls.py bakerydemo/account_security/templates/account_security/password_change.html bakerydemo/account_security/tests/test_password_change_view.py bakerydemo/urls.py
git commit -m "feat: add secure admin password change flow"
```

---

### Task 6: 攔截臨時／過期密碼並統一既有改密碼入口

**Files:**
- Create: `bakerydemo/account_security/middleware.py`
- Create: `bakerydemo/account_security/tests/test_middleware.py`
- Modify: `bakerydemo/settings/base.py:83-94`

**Interfaces:**
- Consumes: Task 3 `get_security_state`, `password_is_expired`；Task 5 route 與 return session key。
- Produces: `PasswordPolicyMiddleware`, 設定 `ACCOUNT_SECURITY_PROTECTED_PREFIXES`。

- [ ] **Step 1: 寫 Wagtail、Django、效期、前台與登出例外測試**

```python
# bakerydemo/account_security/tests/test_middleware.py
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone


class PasswordPolicyMiddlewareTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="admin", email="admin@example.com", password="Temporary-Password-1!"
        )
        self.client.force_login(self.user)
        self.change_url = reverse("account_security:password_change")

    def test_temporary_password_redirects_both_admins(self):
        for url in (reverse("wagtailadmin_home"), reverse("admin:index")):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertRedirects(response, self.change_url, fetch_redirect_response=False)

    def test_frontend_page_is_not_blocked(self):
        response = self.client.get("/")
        self.assertNotEqual(response.url if response.status_code in {301, 302} else "", self.change_url)

    def test_password_at_90_days_is_redirected(self):
        state = self.user.account_security_state
        state.must_change_password = False
        state.password_changed_at = timezone.now() - timedelta(days=90)
        state.save()

        response = self.client.get(reverse("wagtailadmin_home"))
        self.assertRedirects(response, self.change_url, fetch_redirect_response=False)

    def test_logout_remains_available(self):
        response = self.client.post(reverse("wagtailadmin_logout"))
        self.assertNotEqual(response.url if response.status_code in {301, 302} else "", self.change_url)

    def test_missing_state_fails_closed(self):
        self.user.account_security_state.delete()

        response = self.client.get(reverse("wagtailadmin_home"))

        self.assertRedirects(response, self.change_url, fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertTrue(self.user.account_security_state.must_change_password)

    def test_builtin_password_change_routes_use_shared_flow(self):
        state = self.user.account_security_state
        state.must_change_password = False
        state.password_changed_at = timezone.now()
        state.save()
        for url in (
            reverse("wagtailadmin_account_change_password"),
            reverse("admin:password_change"),
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertRedirects(
                    response,
                    self.change_url,
                    fetch_redirect_response=False,
                )
```

- [ ] **Step 2: 執行測試並確認臨時密碼仍可進入後台**

Run: `env DJANGO_SETTINGS_MODULE=bakerydemo.settings.test ./manage.py test bakerydemo.account_security.tests.test_middleware`

Expected: FAIL，兩個 admin 首頁沒有導向共用改密碼頁。

- [ ] **Step 3: 實作 request-phase 密碼政策 middleware**

```python
# bakerydemo/account_security/middleware.py
from django.conf import settings
from django.shortcuts import redirect
from django.urls import Resolver404, resolve, reverse

from .services import get_security_state, password_is_expired
from .views import RETURN_TO_SESSION_KEY

ALLOWED_URL_NAMES = {
    "wagtailadmin_logout",
    "admin:logout",
}
LEGACY_PASSWORD_CHANGE_URL_NAMES = {
    "wagtailadmin_account_change_password",
    "admin:password_change",
}


class PasswordPolicyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if not user.is_authenticated or not (user.is_staff or user.is_superuser):
            return self.get_response(request)

        change_url = reverse("account_security:password_change")
        if request.path_info == change_url:
            return self.get_response(request)

        protected_prefixes = getattr(
            settings,
            "ACCOUNT_SECURITY_PROTECTED_PREFIXES",
            ("/admin/", "/django-admin/"),
        )
        if not request.path_info.startswith(tuple(protected_prefixes)):
            return self.get_response(request)

        try:
            view_name = resolve(request.path_info).view_name
        except Resolver404:
            view_name = None
        if view_name in LEGACY_PASSWORD_CHANGE_URL_NAMES:
            return redirect("account_security:password_change")
        if view_name in ALLOWED_URL_NAMES:
            return self.get_response(request)

        state = get_security_state(user)
        if state.must_change_password or password_is_expired(user):
            request.session[RETURN_TO_SESSION_KEY] = request.get_full_path()
            return redirect("account_security:password_change")
        return self.get_response(request)
```

- [ ] **Step 4: 設定 middleware 順序與受保護前綴**

把 middleware 放在 `AuthenticationMiddleware`、`MessageMiddleware` 之後，Axes middleware 之前：

```python
"bakerydemo.account_security.middleware.PasswordPolicyMiddleware",
```

並加入：

```python
ACCOUNT_SECURITY_PROTECTED_PREFIXES = ("/admin/", "/django-admin/")
```

- [ ] **Step 5: 執行 middleware 與 view 回歸測試**

Run: `env DJANGO_SETTINGS_MODULE=bakerydemo.settings.test ./manage.py test bakerydemo.account_security.tests.test_middleware bakerydemo.account_security.tests.test_password_change_view`

Expected: PASS；沒有 redirect loop。

- [ ] **Step 6: 提交強制變更與效期攔截**

```bash
git add bakerydemo/account_security/middleware.py bakerydemo/account_security/tests/test_middleware.py bakerydemo/settings/base.py
git commit -m "feat: enforce temporary and expired admin passwords"
```

---

### Task 7: 整合 django-axes 並保護兩個登入入口

**Files:**
- Modify: `requirements/base.txt:1-10`
- Modify: `bakerydemo/settings/base.py:39-94`
- Modify: `bakerydemo/settings/production.py:143`
- Modify: `bakerydemo/account_security/apps.py`
- Modify: `bakerydemo/account_security/forms.py`
- Modify: `bakerydemo/account_security/views.py`
- Create: `bakerydemo/account_security/templates/account_security/lockout.html`
- Create: `bakerydemo/account_security/tests/test_login_lockout.py`

**Interfaces:**
- Consumes: django-axes authentication backend、database handler、Task 5 templates。
- Produces: `SecurityWagtailLoginForm`, `SecurityAdminAuthenticationForm`, `lockout_response(request, response=None, credentials=None, *args, **kwargs)`。

- [ ] **Step 1: 加入相容 Django 6.0 的 Axes 依賴並安裝**

在 `requirements/base.txt` 加入：

```text
django-axes[ipware]>=8.3.1,<9
```

Run: `pip install -r requirements/development.txt`

Expected: 安裝 django-axes 8.3.x，且 resolver 不降級 Django 6.0 或 Wagtail 7.4。

- [ ] **Step 2: 寫第 4／5 次、跨 IP、成功清零與兩入口測試**

```python
# bakerydemo/account_security/tests/test_login_lockout.py
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import DatabaseError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from axes.models import AccessAttempt


class AdminLoginLockoutTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="admin", email="admin@example.com", password="Correct-Password-1!"
        )

    def _post_wagtail_login(self, password, remote_addr="192.0.2.10"):
        return self.client.post(
            reverse("wagtailadmin_login"),
            {"username": "admin", "password": password},
            REMOTE_ADDR=remote_addr,
        )

    def test_fifth_failure_locks_the_username_across_ip_addresses(self):
        for attempt in range(4):
            response = self._post_wagtail_login(
                "Wrong-Password-1!", remote_addr=f"192.0.2.{attempt + 1}"
            )
            self.assertNotEqual(response.status_code, 429)

        response = self._post_wagtail_login(
            "Wrong-Password-1!", remote_addr="198.51.100.9"
        )
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers["Retry-After"], "900")

    def test_successful_login_resets_failures(self):
        for _ in range(4):
            self._post_wagtail_login("Wrong-Password-1!")
        self._post_wagtail_login("Correct-Password-1!")
        self.client.logout()

        for _ in range(4):
            response = self._post_wagtail_login("Wrong-Password-1!")
        self.assertNotEqual(response.status_code, 429)

    def test_django_admin_uses_the_same_username_lock(self):
        for _ in range(5):
            self._post_wagtail_login("Wrong-Password-1!")

        response = self.client.post(
            reverse("admin:login"),
            {"username": "admin", "password": "Correct-Password-1!"},
            REMOTE_ADDR="203.0.113.8",
        )
        self.assertEqual(response.status_code, 429)
        self.assertTrue(AccessAttempt.objects.filter(username="admin").exists())

    def test_invalid_and_locked_responses_use_the_same_generic_message(self):
        message = (
            "The username or password is incorrect, or this account is "
            "temporarily unavailable."
        )
        invalid = self._post_wagtail_login("Wrong-Password-1!")
        self.assertContains(invalid, message)
        for _ in range(4):
            locked = self._post_wagtail_login("Wrong-Password-1!")
        self.assertContains(locked, message, status_code=429)

    def test_attempt_storage_failure_does_not_authenticate(self):
        with patch(
            "axes.handlers.database.AccessAttempt.objects.select_for_update",
            side_effect=DatabaseError("attempt storage unavailable"),
        ):
            with self.assertRaises(DatabaseError):
                self._post_wagtail_login("Wrong-Password-1!")

        self.assertNotIn("_auth_user_id", self.client.session)
```

- [ ] **Step 3: 執行測試並確認 Axes 尚未設定鎖定**

Run: `env DJANGO_SETTINGS_MODULE=bakerydemo.settings.test ./manage.py test bakerydemo.account_security.tests.test_login_lockout`

Expected: FAIL，第 5 次仍不是 429 或 `axes` 尚未在 `INSTALLED_APPS`。

- [ ] **Step 4: 設定 Axes database handler、帳號鎖定與 15 分鐘冷卻**

在 `base.py`：

```python
from datetime import timedelta

INSTALLED_APPS += ["axes"]

AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

AXES_HANDLER = "axes.handlers.database.AxesDatabaseHandler"
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = timedelta(minutes=15)
AXES_LOCKOUT_PARAMETERS = ["username", ["username", "ip_address"]]
AXES_RESET_ON_SUCCESS = True
AXES_ENABLE_RETRY_AFTER_HEADER = True
AXES_HTTP_RESPONSE_CODE = 429
AXES_LOCKOUT_CALLABLE = "bakerydemo.account_security.views.lockout_response"
WAGTAILADMIN_USER_LOGIN_FORM = (
    "bakerydemo.account_security.forms.SecurityWagtailLoginForm"
)
```

第一個 `username` 參數保證跨 IP 的帳號總計數；第二個組合只增加來源維度與滿足 Axes 的 IP 安全檢查，不會把不同帳號因共用一個 IP 而合併鎖定。

把 `axes.middleware.AxesMiddleware` 放在整個 `MIDDLEWARE` 最後。

`production.py` 原本會在最後 append WhiteNoise，必須改成插在 Axes 之前：

```python
MIDDLEWARE.insert(
    MIDDLEWARE.index("axes.middleware.AxesMiddleware"),
    "whitenoise.middleware.WhiteNoiseMiddleware",
)
```

- [ ] **Step 5: 統一 Wagtail、Django 與鎖定錯誤訊息**

```python
# additions to forms.py
from django.contrib.auth.forms import AuthenticationForm
from wagtail.admin.forms import LoginForm as WagtailLoginForm

GENERIC_LOGIN_ERROR = _(
    "The username or password is incorrect, or this account is temporarily unavailable."
)


class SecurityAdminAuthenticationForm(AuthenticationForm):
    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": GENERIC_LOGIN_ERROR,
        "inactive": GENERIC_LOGIN_ERROR,
    }


class SecurityWagtailLoginForm(WagtailLoginForm):
    error_messages = {
        **WagtailLoginForm.error_messages,
        "invalid_login": GENERIC_LOGIN_ERROR,
        "inactive": GENERIC_LOGIN_ERROR,
    }
```

在 `AccountSecurityConfig.ready()` 設定 Django admin 表單，並保留 signal import：

```python
from django.contrib import admin

from .forms import SecurityAdminAuthenticationForm

admin.site.login_form = SecurityAdminAuthenticationForm
from . import signals  # noqa: E402,F401
from . import checks  # noqa: E402,F401
```

在 `views.py` 加入：

```python
from django.shortcuts import render
from django.utils.translation import gettext as _


def lockout_response(request, response=None, credentials=None, *args, **kwargs):
    message = _(
        "The username or password is incorrect, or this account is temporarily unavailable."
    )
    locked = render(
        request,
        "account_security/lockout.html",
        {"message": message},
        status=429,
    )
    locked.headers["Retry-After"] = "900"
    return locked
```

```django
{# bakerydemo/account_security/templates/account_security/lockout.html #}
{% extends "wagtailadmin/login.html" %}
{% load i18n %}

{% block branding_login %}{% translate "Unable to sign in" %}{% endblock %}
{% block login_form %}
  <p role="alert">{{ message }}</p>
  <p><a class="button" href="{% url 'wagtailadmin_login' %}">{% translate "Return to sign in" %}</a></p>
{% endblock %}
```

鎖定頁不顯示帳號、剩餘嘗試次數或帳號存在狀態。

- [ ] **Step 6: 執行 migration、Axes check 與登入整合測試**

Run: `./manage.py migrate`

Expected: 套用 Axes migrations 與 account_security migrations。

Run: `./manage.py check`

Expected: 不出現 `axes.W001`～`axes.W006`。

Run: `env DJANGO_SETTINGS_MODULE=bakerydemo.settings.test ./manage.py test bakerydemo.account_security.tests.test_login_lockout`

Expected: PASS，第 5 次為 429、`Retry-After=900`、兩入口共用鎖定。

- [ ] **Step 7: 驗證 15 分鐘自動解除與緊急指令**

在 `AdminLoginLockoutTests` 加入：

```python
def test_lock_expires_after_fifteen_minutes(self):
    for _ in range(5):
        self._post_wagtail_login("Wrong-Password-1!")
    AccessAttempt.objects.filter(username="admin").update(
        attempt_time=timezone.now() - timedelta(minutes=16)
    )

    response = self._post_wagtail_login("Correct-Password-1!")

    self.assertNotEqual(response.status_code, 429)
    self.assertIn("_auth_user_id", self.client.session)


def test_axes_username_command_unlocks_exact_account(self):
    for _ in range(5):
        self._post_wagtail_login("Wrong-Password-1!")

    call_command("axes_reset_username", "admin")

    self.assertFalse(AccessAttempt.objects.filter(username="admin").exists())
```

Run: `env DJANGO_SETTINGS_MODULE=bakerydemo.settings.test ./manage.py test bakerydemo.account_security.tests.test_login_lockout`

Expected: PASS，冷卻與人工解鎖均可用。

- [ ] **Step 8: 提交登入鎖定**

```bash
git add requirements/base.txt bakerydemo/settings/base.py bakerydemo/settings/production.py bakerydemo/account_security/apps.py bakerydemo/account_security/forms.py bakerydemo/account_security/views.py bakerydemo/account_security/templates/account_security/lockout.html bakerydemo/account_security/tests/test_login_lockout.py
git commit -m "feat: lock repeated admin login failures"
```

---

### Task 8: 強制正式環境 HTTPS、安全 Cookie 與安全啟動檢查

**Files:**
- Create: `bakerydemo/account_security/checks.py`
- Create: `bakerydemo/account_security/tests/test_security_checks.py`
- Create: `bakerydemo/account_security/tests/test_settings.py`
- Modify: `bakerydemo/settings/base.py:275`
- Modify: `bakerydemo/settings/production.py:254-275`
- Modify: `bakerydemo/settings/dev.py:1-12`
- Modify: `bakerydemo/settings/test.py:1-26`

**Interfaces:**
- Consumes: Task 2 validators、Django deploy checks。
- Produces: check IDs `account_security.E001`～`E003`，正式環境 secure-cookie flags。

- [ ] **Step 1: 寫正式／localhost 設定與初始密碼檢查的失敗測試**

```python
# bakerydemo/account_security/tests/test_security_checks.py
from django.test import SimpleTestCase, override_settings

from bakerydemo.account_security.checks import check_account_security_settings


class AccountSecurityChecksTests(SimpleTestCase):
    @override_settings(
        ACCOUNT_SECURITY_ENFORCE_PRODUCTION_CHECKS=True,
        ADMIN_PASSWORD="changeme",
        WAGTAILADMIN_BASE_URL="http://example.com",
        SESSION_COOKIE_SECURE=False,
        CSRF_COOKIE_SECURE=False,
    )
    def test_insecure_production_settings_are_errors(self):
        errors = check_account_security_settings(None)
        self.assertEqual(
            {error.id for error in errors},
            {"account_security.E001", "account_security.E002", "account_security.E003"},
        )

    @override_settings(ACCOUNT_SECURITY_ENFORCE_PRODUCTION_CHECKS=False)
    def test_local_development_skips_production_only_errors(self):
        self.assertEqual(check_account_security_settings(None), [])
```

```python
# bakerydemo/account_security/tests/test_settings.py
import json
import os
import subprocess
import sys

from django.test import SimpleTestCase


class AccountSecuritySettingsTests(SimpleTestCase):
    def _read_settings(self, module, extra_env=None):
        script = f'''\
import importlib
import json
s = importlib.import_module("{module}")
print(json.dumps({{
    "ssl": getattr(s, "SECURE_SSL_REDIRECT", False),
    "session": getattr(s, "SESSION_COOKIE_SECURE", False),
    "csrf": getattr(s, "CSRF_COOKIE_SECURE", False),
    "hsts": getattr(s, "SECURE_HSTS_SECONDS", 0),
    "proxy": getattr(s, "SECURE_PROXY_SSL_HEADER", None),
    "admin_url": getattr(s, "WAGTAILADMIN_BASE_URL", ""),
}}))
'''
        environment = os.environ.copy()
        environment.update(extra_env or {})
        result = subprocess.run(
            [sys.executable, "-c", script],
            check=True,
            capture_output=True,
            text=True,
            env=environment,
        )
        return json.loads(result.stdout.strip().splitlines()[-1])

    def test_production_enforces_https_and_secure_cookies(self):
        production = self._read_settings(
            "bakerydemo.settings.production",
            {"PRIMARY_HOST": "cms.example.com"},
        )

        self.assertTrue(production["ssl"])
        self.assertTrue(production["session"])
        self.assertTrue(production["csrf"])
        self.assertGreater(production["hsts"], 0)
        self.assertEqual(
            production["proxy"],
            ["HTTP_X_FORWARDED_PROTO", "https"],
        )
        self.assertEqual(production["admin_url"], "https://cms.example.com")

    def test_dev_and_test_keep_local_http_available(self):
        for module in (
            "bakerydemo.settings.dev",
            "bakerydemo.settings.test",
        ):
            with self.subTest(module=module):
                local = self._read_settings(module)
                self.assertFalse(local["ssl"])
                self.assertFalse(local["session"])
                self.assertFalse(local["csrf"])
```

- [ ] **Step 2: 執行測試並確認 checks 尚不存在**

Run: `env DJANGO_SETTINGS_MODULE=bakerydemo.settings.test ./manage.py test bakerydemo.account_security.tests.test_security_checks bakerydemo.account_security.tests.test_settings`

Expected: FAIL，錯誤包含 `No module named 'bakerydemo.account_security.checks'`。

- [ ] **Step 3: 實作 deploy system check**

```python
# bakerydemo/account_security/checks.py
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.checks import Error, Tags, register
from django.core.exceptions import ValidationError


@register(Tags.security, deploy=True)
def check_account_security_settings(app_configs, **kwargs):
    if not getattr(settings, "ACCOUNT_SECURITY_ENFORCE_PRODUCTION_CHECKS", False):
        return []
    errors = []
    admin_password = getattr(settings, "ADMIN_PASSWORD", "")
    try:
        validate_password(admin_password)
    except ValidationError:
        errors.append(
            Error(
                "ADMIN_PASSWORD is missing or does not satisfy password policy.",
                id="account_security.E001",
            )
        )
    secure_cookies = settings.SESSION_COOKIE_SECURE and settings.CSRF_COOKIE_SECURE
    if not settings.SECURE_SSL_REDIRECT or not secure_cookies:
        errors.append(
            Error(
                "Production admin login requires HTTPS and secure cookies.",
                id="account_security.E002",
            )
        )
    admin_url = urlparse(getattr(settings, "WAGTAILADMIN_BASE_URL", ""))
    if admin_url.scheme != "https":
        errors.append(
            Error(
                "WAGTAILADMIN_BASE_URL must use https in production.",
                id="account_security.E003",
            )
        )
    return errors
```

- [ ] **Step 4: 明確區分 production 與 localhost 設定**

在 `base.py`：

```python
ACCOUNT_SECURITY_ENFORCE_PRODUCTION_CHECKS = False
```

在 `production.py`：

```python
ACCOUNT_SECURITY_ENFORCE_PRODUCTION_CHECKS = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
```

保留既有 `SECURE_SSL_REDIRECT=True` 預設、`SECURE_PROXY_SSL_HEADER` 與 HSTS。dev/test 明確保持：

```python
ACCOUNT_SECURITY_ENFORCE_PRODUCTION_CHECKS = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
```

- [ ] **Step 5: 執行 checks、settings tests 與 deploy check**

Run: `env DJANGO_SETTINGS_MODULE=bakerydemo.settings.test ./manage.py test bakerydemo.account_security.tests.test_security_checks bakerydemo.account_security.tests.test_settings`

Expected: PASS。

Run: `./manage.py check --deploy --settings=bakerydemo.settings.production`

Expected: 在未提供 production 環境變數時明確回報缺少安全設定；提供有效 `PRIMARY_HOST`、強密碼與其他既有 production 必要變數後，不出現 `account_security.E001`～`E003`。

- [ ] **Step 6: 提交 HTTPS 與部署檢查**

```bash
git add bakerydemo/account_security/checks.py bakerydemo/account_security/tests/test_security_checks.py bakerydemo/account_security/tests/test_settings.py bakerydemo/settings/base.py bakerydemo/settings/production.py bakerydemo/settings/dev.py bakerydemo/settings/test.py
git commit -m "feat: enforce secure admin deployment settings"
```

---

### Task 9: 加入繁體中文翻譯並完成整體驗證

**Files:**
- Create: `bakerydemo/account_security/locale/zh_Hant/LC_MESSAGES/django.po`
- Generate: `bakerydemo/account_security/locale/zh_Hant/LC_MESSAGES/django.mo`
- Create: `bakerydemo/account_security/tests/test_translations.py`
- Modify: `bakerydemo/settings/base.py:83-94`
- Modify: `bakerydemo/base/tests/test_admin_navigation.py:1-20`

**Interfaces:**
- Consumes: Tasks 2、5、7、8 的 gettext source strings。
- Produces: `zh-hant` 與 `en` 兩種安全錯誤／欄位文字。

- [ ] **Step 1: 啟用標準 LocaleMiddleware 並寫翻譯失敗測試**

把 `django.middleware.locale.LocaleMiddleware` 放在 `SessionMiddleware` 後、`CommonMiddleware` 前。

```python
# bakerydemo/account_security/tests/test_translations.py
from django.test import SimpleTestCase
from django.utils import translation

from bakerydemo.account_security.forms import GENERIC_LOGIN_ERROR


class AccountSecurityTranslationTests(SimpleTestCase):
    def test_generic_login_error_has_english_and_traditional_chinese(self):
        with translation.override("en"):
            english = str(GENERIC_LOGIN_ERROR)
        with translation.override("zh-hant"):
            traditional_chinese = str(GENERIC_LOGIN_ERROR)

        self.assertIn("temporarily unavailable", english)
        self.assertIn("暫時無法登入", traditional_chinese)
        self.assertNotEqual(english, traditional_chinese)
```

- [ ] **Step 2: 執行測試並確認尚未有自訂翻譯**

Run: `env DJANGO_SETTINGS_MODULE=bakerydemo.settings.test ./manage.py test bakerydemo.account_security.tests.test_translations`

Expected: FAIL，繁中內容仍為英文。

- [ ] **Step 3: 建立 zh_Hant catalog 並翻譯所有自訂文字**

Run: `./manage.py makemessages -l zh_Hant -i node_modules -i nuxt-bakery-demo/node_modules`

在 `django.po` 為全部自訂 source 提供以下繁中 msgstr：

```po
msgid "The username or password is incorrect, or this account is temporarily unavailable."
msgstr "帳號或密碼錯誤，或此帳號目前暫時無法登入。"

msgid "The password must contain at least 12 characters."
msgstr "密碼至少必須包含 12 個字元。"

msgid "The password must contain an uppercase English letter."
msgstr "密碼至少必須包含 1 個英文大寫字母。"

msgid "The password must contain a lowercase English letter."
msgstr "密碼至少必須包含 1 個英文小寫字母。"

msgid "The password must contain a number."
msgstr "密碼至少必須包含 1 個數字。"

msgid "The password must contain a symbol."
msgstr "密碼至少必須包含 1 個特殊符號。"

msgid "Use at least 12 characters with uppercase, lowercase, number, and symbol."
msgstr "請使用至少 12 個字元，並包含英文大寫、英文小寫、數字及特殊符號。"

msgid "This password was recently used. Choose a different password."
msgstr "這組密碼最近使用過，請選擇其他密碼。"

msgid "The new password cannot match any of your 3 most recent passwords."
msgstr "新密碼不能與最近使用的 3 組密碼相同。"

msgid "Current password"
msgstr "目前密碼"

msgid "New password"
msgstr "新密碼"

msgid "Confirm new password"
msgstr "確認新密碼"

msgid "The current password is incorrect."
msgstr "目前密碼不正確。"

msgid "The two password fields did not match."
msgstr "兩次輸入的新密碼不一致。"

msgid "Change password"
msgstr "變更密碼"

msgid "Your password must be changed before you can continue."
msgstr "您必須先變更密碼，才能繼續使用後台。"

msgid "Save new password"
msgstr "儲存新密碼"

msgid "Sign out"
msgstr "登出"

msgid "Unable to sign in"
msgstr "目前無法登入"

msgid "Return to sign in"
msgstr "返回登入頁"
```

Run: `rg -n 'msgstr ""' bakerydemo/account_security/locale/zh_Hant/LC_MESSAGES/django.po`

Expected: 除 PO 標頭外沒有空白 `msgstr`。

- [ ] **Step 4: 編譯 catalog 並執行翻譯測試**

Run: `./manage.py compilemessages -l zh_Hant`

Expected: 產生 `django.mo`，沒有 fuzzy 或語法錯誤。

Run: `env DJANGO_SETTINGS_MODULE=bakerydemo.settings.test ./manage.py test bakerydemo.account_security.tests.test_translations`

Expected: PASS。

- [ ] **Step 5: 執行 account_security 全測試與 migration 檢查**

既有 admin navigation 測試使用新建帳號直接 `force_login`；在登入前明確建立「已完成改密碼」狀態，避免測試繞過本功能的真實前置條件：

```python
from bakerydemo.account_security.services import sync_password_change

# after creating self.user and before force_login
sync_password_change(self.user, must_change_password=False)
```

Run: `env DJANGO_SETTINGS_MODULE=bakerydemo.settings.test ./manage.py test bakerydemo.account_security.tests`

Expected: 全部 PASS。

Run: `./manage.py makemigrations --check --dry-run`

Expected: `No changes detected`。

Run: `./manage.py check`

Expected: 無 Django 或 Axes system check 問題。

- [ ] **Step 6: 執行專案回歸測試與 lint**

Run: `env DJANGO_SETTINGS_MODULE=bakerydemo.settings.test ./manage.py test`

Expected: 全專案測試 PASS。

Run: `make lint`

Expected: Ruff、djhtml、curlylint 與 frontend lint 全部 PASS；若既有工具遷移造成非本次錯誤，記錄精確檔案與錯誤，不修改無關檔案。

- [ ] **Step 7: 執行手動安全驗收**

1. localhost 啟動 Wagtail，從 `/admin/` 錯誤登入 4 次仍可嘗試，第 5 次得到通用訊息與 429。
2. 從 `/django-admin/` 使用同帳號與正確密碼，確認仍被同一鎖定擋住。
3. 執行 `./manage.py axes_reset_username admin`，確認可再次登入。
4. 執行 `./manage.py reset_admin_password`，登入後只能進入共用改密碼頁。
5. 依序設定 3 組有效密碼，確認這 3 組均不能重複，第 4 組較舊密碼可再次使用。
6. 將測試狀態設為 90 天前，確認 Wagtail 與 Django 後台都導向共用改密碼頁。
7. 在 production-like HTTPS 代理後確認 HTTP 重新導向、session 與 CSRF Cookie 有 Secure、HSTS 存在，登入 POST 不經 HTTP。

- [ ] **Step 8: 提交翻譯與最終驗證成果**

```bash
git add bakerydemo/account_security/locale bakerydemo/account_security/tests/test_translations.py bakerydemo/settings/base.py bakerydemo/base/tests/test_admin_navigation.py
git commit -m "feat: localize admin security messages"
```

---

## Final Review Checklist

- [ ] `git diff --check` 無 whitespace error。
- [ ] `git status --short` 只顯示明確保留的既有使用者修改，沒有測試資料庫、密碼、`.env` 或暫存檔。
- [ ] `git log --oneline` 顯示每個 task 的小型提交，沒有把原有 Nuxt／API 工作混入。
- [ ] PasswordHistory 沒有註冊到 Wagtail snippets 或 Django admin。
- [ ] 所有登入與改密碼模板都包含 CSRF，密碼 input 不渲染 value。
- [ ] 兩個後台登入入口、兩種語言、localhost 與 production-like HTTPS 均完成驗收。
- [ ] 將實際測試指令、結果、部署所需環境變數與仍需人工檢查項目整理給使用者。

## Reference Documentation

- django-axes 8 installation: <https://django-axes.readthedocs.io/en/latest/2_installation.html>
- django-axes lockout configuration: <https://django-axes.readthedocs.io/en/latest/4_configuration.html>
- Wagtail admin user/login settings: <https://docs.wagtail.org/en/stable/reference/settings.html>
- Django password validation: <https://docs.djangoproject.com/en/6.0/topics/auth/passwords/#password-validation>
- Django deployment security checklist: <https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/>
