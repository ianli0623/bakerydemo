import io
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image
from wagtail.users.models import UserProfile

from bakerydemo.account_security.services import sync_password_change
from bakerydemo.base.forms import ResettableAvatarPreferencesForm


class AdminAccountSettingsTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.media_directory = tempfile.TemporaryDirectory()
        cls.media_override = override_settings(MEDIA_ROOT=cls.media_directory.name)
        cls.media_override.enable()

    @classmethod
    def tearDownClass(cls):
        cls.media_override.disable()
        cls.media_directory.cleanup()
        super().tearDownClass()

    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_superuser(
            username="admin-avatar",
            email="admin-avatar@example.com",
            first_name="Admin",
            last_name="Avatar",
            password="Admin-Avatar-Password-1!",
        )
        sync_password_change(cls.user, must_change_password=False)

    def setUp(self):
        self.client.force_login(self.user)
        self.profile = UserProfile.get_for_user(self.user)

    def _account_form_data(self, **extra):
        data = {
            "name_email-first_name": self.user.first_name,
            "name_email-last_name": self.user.last_name,
            "name_email-email": self.user.email,
            "locale-preferred_language": "zh-hant",
            "locale-current_time_zone": "UTC",
            "theme-theme": self.profile.theme,
            "theme-contrast": self.profile.contrast,
            "theme-density": self.profile.density,
        }
        data.update(extra)
        return data

    def _image_file(self, name="custom.png"):
        image_bytes = io.BytesIO()
        Image.new("RGB", (10, 10), color="blue").save(image_bytes, format="PNG")
        return SimpleUploadedFile(
            name,
            image_bytes.getvalue(),
            content_type="image/png",
        )

    def test_reset_to_default_clears_custom_avatar(self):
        self.profile.avatar.save("custom.png", self._image_file(), save=True)
        avatar_name = self.profile.avatar.name
        avatar_storage = self.profile.avatar.storage

        response = self.client.post(
            reverse("wagtailadmin_account"),
            self._account_form_data(**{"avatar-avatar-clear": "on"}),
        )

        self.assertRedirects(response, reverse("wagtailadmin_account"))
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.avatar)
        self.assertFalse(avatar_storage.exists(avatar_name))

    def test_saving_without_avatar_input_preserves_custom_avatar(self):
        self.profile.avatar.save("custom.png", self._image_file(), save=True)
        avatar_name = self.profile.avatar.name

        response = self.client.post(
            reverse("wagtailadmin_account"),
            self._account_form_data(),
        )

        self.assertRedirects(response, reverse("wagtailadmin_account"))
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.avatar.name, avatar_name)
        self.assertTrue(self.profile.avatar.storage.exists(avatar_name))

    def test_replacement_avatar_upload_remains_valid(self):
        form = ResettableAvatarPreferencesForm(
            data={},
            files={"avatar-avatar": self._image_file("replacement.png")},
            instance=self.profile,
            prefix="avatar",
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["avatar"].name, "replacement.png")

    def test_keyboard_shortcuts_setting_is_hidden(self):
        response = self.client.get(reverse("wagtailadmin_account"))

        self.assertEqual(response.status_code, 200)
        for field_name in ("theme", "contrast", "density"):
            with self.subTest(field_name=field_name):
                self.assertContains(response, f'name="theme-{field_name}"')
        self.assertNotContains(response, 'name="theme-keyboard_shortcuts"')
        self.assertNotContains(
            response,
            "Enable custom keyboard shortcuts specific to Wagtail.",
        )

    def test_saving_account_preserves_hidden_keyboard_shortcuts_setting(self):
        self.profile.keyboard_shortcuts = True
        self.profile.save(update_fields=["keyboard_shortcuts"])

        response = self.client.post(
            reverse("wagtailadmin_account"),
            self._account_form_data(),
        )

        self.assertRedirects(response, reverse("wagtailadmin_account"))
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.keyboard_shortcuts)
