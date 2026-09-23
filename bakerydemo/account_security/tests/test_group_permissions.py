from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import TestCase
from django.urls import reverse
from django.utils.module_loading import import_string
from wagtail.users.models import UserProfile

from bakerydemo.account_security.services import sync_password_change


class GroupPermissionAdminTests(TestCase):
    zh_hant_permission_labels = {
        "Localized site content": "多語系網站內容",
        "Simple translation": "簡易翻譯",
        "Custom permissions": "自訂權限",
        "Can publish": "可發佈",
        "Can submit translations": "可提交翻譯",
        "Toggle all": "全選／取消全選",
        "Toggle all add permissions": "全選／取消全部新增權限",
        "Toggle all change permissions": "全選／取消全部變更權限",
        "Toggle all delete permissions": "全選／取消全部刪除權限",
        "Toggle all custom permissions": "全選／取消全部自訂權限",
    }
    translated_object_labels = {
        "Localized site content": "多語系網站內容",
        "Simple translation": "簡易翻譯",
    }
    visible_permission_keys = (
        ("auth", "change_group"),
        ("auth", "change_user"),
        ("base", "change_localizedsitecontent"),
        ("base", "change_sitesettings"),
        ("simple_translation", "submit_translation"),
        ("wagtailadmin", "access_admin"),
    )
    hidden_permission_keys = (
        ("base", "change_genericsettings"),
        ("wagtailcore", "change_locale"),
        ("wagtailcore", "change_site"),
        ("wagtailcore", "add_task"),
        ("wagtailcore", "add_workflow"),
        ("wagtailredirects", "add_redirect"),
        ("wagtailsearchpromotions", "add_searchpromotion"),
    )

    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_superuser(
            username="group-permission-admin",
            email="group-permission-admin@example.com",
            password="Group-Permission-Admin-1!",
        )
        sync_password_change(cls.user, must_change_password=False)
        cls.visible_permissions = [
            Permission.objects.get(
                content_type__app_label=app_label,
                codename=codename,
            )
            for app_label, codename in cls.visible_permission_keys
        ]
        cls.hidden_permissions = [
            Permission.objects.get(
                content_type__app_label=app_label,
                codename=codename,
            )
            for app_label, codename in cls.hidden_permission_keys
        ]
        cls.hidden_permission = cls.hidden_permissions[-2]

    def setUp(self):
        self.client.force_login(self.user)

    def test_group_form_shows_permissions_for_active_admin_features(self):
        response = self.client.get(reverse("wagtailusers_groups:add"))

        self.assertEqual(response.status_code, 200)
        for permission in self.visible_permissions:
            with self.subTest(permission=permission.codename):
                self.assertContains(response, f'value="{permission.pk}"')

    def test_group_form_hides_permissions_for_disabled_admin_features(self):
        response = self.client.get(reverse("wagtailusers_groups:add"))

        self.assertEqual(response.status_code, 200)
        for permission in self.hidden_permissions:
            with self.subTest(permission=permission.codename):
                self.assertNotContains(response, f'value="{permission.pk}"')

    def test_group_form_uses_zh_hant_permission_labels(self):
        response = self.client.get(reverse("wagtailusers_groups:add"))

        self.assertEqual(response.status_code, 200)
        for english, zh_hant in self.zh_hant_permission_labels.items():
            with self.subTest(label=english):
                self.assertContains(response, zh_hant)
                if english in self.translated_object_labels:
                    self.assertNotContains(
                        response,
                        f"<h3>{english}</h3>",
                        html=True,
                    )
                else:
                    self.assertNotContains(response, english)

    def test_group_form_preserves_english_labels_for_english_users(self):
        profile = UserProfile.get_for_user(self.user)
        profile.preferred_language = "en"
        profile.save(update_fields=["preferred_language"])

        response = self.client.get(reverse("wagtailusers_groups:add"))

        self.assertEqual(response.status_code, 200)
        for english, zh_hant in self.zh_hant_permission_labels.items():
            with self.subTest(label=english):
                self.assertContains(response, english)
                self.assertNotContains(response, zh_hant)

    def test_saving_group_preserves_hidden_existing_permissions(self):
        group = Group.objects.create(name="Permission preservation test")
        group.permissions.add(self.hidden_permission)
        app_config = apps.get_app_config("wagtailusers")
        group_viewset_class = import_string(app_config.group_viewset)
        form_class = group_viewset_class().get_form_class(for_update=True)
        form = form_class(
            data={"name": group.name, "permissions": []},
            instance=group,
        )

        self.assertTrue(form.is_valid(), form.errors)
        form.save()

        self.assertTrue(group.permissions.filter(pk=self.hidden_permission.pk).exists())
