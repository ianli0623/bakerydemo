from django.contrib.auth import get_user_model
from django.test import SimpleTestCase
from django.utils import translation

from bakerydemo.account_security.forms import (
    GENERIC_LOGIN_ERROR,
    SecurityPasswordChangeForm,
)
from bakerydemo.account_security.validators import PasswordComplexityValidator


class AccountSecurityTranslationTests(SimpleTestCase):
    def test_generic_login_error_has_english_and_traditional_chinese(self):
        with translation.override("en"):
            english = str(GENERIC_LOGIN_ERROR)
        with translation.override("zh-hant"):
            traditional_chinese = str(GENERIC_LOGIN_ERROR)

        self.assertIn("temporarily unavailable", english)
        self.assertIn("暫時無法登入", traditional_chinese)
        self.assertNotEqual(english, traditional_chinese)

    def test_password_help_and_form_labels_have_traditional_chinese(self):
        user = get_user_model()(username="translation-test")

        with translation.override("zh-hant"):
            help_text = str(PasswordComplexityValidator().get_help_text())
            form = SecurityPasswordChangeForm(user)
            labels = [str(field.label) for field in form.fields.values()]

        self.assertIn("至少 12 個字元", help_text)
        self.assertEqual(labels, ["目前密碼", "新密碼", "確認新密碼"])
