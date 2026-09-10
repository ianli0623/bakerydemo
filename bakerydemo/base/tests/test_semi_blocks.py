from io import BytesIO
from tempfile import TemporaryDirectory

from django.core.exceptions import ValidationError
from django.core.files.images import ImageFile
from django.test import TestCase
from django.test.utils import override_settings
from PIL import Image as PILImage
from wagtail.blocks import ListBlockValidationError, StructBlockValidationError
from wagtail.images import get_image_model
from wagtail.models import Page, Site

from bakerydemo.base import blocks
from bakerydemo.base.models import StandardPage


def make_test_image_file(name):
    buffer = BytesIO()
    PILImage.new("RGB", (32, 24), "#123456").save(buffer, "JPEG")
    return ImageFile(BytesIO(buffer.getvalue()), name=name)


class ContentLinkBlockTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.root = Page.get_first_root_node()
        cls.site = Site.objects.create(
            hostname="testserver",
            root_page=cls.root,
            is_default_site=True,
        )
        cls.about = StandardPage(title="認識標準", slug="about")
        cls.root.add_child(instance=cls.about)
        cls.about.save_revision().publish()

    def test_placeholder_link_has_a_disabled_api_representation(self):
        block_class = getattr(blocks, "ContentLinkBlock", None)
        self.assertIsNotNone(
            block_class,
            "ContentLinkBlock must model editor-visible links and placeholders",
        )

        block = block_class()
        value = block.to_python(
            {
                "label": "下載 FAQ",
                "internal_page": None,
                "external_url": "",
                "fragment": "",
            }
        )

        self.assertEqual(
            block.get_api_representation(value),
            {
                "label": "下載 FAQ",
                "kind": "disabled",
                "href": None,
                "new_tab": False,
            },
        )

    def test_optional_empty_link_stays_absent(self):
        block = blocks.ContentLinkBlock(required=False)
        value = block.normalize({})

        self.assertEqual(block.clean(value), value)
        self.assertIsNone(block.get_api_representation(value))

    def test_persisted_empty_link_stays_absent_from_the_api(self):
        block = blocks.ContentLinkBlock(required=False)
        value = block.to_python({})

        self.assertIsNone(block.get_api_representation(value))

    def test_persisted_missing_optional_link_can_be_published(self):
        block = blocks.ContentLinkBlock(required=False)
        value = block.to_python({})

        cleaned = block.clean(value)

        self.assertIsNone(block.get_api_representation(cleaned))

    def test_persisted_empty_optional_link_can_be_published(self):
        block = blocks.ContentLinkBlock(required=False)
        value = block.to_python(
            {
                "label": "",
                "internal_page": None,
                "external_url": "",
                "fragment": "",
            }
        )

        self.assertEqual(block.clean(value), value)

    def test_link_destination_requires_a_label(self):
        block = blocks.ContentLinkBlock(required=False)
        value = block.to_python(
            {
                "label": "",
                "internal_page": None,
                "external_url": "https://example.com",
                "fragment": "",
            }
        )

        with self.assertRaises(StructBlockValidationError) as raised:
            block.clean(value)

        self.assertIn("label", raised.exception.block_errors)

    def test_http_link_has_an_external_api_representation(self):
        block = blocks.ContentLinkBlock()
        value = block.to_python(
            {
                "label": "官方公告",
                "internal_page": None,
                "external_url": "https://moda.gov.tw/notice#semi-e187",
                "fragment": "",
            }
        )

        self.assertEqual(
            block.get_api_representation(value),
            {
                "label": "官方公告",
                "kind": "external",
                "href": "https://moda.gov.tw/notice#semi-e187",
                "new_tab": True,
            },
        )

    def test_contact_links_are_external_without_opening_a_new_tab(self):
        block = blocks.ContentLinkBlock()

        for external_url in (
            "mailto:MaxYCLee@itri.org.tw",
            "tel:+886223116228,202",
        ):
            with self.subTest(external_url=external_url):
                value = block.to_python(
                    {
                        "label": "聯絡窗口",
                        "internal_page": None,
                        "external_url": external_url,
                        "fragment": "",
                    }
                )
                self.assertEqual(
                    block.get_api_representation(value),
                    {
                        "label": "聯絡窗口",
                        "kind": "external",
                        "href": external_url,
                        "new_tab": False,
                    },
                )

    def test_unsafe_external_scheme_is_rejected(self):
        block = blocks.ContentLinkBlock()
        value = block.to_python(
            {
                "label": "不安全連結",
                "internal_page": None,
                "external_url": "javascript:alert(1)",
                "fragment": "",
            }
        )

        with self.assertRaises(StructBlockValidationError) as raised:
            block.clean(value)

        self.assertIn("external_url", raised.exception.block_errors)

    def test_incomplete_external_destinations_are_rejected(self):
        block = blocks.ContentLinkBlock()

        for external_url in ("https:", "http:relative", "mailto:", "tel:"):
            with self.subTest(external_url=external_url):
                value = block.to_python(
                    {
                        "label": "無效連結",
                        "internal_page": None,
                        "external_url": external_url,
                        "fragment": "",
                    }
                )
                with self.assertRaises(StructBlockValidationError):
                    block.clean(value)

    def test_internal_and_external_destinations_cannot_both_be_set(self):
        block = blocks.ContentLinkBlock()
        value = block.to_python(
            {
                "label": "衝突連結",
                "internal_page": None,
                "external_url": "https://example.com",
                "fragment": "",
            }
        )
        value["internal_page"] = Page.get_first_root_node()

        with self.assertRaises(StructBlockValidationError) as raised:
            block.clean(value)

        self.assertEqual(
            set(raised.exception.block_errors),
            {"internal_page", "external_url"},
        )

    def test_fragment_requires_an_internal_page(self):
        block = blocks.ContentLinkBlock()
        value = block.to_python(
            {
                "label": "文件表格",
                "internal_page": None,
                "external_url": "",
                "fragment": "documents-table",
            }
        )

        with self.assertRaises(StructBlockValidationError) as raised:
            block.clean(value)

        self.assertIn("fragment", raised.exception.block_errors)

    def test_fragment_must_be_a_safe_anchor(self):
        block = blocks.ContentLinkBlock()
        value = block.to_python(
            {
                "label": "不安全片段",
                "internal_page": None,
                "external_url": "",
                "fragment": "documents table<script>",
            }
        )
        value["internal_page"] = Page.get_first_root_node()

        with self.assertRaises(StructBlockValidationError) as raised:
            block.clean(value)

        self.assertIn("fragment", raised.exception.block_errors)

    def test_internal_page_keeps_a_safe_fragment_in_its_api_path(self):
        block = blocks.ContentLinkBlock()
        value = block.to_python(
            {
                "label": "背景介紹",
                "internal_page": self.about.pk,
                "external_url": "",
                "fragment": "background",
            }
        )

        self.assertEqual(
            block.get_api_representation(value),
            {
                "label": "背景介紹",
                "kind": "internal",
                "href": "/about/#background",
                "new_tab": False,
            },
        )


