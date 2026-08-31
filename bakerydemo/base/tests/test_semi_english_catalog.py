import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase
from PIL import Image as PILImage

from bakerydemo.base.models import HomePage
from bakerydemo.base.semi_e187.english import (
    ENGLISH_CATALOG,
    find_han_editorial_paths,
    find_untranslated_paths,
    translate_import_plan,
)
from bakerydemo.base.semi_e187.parser import parse_source_site

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "semi_e187"
REQUIRED_IMAGES = ("GPM01.jpg", "contret01.jpg", "GPM+contret.jpg")


class SemiEnglishCatalogTests(SimpleTestCase):
    def setUp(self):
        self.html_temp = TemporaryDirectory()
        self.asset_temp = TemporaryDirectory()
        self.addCleanup(self.html_temp.cleanup)
        self.addCleanup(self.asset_temp.cleanup)
        self.html_dir = Path(self.html_temp.name)
        self.asset_dir = Path(self.asset_temp.name)
        shutil.copytree(FIXTURE_DIR, self.html_dir, dirs_exist_ok=True)
        for index, filename in enumerate(REQUIRED_IMAGES):
            PILImage.new(
                "RGB",
                (32 + index, 24 + index),
                f"#{index + 1:02x}3456",
            ).save(self.asset_dir / filename, "JPEG")

    def source_plan(self):
        return parse_source_site(self.html_dir, self.asset_dir)

    def test_english_catalog_covers_every_editorial_string(self):
        missing = find_untranslated_paths(self.source_plan(), ENGLISH_CATALOG)

        self.assertEqual(missing, ())

    def test_translated_plan_contains_no_unapproved_han_copy(self):
        translated = translate_import_plan(self.source_plan())

        self.assertEqual(find_han_editorial_paths(translated), ())

    def test_translation_keeps_routes_assets_and_company_legal_names_stable(self):
        source = self.source_plan()
        translated = translate_import_plan(source)

        self.assertEqual(
            [page.slug for page in translated.pages],
            [page.slug for page in source.pages],
        )
        self.assertEqual(translated.assets, source.assets)
        source_cases = [
            block
            for block in source.page("ecosystem").body
            if block.type == "case_study"
        ]
        translated_cases = [
            block
            for block in translated.page("ecosystem").body
            if block.type == "case_study"
        ]
        self.assertEqual(
            [case.value["company"] for case in translated_cases],
            [case.value["company"] for case in source_cases],
        )

    def test_catalog_covers_the_detailed_published_process_and_controls(self):
        detailed_paths = {
            "pages.certification.body.3.value.steps.0.checklist.2",
            "pages.certification.body.3.value.steps.0.checklist.3",
            "pages.certification.body.3.value.steps.1.checklist.1",
            "pages.certification.body.3.value.steps.1.checklist.2",
            "pages.certification.body.3.value.steps.1.checklist.3",
            "pages.certification.body.3.value.steps.2.checklist.1",
            "pages.certification.body.3.value.steps.2.checklist.2",
            "pages.certification.body.3.value.steps.2.checklist.3",
            "pages.certification.body.3.value.steps.3.checklist.1",
            "pages.certification.body.3.value.steps.3.checklist.2",
            "pages.certification.body.3.value.steps.3.checklist.3",
            "pages.certification.body.3.value.steps.4.checklist.1",
            "pages.certification.body.3.value.steps.4.checklist.2",
            "pages.certification.body.3.value.steps.4.checklist.3",
            "pages.ecosystem.body.1.value.security_controls.2.title",
            "pages.ecosystem.body.1.value.security_controls.2.summary",
            "pages.ecosystem.body.1.value.security_controls.3.title",
            "pages.ecosystem.body.1.value.security_controls.3.summary",
            "pages.ecosystem.body.2.value.security_controls.2.title",
            "pages.ecosystem.body.2.value.security_controls.2.summary",
            "pages.ecosystem.body.2.value.security_controls.3.title",
            "pages.ecosystem.body.2.value.security_controls.3.summary",
        }

        self.assertEqual(detailed_paths - ENGLISH_CATALOG.keys(), set())

    def test_catalog_uses_complete_published_copy_instead_of_fixture_summaries(self):
        self.assertIn(
            "Administration for Digital Industries",
            ENGLISH_CATALOG["home.hero_text"],
        )
        self.assertIn(
            "Over the past decade",
            ENGLISH_CATALOG["pages.about.body.0.value"],
        )
        self.assertIn(
            "jointly owned",
            ENGLISH_CATALOG["pages.resources.body.0.value.cards.0.summary"],
        )

    def test_translated_page_summaries_fit_wagtail_field_limits(self):
        translated = translate_import_plan(self.source_plan())
        hero_limit = HomePage._meta.get_field("hero_text").max_length

        self.assertLessEqual(len(translated.home.hero_text), hero_limit)
