import json
import re

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from bakerydemo.account_security.services import sync_password_change


class AdminNavigationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_superuser(
            username="admin-navigation",
            email="admin-navigation@example.com",
            password="Admin-Navigation-Password-1!",
        )
        sync_password_change(cls.user, must_change_password=False)

    def setUp(self):
        self.client.force_login(self.user)

    def test_only_semi_site_settings_are_exposed_from_demo_menu_groups(self):
        response = self.client.get(reverse("wagtailadmin_home"))

        self.assertEqual(response.status_code, 200)
        match = re.search(
            r'<script id="wagtail-sidebar-props" type="application/json">(.*?)</script>',
            response.content.decode(),
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        sidebar = json.loads(match.group(1))

        labels = []

        def collect_labels(value):
            if isinstance(value, dict):
                if "label" in value:
                    labels.append(value["label"])
                for child in value.values():
                    collect_labels(child)
            elif isinstance(value, list):
                for child in value:
                    collect_labels(child)

        collect_labels(sidebar)

        self.assertIn("SEMI E187 網站設定", labels)
        self.assertNotIn("Bakery Misc", labels)
        self.assertNotIn("Breads", labels)
        self.assertNotIn("People", labels)
        self.assertNotIn("Footer text", labels)
