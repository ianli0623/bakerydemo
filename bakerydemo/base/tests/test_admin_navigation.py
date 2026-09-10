import json
import re

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from wagtail.models import Site
from wagtail.users.models import UserProfile

from bakerydemo.account_security.services import sync_password_change
from bakerydemo.base.models import StandardPage


class AdminNavigationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_superuser(
            username="admin-navigation",
            email="admin-navigation@example.com",
            password="Admin-Navigation-Password-1!",
        )
        sync_password_change(cls.user, must_change_password=False)
        cls.page = StandardPage(title="Editor controls test", slug="editor-controls")
        Site.objects.get(is_default_site=True).root_page.add_child(instance=cls.page)
        cls.page.save_revision().publish()

    def setUp(self):
        self.client.force_login(self.user)

    def _get_sidebar(self):
        response = self.client.get(reverse("wagtailadmin_home"))

        self.assertEqual(response.status_code, 200)
        match = re.search(
            r'<script id="wagtail-sidebar-props" type="application/json">(.*?)</script>',
            response.content.decode(),
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        return json.loads(match.group(1))

    def test_only_semi_site_settings_are_exposed_from_demo_menu_groups(self):
        sidebar = self._get_sidebar()

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

    def test_unused_reports_and_settings_are_hidden(self):
        sidebar = self._get_sidebar()
        menu_names = []

        def collect_names(value):
            if isinstance(value, dict):
                if "name" in value:
                    menu_names.append(value["name"])
                for child in value.values():
                    collect_names(child)
            elif isinstance(value, list):
                for child in value:
                    collect_names(child)

        collect_names(sidebar)

        hidden_menu_names = {
            "generic-settings",
            "locales",
            "locked-pages",
            "page-types-usage",
            "promoted-search-results",
            "redirects",
            "search-terms",
            "sites",
            "styleguide",
            "workflow-tasks",
            "workflows",
        }
        for menu_name in hidden_menu_names:
            with self.subTest(menu_name=menu_name):
                self.assertNotIn(menu_name, menu_names)

    def test_site_settings_have_an_identifiable_chinese_label(self):
        sidebar = self._get_sidebar()
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

        self.assertIn("SEMI E187 導覽設定", labels)
        self.assertNotIn("Site settings", labels)

    def test_aging_pages_label_is_localized_for_admin_language(self):
        sidebar = self._get_sidebar()
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

        self.assertIn("久未更新頁面", labels)
        self.assertNotIn("Aging pages", labels)

        response = self.client.get(reverse("wagtailadmin_reports:aging_pages"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "久未更新頁面")
        self.assertNotContains(response, "Aging pages")

        profile = UserProfile.objects.create(user=self.user)
        profile.preferred_language = "en"
        profile.save(update_fields=["preferred_language"])

        labels.clear()
        collect_labels(self._get_sidebar())

        self.assertIn("Aging pages", labels)
        self.assertNotIn("久未更新頁面", labels)

        response = self.client.get(reverse("wagtailadmin_reports:aging_pages"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Aging pages")
        self.assertNotContains(response, "久未更新頁面")

    def test_help_and_search_are_hidden_from_main_menu(self):
        sidebar = self._get_sidebar()
        menu_names = []

        def collect_names(value):
            if isinstance(value, dict):
                if "name" in value:
                    menu_names.append(value["name"])
                for child in value.values():
                    collect_names(child)
            elif isinstance(value, list):
                for child in value:
                    collect_names(child)

        collect_names(sidebar)

        with self.subTest(item="help"):
            self.assertNotIn("help", menu_names)

        response = self.client.get(reverse("wagtailadmin_home"))
        with self.subTest(item="search"):
            self.assertRegex(
                response.content.decode(),
                r"<style data-hide-admin-search>\s*"
                r'#wagtail-sidebar form\[role="search"\]\s*'
                r"\{\s*display:\s*none;\s*\}\s*</style>",
            )

    def test_unused_page_editor_controls_are_hidden(self):
        response = self.client.get(
            reverse("wagtailadmin_pages:edit", args=[self.page.id])
        )
        html = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn('data-side-panel-toggle="status"', html)
        for panel_name in ("preview", "checks", "comments"):
            with self.subTest(panel_name=panel_name):
                self.assertEqual(
                    html.count(f'data-side-panel-toggle="{panel_name}"'),
                    0,
                    f"{panel_name} side panel toggle is still rendered",
                )
        self.assertEqual(
            html.count("page-status-tag"),
            0,
            "live page status link is still rendered",
        )

    def test_page_editor_hides_submit_to_moderators_approval(self):
        response = self.client.get(
            reverse("wagtailadmin_pages:edit", args=[self.page.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="action-submit"')
        self.assertContains(response, 'name="action-publish"')

    def test_page_listing_hides_view_live_action(self):
        response = self.client.get(
            reverse("wagtailadmin_explore", args=[self.page.get_parent().id])
        )
        html = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("檢視線上版本", html)
        self.assertContains(
            response,
            reverse("wagtailadmin_pages:edit", args=[self.page.id]),
        )
        self.assertContains(
            response,
            reverse("wagtailadmin_pages:history", args=[self.page.id]),
        )

    def test_page_history_merges_equivalent_autosave_and_publish_entries(self):
        self.page.introduction = "Updated introduction"
        first_autosave = self.page.save_revision(user=self.user, log_action=True)
        second_autosave = self.page.save_revision(user=self.user, log_action=True)
        published_revision = self.page.save_revision(user=self.user, log_action=True)
        published_revision.publish(user=self.user)

        response = self.client.get(
            reverse("wagtailadmin_pages:history", args=[self.page.id])
        )

        self.assertEqual(response.status_code, 200)
        displayed_entries = list(response.context["object_list"])
        displayed_revision_ids = {
            entry.revision_id
            for entry in displayed_entries
            if entry.revision_id
            in {first_autosave.id, second_autosave.id, published_revision.id}
        }
        self.assertEqual(displayed_revision_ids, {published_revision.id})

        published_entry = next(
            entry
            for entry in displayed_entries
            if entry.revision_id == published_revision.id
        )
        action_column = response.context["view"].columns[0]
        self.assertTrue(action_column.get_actions(published_entry, response.context))

    def test_page_history_keeps_genuinely_different_drafts(self):
        self.page.introduction = "First update"
        first_revision = self.page.save_revision(user=self.user, log_action=True)
        self.page.introduction = "Second update"
        second_revision = self.page.save_revision(user=self.user, log_action=True)

        response = self.client.get(
            reverse("wagtailadmin_pages:history", args=[self.page.id])
        )

        self.assertEqual(response.status_code, 200)
        displayed_revision_ids = {
            entry.revision_id for entry in response.context["object_list"]
        }
        self.assertIn(first_revision.id, displayed_revision_ids)
        self.assertIn(second_revision.id, displayed_revision_ids)

    def test_admin_home_renders_semi_e187_branding(self):
        response = self.client.get(reverse("wagtailadmin_home"))

        self.assertEqual(response.status_code, 200)
        self.assertRegex(
            response.content.decode(),
            r"<h1\b[^>]*>\s*SEMI E187\s*</h1>",
        )
        self.assertNotRegex(
            response.content.decode(),
            r"<h1\b[^>]*>\s*The Wagtail Bakery\s*</h1>",
        )
        self.assertContains(response, "data-admin-branding-removed")
        self.assertNotContains(response, "wagtailadmin/images/favicon.ico")

    def test_admin_home_hides_editor_guide_but_keeps_account_link(self):
        response = self.client.get(reverse("wagtailadmin_home"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "editor guide")
        self.assertContains(response, reverse("wagtailadmin_account"))

    def test_page_listing_hides_live_status_but_keeps_status_panel(self):
        response = self.client.get(reverse("wagtailadmin_explore", args=[self.page.id]))
        html = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(html.count("page-status-tag"), 0)
        self.assertIn('data-side-panel-toggle="status"', html)

    def test_login_does_not_render_wagtail_branding(self):
        self.client.logout()

        response = self.client.get(reverse("wagtailadmin_login"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'class="login-logo"')
        self.assertNotContains(response, "wagtailadmin/images/favicon.ico")
