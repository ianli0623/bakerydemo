from collections.abc import Iterable, Mapping
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from PIL import Image as PILImage
from wagtail.images import get_image_model
from wagtail.models import Locale, Page, Site

from bakerydemo.base.models import HomePage, LocalizedSiteContent

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "semi_e187"
REQUIRED_IMAGES = ("GPM01.jpg", "contret01.jpg", "GPM+contret.jpg")
PAGE_SLUGS = ("about", "resources", "certification", "ecosystem")


def _page_references(value):
    if isinstance(value, Page):
        yield value
        return
    if isinstance(value, Mapping):
        for child in value.values():
            yield from _page_references(child)
        return
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        for child in value:
            child_value = getattr(child, "value", child)
            yield from _page_references(child_value)


class ImportSemiE187TranslationsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        root = Page.get_first_root_node()
        cls.home = HomePage(
            title="Bakery Home",
            slug="semi-translation-home",
            hero_text="Bakery",
            hero_cta="Explore",
        )
        root.add_child(instance=cls.home)
        cls.home.save_revision().publish()

        cls.site = Site.objects.get(hostname="localhost", port=80)
        cls.site.root_page = cls.home
        cls.site.is_default_site = True
        cls.site.save()

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
        call_command(
            "import_semi_e187",
            html_dir=self.html_dir,
            asset_dir=self.asset_dir,
            home_id=self.home.pk,
            publish=True,
            stdout=StringIO(),
        )

    def call_translation_command(self, **overrides):
        output = StringIO()
        options = {
            "html_dir": self.html_dir,
            "asset_dir": self.asset_dir,
            "home_id": self.home.pk,
            "publish": True,
            "stdout": output,
        }
        options.update(overrides)
        call_command(
            "import_semi_e187_translations",
            **{key: value for key, value in options.items() if value is not False},
        )
        return output.getvalue()

    def source_pages(self):
        home = HomePage.objects.get(pk=self.home.pk)
        children = {
            page.slug: page.specific
            for page in home.get_children().filter(slug__in=PAGE_SLUGS)
        }
        return {"": home, **children}

    def test_dry_run_performs_no_database_or_media_writes(self):
        before_pages = list(
            Page.objects.order_by("pk").values_list(
                "pk",
                "locale_id",
                "translation_key",
                "live",
            )
        )
        before_content = list(
            LocalizedSiteContent.objects.order_by("pk").values_list(
                "pk",
                "locale_id",
                "translation_key",
                "live",
            )
        )
        before_media = tuple(Path(self.media_temp.name).rglob("*"))

        output = self.call_translation_command(publish=False, dry_run=True)

        self.assertEqual(
            list(
                Page.objects.order_by("pk").values_list(
                    "pk",
                    "locale_id",
                    "translation_key",
                    "live",
                )
            ),
            before_pages,
        )
        self.assertEqual(
            list(
                LocalizedSiteContent.objects.order_by("pk").values_list(
                    "pk",
                    "locale_id",
                    "translation_key",
                    "live",
                )
            ),
            before_content,
        )
        self.assertEqual(tuple(Path(self.media_temp.name).rglob("*")), before_media)
        self.assertTrue(output.rstrip().endswith("DRY RUN: no data was changed."))

    def test_publish_creates_live_linked_translations_and_reuses_images(self):
        source_pages = self.source_pages()
        source_keys = {
            slug: page.translation_key for slug, page in source_pages.items()
        }
        image_ids = set(get_image_model().objects.values_list("pk", flat=True))

        output = self.call_translation_command()

        zh = Locale.objects.get(language_code="zh-hant")
        en = Locale.objects.get(language_code="en")
        translated_pages = {}
        for slug, source_id in {
            slug: page.pk for slug, page in source_pages.items()
        }.items():
            source = Page.objects.get(pk=source_id).specific
            translated = source.get_translation(en).specific
            translated_pages[slug] = translated
            self.assertEqual(source.locale, zh)
            self.assertEqual(source.translation_key, source_keys[slug])
            self.assertEqual(translated.translation_key, source_keys[slug])
            self.assertTrue(translated.live)
            self.assertIsNotNone(translated.latest_revision_id)

        referenced_pages = []
        english_home = translated_pages[""]
        referenced_pages.extend(
            [english_home.hero_cta_link, english_home.secondary_hero_cta_link]
        )
        for page in translated_pages.values():
            referenced_pages.extend(_page_references(page.body))
        self.assertTrue(referenced_pages)
        self.assertTrue(all(page.locale == en for page in referenced_pages))

        self.assertEqual(
            set(get_image_model().objects.values_list("pk", flat=True)),
            image_ids,
        )
        english_content = LocalizedSiteContent.for_site_and_locale(
            self.site,
            en,
        )
        self.assertIsNotNone(english_content)
        self.assertEqual(
            english_content.site_name,
            "SEMI E187 Semiconductor Equipment Cybersecurity Standard",
        )
        self.assertTrue(english_content.live)
        self.assertIn("Published English pages: 5", output)
        self.assertIn("Reused images: 3", output)

    def test_second_publish_is_rejected_without_overwriting_english(self):
        self.call_translation_command()
        english = Locale.objects.get(language_code="en")
        first_titles = {
            page.translation_key: page.title
            for page in Page.objects.filter(locale=english)
        }

        with self.assertRaisesRegex(CommandError, "already exists"):
            self.call_translation_command()

        self.assertEqual(
            {
                page.translation_key: page.title
                for page in Page.objects.filter(locale=english)
            },
            first_titles,
        )

    def test_missing_target_translation_rolls_back_every_translation_write(self):
        from bakerydemo.base.semi_e187.translation_publisher import (
            copy_translation_tree,
        )

        before_page_count = Page.objects.count()
        source_locale_ids = {
            page.pk: page.locale_id for page in self.source_pages().values()
        }

        def incomplete_tree(source_pages, locale):
            translations = copy_translation_tree(source_pages, locale)
            translations.pop("resources")
            return translations

        with (
            patch(
                "bakerydemo.base.semi_e187.translation_publisher.copy_translation_tree",
                side_effect=incomplete_tree,
            ),
            self.assertRaisesRegex(CommandError, "resources"),
        ):
            self.call_translation_command()

        self.assertEqual(Page.objects.count(), before_page_count)
        self.assertEqual(
            {page.pk: page.locale_id for page in self.source_pages().values()},
            source_locale_ids,
        )
        self.assertFalse(Locale.objects.filter(language_code="en").exists())

    def test_command_requires_exactly_one_mode(self):
        common = {
            "html_dir": self.html_dir,
            "asset_dir": self.asset_dir,
            "home_id": self.home.pk,
        }
        with self.assertRaises(CommandError):
            call_command("import_semi_e187_translations", **common)
        with self.assertRaises(CommandError):
            call_command(
                "import_semi_e187_translations",
                **common,
                dry_run=True,
                publish=True,
            )
