import hashlib
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.files.images import ImageFile
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from PIL import Image as PILImage
from wagtail.images import get_image_model
from wagtail.models import Collection, Locale, Page, Site

from bakerydemo.base.models import (
    HomePage,
    LocalizedSiteContent,
    SiteSettings,
    StandardPage,
)
from bakerydemo.base.semi_e187.parser import parse_source_site
from bakerydemo.base.semi_e187.targets import TargetValidationError, validate_targets

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "semi_e187"
REQUIRED_IMAGES = ("GPM01.jpg", "contret01.jpg", "GPM+contret.jpg")


class ImportSemiE187DryRunTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.root = Page.get_first_root_node()
        cls.home = HomePage(
            title="Bakery Home",
            slug="semi-import-home",
            hero_text="Bakery",
            hero_cta="Explore",
        )
        cls.root.add_child(instance=cls.home)
        cls.home.save_revision().publish()

        cls.site = Site.objects.get(hostname="localhost", port=80)
        cls.site.root_page = cls.home
        cls.site.is_default_site = True
        cls.site.save()

        for title, slug in (
            ("TEST", "test-page"),
            ("AXCC", "axcc"),
            ("CCC", "ccc"),
        ):
            page = StandardPage(title=title, slug=slug, show_in_menus=True)
            cls.home.add_child(instance=page)
            page.save_revision().publish()

    def setUp(self):
        self.html_temp = TemporaryDirectory()
        self.asset_temp = TemporaryDirectory()
        self.media_temp = TemporaryDirectory()
        self.addCleanup(self.html_temp.cleanup)
        self.addCleanup(self.asset_temp.cleanup)
        self.addCleanup(self.media_temp.cleanup)
        self.html_dir = Path(self.html_temp.name)
        self.asset_dir = Path(self.asset_temp.name)
        for source in FIXTURE_DIR.iterdir():
            (self.html_dir / source.name).write_bytes(source.read_bytes())
        for index, filename in enumerate(REQUIRED_IMAGES):
            PILImage.new("RGB", (32 + index, 24), f"#{index + 1:02x}3456").save(
                self.asset_dir / filename,
                "JPEG",
            )
        self.media_override = override_settings(MEDIA_ROOT=self.media_temp.name)
        self.media_override.enable()
        self.addCleanup(self.media_override.disable)

    def call_dry_run(self, **overrides):
        output = StringIO()
        options = {
            "html_dir": self.html_dir,
            "asset_dir": self.asset_dir,
            "home_id": self.home.pk,
            "dry_run": True,
            "stdout": output,
        }
        options.update(overrides)
        call_command("import_semi_e187", **options)
        return output.getvalue()

    def call_publish(self):
        output = StringIO()
        call_command(
            "import_semi_e187",
            html_dir=self.html_dir,
            asset_dir=self.asset_dir,
            home_id=self.home.pk,
            publish=True,
            stdout=output,
        )
        return output.getvalue()

    def database_snapshot(self):
        return {
            "pages": list(
                Page.objects.order_by("pk").values_list(
                    "pk",
                    "path",
                    "depth",
                    "live",
                    "show_in_menus",
                    "slug",
                    "title",
                )
            ),
            "settings": SiteSettings.objects.count(),
            "localized_site_content": LocalizedSiteContent.objects.count(),
            "images": get_image_model().objects.count(),
            "collections": Collection.objects.count(),
        }

    def test_successful_dry_run_reports_actions_and_untouched_pages(self):
        output = self.call_dry_run()

        self.assertIn(f"Home ID {self.home.pk}：更新", output)
        self.assertIn("about：建立", output)
        self.assertIn("resources：建立", output)
        self.assertIn("停用連結：15", output)
        self.assertIn("TEST", output)
        self.assertIn("AXCC", output)
        self.assertIn("CCC", output)
        self.assertTrue(output.rstrip().endswith("DRY RUN：未寫入資料庫或媒體檔案。"))

    def test_dry_run_does_not_write_database_or_media(self):
        before_database = self.database_snapshot()
        before_media = tuple(Path(self.media_temp.name).rglob("*"))

        self.call_dry_run()

        self.assertEqual(self.database_snapshot(), before_database)
        self.assertEqual(tuple(Path(self.media_temp.name).rglob("*")), before_media)

    def test_invalid_contact_aborts_publish_before_any_write(self):
        path = self.html_dir / "index.html"
        source = path.read_text(encoding="utf-8")
        path.write_text(
            source.replace(
                "mailto:MaxYCLee@itri.org.tw",
                "mailto:not-an-email",
            ),
            encoding="utf-8",
        )
        before_database = self.database_snapshot()
        before_media = tuple(Path(self.media_temp.name).rglob("*"))

        with self.assertRaisesRegex(CommandError, "contact email"):
            self.call_publish()

        self.assertEqual(self.database_snapshot(), before_database)
        self.assertEqual(tuple(Path(self.media_temp.name).rglob("*")), before_media)

    def test_mode_is_required_and_modes_are_mutually_exclusive(self):
        common = {
            "html_dir": self.html_dir,
            "asset_dir": self.asset_dir,
            "home_id": self.home.pk,
        }

        with self.assertRaises(CommandError):
            call_command("import_semi_e187", **common)
        with self.assertRaises(CommandError):
            call_command(
                "import_semi_e187",
                **common,
                dry_run=True,
                publish=True,
            )

    def test_missing_input_directories_are_reported_as_command_errors(self):
        missing = self.html_dir / "missing"
        for option in ("html_dir", "asset_dir"):
            with self.subTest(option=option):
                values = {
                    "html_dir": self.html_dir,
                    "asset_dir": self.asset_dir,
                    option: missing,
                }
                with self.assertRaisesRegex(CommandError, "目錄不存在"):
                    call_command("import_semi_e187", **values, dry_run=True)

    def test_missing_or_wrong_home_page_is_rejected(self):
        with self.assertRaisesRegex(CommandError, "Home ID 999"):
            self.call_dry_run(home_id=999)

        wrong_home = StandardPage(title="Wrong home type", slug="wrong-home")
        self.root.add_child(instance=wrong_home)
        with self.assertRaisesRegex(CommandError, "HomePage"):
            self.call_dry_run(home_id=wrong_home.pk)

    def test_conflicting_page_type_is_rejected(self):
        conflict = Page(title="Conflict", slug="about")
        self.home.add_child(instance=conflict)

        with self.assertRaisesRegex(CommandError, "about.*StandardPage"):
            self.call_dry_run()

    def test_same_slug_standard_page_outside_home_is_rejected(self):
        outside = StandardPage(title="Outside about", slug="about")
        self.root.add_child(instance=outside)

        with self.assertRaisesRegex(CommandError, "about.*直接子頁"):
            self.call_dry_run()

    def test_existing_direct_standard_page_is_reported_as_update(self):
        about = StandardPage(title="Existing about", slug="about")
        self.home.add_child(instance=about)
        about.save_revision().publish()

        output = self.call_dry_run()

        self.assertIn(f"about：更新（ID {about.pk}）", output)

    def test_publish_updates_home_and_creates_all_content(self):
        self.home.lead_title = "Legacy promo"
        self.home.lead_text = "Legacy promo text"
        self.home.featured_section_1_title = "Legacy section"
        self.home.featured_section_1 = Page.objects.get(slug="test-page")
        self.home.save()

        output = self.call_publish()

        self.home.refresh_from_db()
        imported = list(
            self.home.get_children()
            .filter(slug__in=("about", "resources", "certification", "ecosystem"))
            .specific()
        )
        self.assertEqual(
            [page.slug for page in imported],
            ["about", "resources", "certification", "ecosystem"],
        )
        self.assertTrue(all(isinstance(page, StandardPage) for page in imported))
        self.assertTrue(all(page.live and page.latest_revision_id for page in imported))
        self.assertTrue(all(page.show_in_menus for page in imported))
        self.assertEqual(self.home.pk, self.site.root_page_id)
        self.assertTrue(self.home.live)
        self.assertTrue(self.home.latest_revision_id)
        self.assertEqual(self.home.lead_title, "")
        self.assertEqual(str(self.home.lead_text), "")
        self.assertIsNone(self.home.featured_section_1)
        self.assertEqual(self.home.featured_section_1_title, "")

        settings = SiteSettings.objects.get(site=self.site)
        self.assertEqual(settings.contact_phone, "02-23116228 #202")
        self.assertEqual(settings.contact_email, "MaxYCLee@itri.org.tw")
        self.assertEqual(
            [block.value.pk for block in settings.primary_navigation],
            [self.home.pk, *[page.pk for page in imported]],
        )
        localized_content = LocalizedSiteContent.for_site_and_locale(
            self.site,
            Locale.objects.get(language_code="zh-hant"),
        )
        self.assertIsNotNone(localized_content)
        self.assertEqual(localized_content.title_suffix, "SEMI E187")
        self.assertEqual(localized_content.brand_label, "認驗證制度")
        self.assertEqual(localized_content.contact_name, "李先生")
        self.assertEqual(
            localized_content.footer_introduction,
            "若有合規輔導或技術疑問，歡迎聯絡推動辦公室。",
        )
        self.assertTrue(localized_content.revisions.exists())
        images = get_image_model().objects.filter(collection__name="SEMI E187")
        self.assertEqual(images.count(), 3)
        self.assertIn("建立頁面：4", output)
        self.assertIn("建立圖片：3", output)

    def test_publish_is_idempotent_for_pages_images_and_collection(self):
        self.call_publish()
        first_page_ids = dict(
            Page.objects.filter(
                slug__in=("about", "resources", "certification", "ecosystem")
            ).values_list("slug", "pk")
        )
        first_image_ids = dict(
            get_image_model()
            .objects.filter(collection__name="SEMI E187")
            .values_list("title", "pk")
        )
        first_counts = (
            Page.objects.count(),
            get_image_model().objects.count(),
            Collection.objects.filter(name="SEMI E187").count(),
        )

        output = self.call_publish()

        self.assertEqual(
            dict(
                Page.objects.filter(
                    slug__in=("about", "resources", "certification", "ecosystem")
                ).values_list("slug", "pk")
            ),
            first_page_ids,
        )
        self.assertEqual(
            dict(
                get_image_model()
                .objects.filter(collection__name="SEMI E187")
                .values_list("title", "pk")
            ),
            first_image_ids,
        )
        self.assertEqual(
            (
                Page.objects.count(),
                get_image_model().objects.count(),
                Collection.objects.filter(name="SEMI E187").count(),
            ),
            first_counts,
        )
        self.assertIn("建立頁面：0", output)
        self.assertIn("重用圖片：3", output)

    def test_changed_image_reuses_id_replaces_bytes_and_invalidates_renditions(self):
        self.call_publish()
        image_model = get_image_model()
        image = image_model.objects.get(title="SEMI E187 — GPM01")
        image_id = image.pk
        old_name = image.file.name
        with image.file.open("rb") as stored:
            old_hash = hashlib.sha256(stored.read()).hexdigest()
        image.get_rendition("max-10x10")
        self.assertEqual(image.renditions.count(), 1)
        PILImage.new("RGB", (40, 30), "#abcdef").save(
            self.asset_dir / "GPM01.jpg",
            "JPEG",
        )

        with self.captureOnCommitCallbacks(execute=True):
            output = self.call_publish()

        image = image_model.objects.get(pk=image_id)
        with image.file.open("rb") as stored:
            new_hash = hashlib.sha256(stored.read()).hexdigest()
        self.assertNotEqual(new_hash, old_hash)
        self.assertNotEqual(image.file.name, old_name)
        self.assertEqual(image.renditions.count(), 0)
        self.assertFalse(image.file.storage.exists(old_name))
        self.assertIn("更新圖片：1", output)
        self.assertIn("重用圖片：2", output)

    def test_failure_after_media_writes_rolls_back_and_removes_only_new_files(self):
        existing = get_image_model().objects.create(
            title="Existing image",
            file=ImageFile(
                (self.asset_dir / "GPM01.jpg").open("rb"),
                name="existing.jpg",
            ),
            collection=Collection.get_first_root_node(),
        )
        existing_name = existing.file.name
        before_database = self.database_snapshot()
        before_files = {
            path.relative_to(self.media_temp.name)
            for path in Path(self.media_temp.name).rglob("*")
            if path.is_file()
        }

        with (
            patch(
                "bakerydemo.base.semi_e187.publisher.upsert_page_shells",
                side_effect=RuntimeError("injected publication failure"),
            ),
            self.assertRaisesRegex(RuntimeError, "injected publication failure"),
        ):
            self.call_publish()

        after_files = {
            path.relative_to(self.media_temp.name)
            for path in Path(self.media_temp.name).rglob("*")
            if path.is_file()
        }
        self.assertEqual(self.database_snapshot(), before_database)
        self.assertEqual(after_files, before_files)
        self.assertTrue(existing.file.storage.exists(existing_name))

    def test_two_publishes_preserve_unrelated_page_state(self):
        unrelated_slugs = ("test-page", "axcc", "ccc")

        def snapshot():
            return [
                (
                    page.pk,
                    page.path,
                    page.depth,
                    page.live,
                    page.show_in_menus,
                    page.slug,
                    page.title,
                    page.get_parent().pk,
                )
                for page in Page.objects.filter(slug__in=unrelated_slugs).order_by("pk")
            ]

        before = snapshot()

        self.call_publish()
        self.call_publish()

        self.assertEqual(snapshot(), before)

    def test_target_validation_is_read_only(self):
        plan = parse_source_site(self.html_dir, self.asset_dir)
        before = self.database_snapshot()

        targets = validate_targets(plan, self.home.pk)

        self.assertEqual(
            [target.slug for target in targets.pages],
            list(plan.settings.navigation_slugs[1:]),
        )
        self.assertEqual(self.database_snapshot(), before)


class TargetErrorContractTests(TestCase):
    def test_target_validation_error_is_a_value_error(self):
        self.assertTrue(issubclass(TargetValidationError, ValueError))
