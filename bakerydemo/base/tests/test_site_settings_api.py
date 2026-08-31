from io import BytesIO
from tempfile import TemporaryDirectory

from django.core.files.images import ImageFile
from django.test import TestCase
from django.test.utils import override_settings
from PIL import Image as PILImage
from wagtail.images import get_image_model
from wagtail.models import Page, PageViewRestriction, Site

from bakerydemo.base.models import HomePage, SiteSettings, StandardPage
from bakerydemo.base.public_api import phone_to_href


def make_test_image_file(name):
    buffer = BytesIO()
    PILImage.new("RGB", (64, 24), "#123456").save(buffer, "PNG")
    return ImageFile(BytesIO(buffer.getvalue()), name=name)


class PhoneHrefTests(TestCase):
    def test_taiwan_landline_and_extension_are_normalized(self):
        self.assertEqual(
            phone_to_href("02-23116228 #202"),
            "tel:+886223116228,202",
        )

    def test_empty_phone_stays_empty(self):
        self.assertEqual(phone_to_href(""), "")

    def test_nonempty_phone_without_digits_is_rejected(self):
        with self.assertRaises(ValueError):
            phone_to_href("請來信洽詢")


class SiteSettingsApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.root = Page.get_first_root_node()
        cls.home = HomePage(
            title="SEMI E187",
            slug="semi-site",
            hero_text="推動半導體設備資安",
            hero_cta="認識標準",
        )
        cls.root.add_child(instance=cls.home)
        cls.home.save_revision().publish()

        cls.site = Site.objects.get(hostname="localhost", port=80)
        cls.site.root_page = cls.home
        cls.site.is_default_site = True
        cls.site.save()

        cls.about = StandardPage(title="認識標準", slug="about")
        cls.home.add_child(instance=cls.about)
        cls.about.save_revision().publish()

        cls.resources = StandardPage(title="資源中心", slug="resources")
        cls.home.add_child(instance=cls.resources)
        cls.resources.save_revision().publish()

        cls.draft = StandardPage(title="草稿頁", slug="draft", live=False)
        cls.home.add_child(instance=cls.draft)
        cls.draft.save_revision()

        cls.unrelated = StandardPage(
            title="不相關頁面",
            slug="unrelated",
            show_in_menus=True,
        )
        cls.home.add_child(instance=cls.unrelated)
        cls.unrelated.save_revision().publish()

        SiteSettings.objects.filter(site=cls.site).delete()
        cls.settings = SiteSettings.objects.create(
            site=cls.site,
            site_name="SEMI E187 半導體設備資安標準",
            site_tagline="推動半導體設備資安",
            contact_heading="半導體智慧製造資安合規諮詢",
            contact_name="李先生",
            contact_context="認驗證制度與流程",
            contact_phone="02-23116228 #202",
            contact_email="MaxYCLee@itri.org.tw",
            organisation_text=(
                "© SEMI E187 Semiconductor Equipment Cybersecurity "
                "Certification Scheme. 內容經由 ACW 官方指南編修。"
            ),
            primary_navigation=[
                ("page", cls.home),
                ("page", cls.resources),
                ("page", cls.draft),
                ("page", cls.about),
            ],
        )

    def get_settings(self):
        return self.client.get("/api/site-settings/", HTTP_HOST="localhost")

    def test_endpoint_returns_only_public_fields_and_explicit_live_navigation(self):
        response = self.get_settings()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "site_name": "SEMI E187 半導體設備資安標準",
                "site_tagline": "推動半導體設備資安",
                "contact": {
                    "heading": "半導體智慧製造資安合規諮詢",
                    "name": "李先生",
                    "context": "認驗證制度與流程",
                    "phone": "02-23116228 #202",
                    "phone_href": "tel:+886223116228,202",
                    "email": "MaxYCLee@itri.org.tw",
                },
                "organisation_text": (
                    "© SEMI E187 Semiconductor Equipment Cybersecurity "
                    "Certification Scheme. 內容經由 ACW 官方指南編修。"
                ),
                "footer_logo": None,
                "navigation": [
                    {"id": self.home.pk, "title": "首頁", "path": "/"},
                    {
                        "id": self.resources.pk,
                        "title": "資源中心",
                        "path": "/resources/",
                    },
                    {
                        "id": self.about.pk,
                        "title": "認識標準",
                        "path": "/about/",
                    },
                ],
            },
        )

    def test_endpoint_does_not_create_a_missing_settings_row(self):
        self.settings.delete()

        response = self.get_settings()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(SiteSettings.objects.filter(site=self.site).count(), 0)
        self.assertEqual(response.json()["navigation"], [])
        self.assertEqual(response.json()["contact"]["phone_href"], "")

    def test_navigation_omits_restricted_and_other_site_pages(self):
        PageViewRestriction.objects.create(
            page=self.resources,
            restriction_type=PageViewRestriction.PASSWORD,
            password="secret",
        )
        other_root = Page(title="Other site", slug="other-site")
        self.root.add_child(instance=other_root)
        other_root.save_revision().publish()
        Site.objects.create(hostname="other.test", root_page=other_root)
        self.settings.primary_navigation = [
            ("page", self.home),
            ("page", self.resources),
            ("page", other_root),
            ("page", self.about),
        ]
        self.settings.save()

        response = self.get_settings()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["id"] for item in response.json()["navigation"]],
            [self.home.pk, self.about.pk],
        )

    def test_invalid_editor_contact_values_do_not_break_the_endpoint(self):
        self.settings.contact_phone = "請來信洽詢"
        self.settings.contact_email = "not-an-email"
        self.settings.save()

        response = self.get_settings()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["contact"]["phone_href"], "")
        self.assertEqual(response.json()["contact"]["email"], "")

    def test_endpoint_is_get_only(self):
        response = self.client.post(
            "/api/site-settings/",
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 405)

    def test_footer_logo_uses_a_bounded_public_rendition(self):
        with (
            TemporaryDirectory() as media_root,
            override_settings(MEDIA_ROOT=media_root),
        ):
            logo = get_image_model().objects.create(
                title="SEMI E187 footer logo",
                file=make_test_image_file("footer-logo.png"),
            )
            self.settings.footer_logo = logo
            self.settings.save()

            response = self.get_settings()

        self.assertEqual(response.status_code, 200)
        footer_logo = response.json()["footer_logo"]
        self.assertEqual(footer_logo["id"], logo.pk)
        self.assertEqual(footer_logo["title"], "SEMI E187 footer logo")
        self.assertEqual(footer_logo["meta"]["rendition"]["width"], 64)
        self.assertEqual(footer_logo["meta"]["rendition"]["height"], 24)
        self.assertIn("max-320x96", footer_logo["meta"]["rendition"]["url"])