class StructuredContentBlockTests(TestCase):
    def test_base_stream_block_exposes_the_structured_content_contract(self):
        block = blocks.BaseStreamBlock()

        self.assertTrue(
            {
                "heading_block",
                "paragraph_block",
                "image_block",
                "block_quote",
                "embed_block",
                "card_grid",
                "document_table",
                "process_steps",
                "case_study",
            }.issubset(block.child_blocks),
        )
        self.assertEqual(
            set(block.child_blocks["card_grid"].child_blocks),
            {"eyebrow", "heading", "introduction", "layout", "cards"},
        )
        self.assertEqual(
            set(block.child_blocks["document_table"].child_blocks),
            {"heading", "caption", "anchor_id", "rows"},
        )
        self.assertEqual(
            set(block.child_blocks["process_steps"].child_blocks),
            {"heading", "introduction", "steps"},
        )
        self.assertEqual(
            set(block.child_blocks["case_study"].child_blocks),
            {
                "case_label",
                "company",
                "product",
                "certification_status",
                "summary",
                "metadata",
                "equipment_image",
                "equipment_caption",
                "challenge_heading",
                "challenge",
                "solution_heading",
                "solution",
                "security_controls_heading",
                "security_controls",
                "outcome_image",
                "outcome_caption",
            },
        )

    def test_structured_collections_require_at_least_one_item(self):
        required_lists = (
            (blocks.CardGridBlock(), "cards"),
            (blocks.DocumentTableBlock(), "rows"),
            (blocks.ProcessStepsBlock(), "steps"),
            (blocks.CaseStudyBlock(), "metadata"),
            (blocks.CaseStudyBlock(), "security_controls"),
        )

        for block, field_name in required_lists:
            with self.subTest(block=type(block).__name__, field=field_name):
                with self.assertRaises(ListBlockValidationError):
                    block.child_blocks[field_name].clean([])

    def test_document_anchor_rejects_unsafe_markup(self):
        anchor_block = blocks.DocumentTableBlock().child_blocks["anchor_id"]

        with self.assertRaises(ValidationError):
            anchor_block.clean("documents-table<script>")

    def test_case_study_api_contains_both_image_renditions(self):
        with (
            TemporaryDirectory() as media_root,
            override_settings(MEDIA_ROOT=media_root),
        ):
            image = get_image_model().objects.create(
                title="GPM equipment",
                description="GPM 自動光學檢測設備",
                file=make_test_image_file("GPM01.jpg"),
            )
            block = blocks.CaseStudyBlock()
            value = block.to_python(
                {
                    "case_label": "案例一",
                    "company": "均豪精密",
                    "product": "AOI 自動光學檢測設備",
                    "certification_status": "通過驗證",
                    "summary": "設備資安驗證案例",
                    "metadata": [{"label": "產品", "value": "AOI"}],
                    "equipment_image": image.pk,
                    "equipment_caption": "設備實體照",
                    "challenge_heading": "挑戰",
                    "challenge": "<p>建立設備安全基線。</p>",
                    "solution_heading": "解決方案",
                    "solution": "<p>完成合規驗證。</p>",
                    "security_controls_heading": "資安控制重點",
                    "security_controls": [
                        {"title": "帳號安全", "summary": "強化權限管理"}
                    ],
                    "outcome_image": image.pk,
                    "outcome_caption": "合格性驗證成果",
                }
            )

            representation = block.get_api_representation(value)

            for field_name in ("equipment_image", "outcome_image"):
                with self.subTest(field=field_name):
                    image_data = representation[field_name]
                    self.assertIsInstance(image_data, dict)
                    self.assertEqual(image_data["id"], image.pk)
                    self.assertEqual(image_data["title"], "GPM equipment")
                    self.assertEqual(
                        set(image_data["meta"]["rendition"]),
                        {"url", "full_url", "width", "height", "alt"},
                    )

            html = block.render(value)
            self.assertIn("<article", html)
            self.assertIn("<dl", html)
            self.assertEqual(html.count("<figure"), 2)
            self.assertIn("建立設備安全基線", html)
            self.assertEqual(
                representation["security_controls_heading"], "資安控制重點"
            )

    def test_card_grid_fallback_is_semantic_and_disables_placeholder_links(self):
        block = blocks.CardGridBlock()
        value = block.to_python(
            {
                "eyebrow": "網站主題專區",
                "heading": "認識 SEMI E187",
                "introduction": "四個標準面向",
                "layout": "two",
                "cards": [
                    {
                        "number": "01",
                        "eyebrow": "標準",
                        "title": "認識標準",
                        "summary": "了解標準背景。",
                        "link": {
                            "label": "下載指南",
                            "internal_page": None,
                            "external_url": "",
                            "fragment": "",
                        },
                    }
                ],
            }
        )

        html = block.render(value)

        self.assertIn("<section", html)
        self.assertIn("<article", html)
        self.assertIn("即將提供", html)
        self.assertNotIn("<a ", html)

    def test_card_grid_fallback_omits_an_empty_optional_link(self):
        block = blocks.CardGridBlock()
        value = block.to_python(
            {
                "eyebrow": "",
                "heading": "SEMI E187 標準涵蓋四大面向",
                "introduction": "",
                "layout": "two",
                "cards": [
                    {
                        "number": "01",
                        "eyebrow": "",
                        "title": "作業系統規範",
                        "summary": "要求使用長期支援的作業系統版本。",
                        "link": {
                            "label": "",
                            "internal_page": None,
                            "external_url": "",
                            "fragment": "",
                        },
                    }
                ],
            }
        )

        html = block.render(value)

        self.assertNotIn("即將提供", html)
        self.assertNotIn("<a ", html)

    def test_document_table_fallback_has_headers_and_anchor(self):
        block = blocks.DocumentTableBlock()
        value = block.to_python(
            {
                "heading": "官方文件",
                "caption": "SEMI E187 文件清單",
                "anchor_id": "documents-table",
                "rows": [
                    {
                        "number": "01",
                        "title": "驗證制度",
                        "summary": "制度公告",
                        "status": "已公告",
                    }
                ],
            }
        )

        html = block.render(value)

        self.assertIn('id="documents-table"', html)
        self.assertIn("<table", html)
        self.assertIn('<th scope="col">', html)
        self.assertIn("<caption>", html)

    def test_process_steps_fallback_preserves_order_and_checklists(self):
        block = blocks.ProcessStepsBlock()
        value = block.to_python(
            {
                "heading": "設備廠商驗證歷程",
                "introduction": "依序完成五個階段",
                "steps": [
                    {
                        "number": "01",
                        "title": "盤點",
                        "summary": "確認設備範圍",
                        "checklist": ["建立資產清單"],
                        "resource_links": [
                            {
                                "label": "下載表單",
                                "internal_page": None,
                                "external_url": "",
                                "fragment": "",
                            }
                        ],
                    }
                ],
            }
        )

        html = block.render(value)

        self.assertIn("<ol", html)
        self.assertIn("建立資產清單", html)
        self.assertIn("即將提供", html)
