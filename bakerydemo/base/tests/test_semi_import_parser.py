import re
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

from bs4 import BeautifulSoup
from django.test import SimpleTestCase
from PIL import Image as PILImage

from bakerydemo.base.semi_e187.html import parse_html, sanitize_rich_text
from bakerydemo.base.semi_e187.links import (
    normalize_source_link,
    validate_fragment,
)
from bakerydemo.base.semi_e187.parser import parse_source_site
from bakerydemo.base.semi_e187.schema import SourceLink, SourceValidationError

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "semi_e187"
REQUIRED_HTML = (
    "index.html",
    "about.html",
    "resources.html",
    "certification.html",
    "ecosystem.html",
)
REQUIRED_IMAGES = ("GPM01.jpg", "contret01.jpg", "GPM+contret.jpg")


class SemiImportParserTests(SimpleTestCase):
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

    def parse(self):
        return parse_source_site(self.html_dir, self.asset_dir)

    def test_preserves_every_visible_section_heading_for_editorial_translation(self):
        plan = self.parse()

        self.assertEqual(plan.home.hero_badge, "標準認知 × 技術資源 × 驗證合規")
        self.assertEqual(plan.home.secondary_hero_cta, "合規設備清單")
        self.assertEqual(plan.home.secondary_hero_cta_link.target_slug, "certification")
        self.assertEqual(plan.home.secondary_hero_cta_link.fragment, "certified-list")
        self.assertEqual(plan.page("about").section_kicker, "ABOUT SEMI E187")
        self.assertEqual(plan.page("about").section_heading, "關於標準與背景介紹")
        self.assertEqual(
            plan.page("certification").section_heading,
            "驗證與合規專區",
        )
        self.assertEqual(
            plan.page("ecosystem").secondary_section_kicker,
            "DEMONSTRATION SITES",
        )
        self.assertEqual(
            plan.page("ecosystem").secondary_section_heading,
            "設備廠商導入應用案例",
        )
        self.assertEqual(
            plan.page("ecosystem").secondary_section_introduction,
            "提供 SEMI E187 導入實務示範。",
        )
        cases = [
            block for block in plan.page("ecosystem").body if block.type == "case_study"
        ]
        self.assertTrue(cases)
        self.assertTrue(
            all(
                case.value["security_controls_heading"] == "資安控制重點"
                for case in cases
            )
        )

    def test_parses_exact_page_order_block_sequences_and_counts(self):
        plan = self.parse()

        self.assertEqual(
            [page.slug for page in plan.pages],
            ["about", "resources", "certification", "ecosystem"],
        )
        self.assertEqual(
            [block.type for block in plan.home.body],
            ["card_grid", "card_grid"],
        )
        self.assertEqual(
            [block.type for block in plan.page("about").body],
            ["paragraph_block", "card_grid"],
        )
        self.assertEqual(
            [block.type for block in plan.page("resources").body],
            ["card_grid", "document_table"],
        )
        self.assertEqual(
            [block.type for block in plan.page("certification").body],
            ["paragraph_block", "card_grid", "card_grid", "process_steps"],
        )
        self.assertEqual(
            [block.type for block in plan.page("ecosystem").body],
            ["card_grid", "case_study", "case_study"],
        )
        self.assertEqual(plan.counts.pages, 5)
        self.assertEqual(plan.counts.blocks, 13)
        self.assertEqual(plan.counts.disabled_links, 15)
        self.assertEqual(
            [asset.filename for asset in plan.assets],
            list(REQUIRED_IMAGES),
        )

    def test_parses_public_site_settings_and_internal_routes(self):
        plan = self.parse()

        self.assertEqual(
            plan.settings.site_name,
            "SEMI E187 半導體設備資安標準",
        )
        self.assertEqual(plan.settings.contact_name, "李先生")
        self.assertEqual(plan.settings.contact_context, "認驗證制度與流程")
        self.assertEqual(plan.settings.brand_label, "認驗證制度")
        self.assertEqual(
            plan.settings.footer_introduction,
            "若有合規輔導或技術疑問，歡迎聯絡推動辦公室。",
        )
        self.assertEqual(plan.settings.contact_phone, "02-23116228 #202")
        topic_cards = plan.home.body[1].value["cards"]
        self.assertEqual(topic_cards[0]["link"].target_slug, "about")
        self.assertEqual(topic_cards[3]["link"].target_slug, "ecosystem")
        self.assertTrue(
            any(warning.code == "language-switch-omitted" for warning in plan.warnings)
        )
        self.assertTrue(
            any(warning.code == "optional-asset-missing" for warning in plan.warnings)
        )

    def test_plan_is_deterministic_and_nested_block_values_are_immutable(self):
        first = self.parse()
        second = self.parse()

        self.assertEqual(first, second)
        with self.assertRaises(TypeError):
            first.home.body[0].value["heading"] = "changed"
        with self.assertRaises(AttributeError):
            first.pages.append(first.pages[0])
        with self.assertRaises(KeyError):
            first.page("missing")

    def test_rich_text_keeps_semantics_and_removes_executable_markup(self):
        rich_text = self.parse().page("about").body[0].value

        self.assertIn("<p>", rich_text)
        self.assertIn("<strong>數位轉型</strong>", rich_text)
        self.assertIn("避免惡意連結", rich_text)
        for unsafe in (
            "<script",
            "<style",
            "onclick",
            "class=",
            "style=",
            "javascript:",
        ):
            with self.subTest(unsafe=unsafe):
                self.assertNotIn(unsafe, rich_text)

    def test_sanitizer_keeps_only_safe_anchor_attributes(self):
        soup = parse_html(
            '<p class="x">請看 <a href="https://example.com" '
            'onclick="bad()" target="_blank">官方說明</a></p>'
        )

        self.assertEqual(
            sanitize_rich_text(soup.contents),
            '<p>請看 <a href="https://example.com">官方說明</a></p>',
        )

    def test_sanitizer_removes_incomplete_external_destinations(self):
        soup = parse_html('<p><a href="https:">無效連結</a></p>')

        self.assertEqual(sanitize_rich_text(soup.contents), "<p>無效連結</p>")

    def test_every_required_html_file_is_validated_before_parsing(self):
        for filename in REQUIRED_HTML:
            with self.subTest(filename=filename):
                path = self.html_dir / filename
                original = path.read_bytes()
                path.unlink()
                try:
                    with self.assertRaisesRegex(
                        SourceValidationError,
                        re.escape(filename),
                    ):
                        self.parse()
                finally:
                    path.write_bytes(original)

    def test_every_required_jpeg_is_validated_before_parsing(self):
        for filename in REQUIRED_IMAGES:
            with self.subTest(filename=filename):
                path = self.asset_dir / filename
                original = path.read_bytes()
                path.unlink()
                try:
                    with self.assertRaisesRegex(
                        SourceValidationError,
                        re.escape(filename),
                    ):
                        self.parse()
                finally:
                    path.write_bytes(original)

    def test_duplicate_case_section_is_rejected(self):
        path = self.html_dir / "ecosystem.html"
        source = path.read_text(encoding="utf-8")
        path.write_text(
            source.replace(
                "</main>",
                '<section id="case-studies"><article></article></section></main>',
            ),
            encoding="utf-8",
        )

        with self.assertRaisesRegex(
            SourceValidationError,
            r"ecosystem\.html.*#case-studies",
        ):
            self.parse()

    def test_malformed_document_table_is_rejected(self):
        path = self.html_dir / "resources.html"
        source = path.read_text(encoding="utf-8")
        path.write_text(
            source.replace(
                '<tr id="doc-01"><td>01</td>',
                '<tr id="doc-01">',
            ),
            encoding="utf-8",
        )

        with self.assertRaisesRegex(
            SourceValidationError,
            r"resources\.html.*documents-table",
        ):
            self.parse()

    def test_process_requires_exactly_five_steps(self):
        path = self.html_dir / "certification.html"
        original = path.read_text(encoding="utf-8")

        for mode in ("fewer", "more"):
            with self.subTest(mode=mode):
                soup = BeautifulSoup(original, "html.parser")
                steps = soup.select("#vendor-process [data-step]")
                if mode == "fewer":
                    steps[-1].decompose()
                else:
                    steps[-1].insert_after(BeautifulSoup(str(steps[-1]), "html.parser"))
                path.write_text(str(soup), encoding="utf-8")

                with self.assertRaisesRegex(
                    SourceValidationError,
                    r"certification\.html.*vendor-process",
                ):
                    self.parse()

        path.write_text(original, encoding="utf-8")

    def test_process_checklists_remove_source_checkmark_decoration(self):
        path = self.html_dir / "certification.html"
        source = path.read_text(encoding="utf-8")
        path.write_text(
            source.replace("<li>盤點設備</li>", "<li>✓ 盤點設備</li>"),
            encoding="utf-8",
        )

        process_steps = self.parse().page("certification").body[-1].value["steps"]

        self.assertEqual(process_steps[0]["checklist"][0], "盤點設備")
        self.assertFalse(
            any(
                item.startswith("✓")
                for step in process_steps
                for item in step["checklist"]
            )
        )

    def test_rejects_invalid_contact_email_and_phone(self):
        path = self.html_dir / "index.html"
        original = path.read_text(encoding="utf-8")

        replacements = (
            (
                "mailto:MaxYCLee@itri.org.tw",
                "mailto:not-an-email",
                "contact email",
            ),
            (
                "電話：02-23116228 #202",
                "電話：請來信洽詢",
                "contact phone",
            ),
        )
        for old, new, message in replacements:
            with self.subTest(message=message):
                path.write_text(original.replace(old, new), encoding="utf-8")
                with self.assertRaisesRegex(SourceValidationError, message):
                    self.parse()

        path.write_text(original, encoding="utf-8")

    def test_rejects_contact_values_longer_than_settings_fields(self):
        path = self.html_dir / "index.html"
        source = path.read_text(encoding="utf-8")
        path.write_text(
            source.replace(
                "李先生（認驗證制度與流程）", f"{'李' * 101}（認驗證制度與流程）"
            ),
            encoding="utf-8",
        )

        with self.assertRaisesRegex(SourceValidationError, "contact name"):
            self.parse()

    def test_ecosystem_requires_exactly_two_case_studies(self):
        path = self.html_dir / "ecosystem.html"
        original = path.read_text(encoding="utf-8")

        for mode in ("fewer", "more"):
            with self.subTest(mode=mode):
                soup = BeautifulSoup(original, "html.parser")
                cases = soup.select("#case-studies article")
                if mode == "fewer":
                    cases[-1].decompose()
                else:
                    cases[-1].insert_after(BeautifulSoup(str(cases[-1]), "html.parser"))
                path.write_text(str(soup), encoding="utf-8")

                with self.assertRaisesRegex(
                    SourceValidationError,
                    r"ecosystem\.html.*case-studies",
                ):
                    self.parse()

        path.write_text(original, encoding="utf-8")

    def test_required_asset_name_error_lists_the_conflicting_file(self):
        original = self.asset_dir / "GPM01.jpg"
        intermediate = self.asset_dir / "rename-in-progress.jpg"
        conflict = self.asset_dir / "GPM01.JPG"
        original.rename(intermediate)
        intermediate.rename(conflict)

        with self.assertRaisesRegex(
            SourceValidationError,
            r"GPM01\.jpg.*GPM01\.JPG",
        ):
            self.parse()


class SourceLinkTests(SimpleTestCase):
    def test_normalizes_internal_fragment_placeholder_and_external_links(self):
        self.assertEqual(
            normalize_source_link("首頁", "index.html", "about"),
            SourceLink("首頁", "", None, ""),
        )
        self.assertEqual(
            normalize_source_link("背景", "about.html#background", ""),
            SourceLink("背景", "about", None, "background"),
        )
        self.assertEqual(
            normalize_source_link("文件", "#documents-table", "resources"),
            SourceLink("文件", "resources", None, "documents-table"),
        )
        self.assertEqual(
            normalize_source_link("稍後提供", "#", "resources"),
            SourceLink("稍後提供", None, None, ""),
        )
        self.assertEqual(
            normalize_source_link("公告", "https://moda.gov.tw/news", "resources"),
            SourceLink("公告", None, "https://moda.gov.tw/news", ""),
        )

    def test_rejects_unsafe_or_unknown_links_and_fragments(self):
        for href in (
            "javascript:alert(1)",
            "//evil.example/path",
            "unknown.html",
            "https:",
            "http:relative",
            "mailto:",
            "tel:",
        ):
            with self.subTest(href=href):
                with self.assertRaises(SourceValidationError):
                    normalize_source_link("不安全", href, "about")

        for fragment in ("9bad", "bad fragment", "<script>"):
            with self.subTest(fragment=fragment):
                with self.assertRaises(SourceValidationError):
                    validate_fragment(fragment)
