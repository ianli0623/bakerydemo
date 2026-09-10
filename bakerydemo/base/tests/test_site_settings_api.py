from io import BytesIO
from tempfile import TemporaryDirectory

from django.core.files.images import ImageFile
from django.test import TestCase
from django.test.utils import override_settings
from PIL import Image as PILImage
from wagtail.images import get_image_model
from wagtail.models import Locale, Page, PageViewRestriction, Site

from bakerydemo.base.models import (
    HomePage,
    LocalizedSiteContent,
    SiteSettings,
    StandardPage,
)
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
        cls.zh_locale = Locale.objects.get_or_create(language_code="zh-hant")[0]
        cls.en_locale = Locale.objects.get_or_create(language_code="en")[0]
        cls.root = Page.get_first_root_node()
        cls.home = HomePage(
            title="SEMI E187",
            slug="semi-site",
            locale=cls.zh_locale,
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

        cls.en_home = HomePage(
            title="SEMI E187 Cybersecurity Certification",
            slug="semi-site-en",
            locale=cls.en_locale,
            translation_key=cls.home.translation_key,
            hero_text="Advancing semiconductor equipment cybersecurity",
            hero_cta="About the standard",
        )
        cls.root.add_child(instance=cls.en_home)
        cls.en_home.save_revision().publish()

        cls.en_about = StandardPage(
            title="About the Standard",
            slug="about",
            locale=cls.en_locale,
            translation_key=cls.about.translation_key,
        )
        cls.en_home.add_child(instance=cls.en_about)
        cls.en_about.save_revision().publish()

        cls.en_resources = StandardPage(
            title="Implementation Resources",
            slug="resources",
            locale=cls.en_locale,
            translation_key=cls.resources.translation_key,
        )
        cls.en_home.add_child(instance=cls.en_resources)
        cls.en_resources.save_revision().publish()

        SiteSettings.objects.filter(site=cls.site).delete()
        cls.settings = SiteSettings.objects.create(
            site=cls.site,
            primary_navigation=[
                ("page", cls.home),
                ("page", cls.resources),
                ("page", cls.about),
            ],
        )
        cls.zh_content = LocalizedSiteContent.objects.create(
            site=cls.site,
            locale=cls.zh_locale,
            brand_label="認驗證制度",
            title_suffix="SEMI E187",
            site_name="SEMI E187 半導體設備資安標準",
            site_tagline="推動半導體設備資安",
            contact_heading="半導體智慧製造資安合規諮詢",
            contact_name="李先生",
            contact_context="認驗證制度與流程",
            contact_phone="02-23116228 #202",
            contact_email="MaxYCLee@itri.org.tw",
            footer_introduction="歡迎聯絡推動辦公室。",
            organisation_text=(
                "© SEMI E187 Semiconductor Equipment Cybersecurity "
                "Certification Scheme. 內容經由 ACW 官方指南編修。"
            ),
        )
        cls.en_content = LocalizedSiteContent.objects.create(
            site=cls.site,
            locale=cls.en_locale,
            translation_key=cls.zh_content.translation_key,
            brand_label="Certification Scheme",
            title_suffix="SEMI E187",
            site_name="SEMI E187 Semiconductor Equipment Cybersecurity Standard",
            site_tagline="Advancing semiconductor equipment cybersecurity",
            contact_heading="Semiconductor Cybersecurity Compliance Consultation",
            contact_name="Mr. Lee",
            contact_context="Certification scheme and process",
            contact_phone="02-23116228 #202",
            contact_email="MaxYCLee@itri.org.tw",
            footer_introduction="Contact the program office for assistance.",
            organisation_text="© SEMI E187. Adapted from the official ACW guide.",
        )

    def get_settings(self, locale="zh-hant"):
        return self.client.get(
            "/api/site-settings/",
            {"locale": locale},
            HTTP_HOST="localhost",
        )

    def test_endpoint_returns_only_public_fields_and_explicit_live_navigation(self):
        response = self.get_settings()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "locale": "zh-hant",
                "home_page_id": self.home.pk,
                "home_path": "/zh-tw/",
                "brand_label": "認驗證制度",
                "title_suffix": "SEMI E187",
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
                "footer_introduction": "歡迎聯絡推動辦公室。",
                "footer_logo": None,
                "navigation": [
                    {
                        "id": self.home.pk,
                        "title": "SEMI E187",
                        "slug": "",
                        "path": "/zh-tw/",
                    },
                    {
                        "id": self.resources.pk,
                        "title": "資源中心",
                        "slug": "resources",
                        "path": "/zh-tw/resources/",
                    },
                    {
                        "id": self.about.pk,
                        "title": "認識標準",
                        "slug": "about",
                        "path": "/zh-tw/about/",
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
        self.assertEqual(
            response.json()["contact"]["phone_href"],
            "tel:+886223116228,202",
        )

    def test_english_settings_return_english_navigation_paths(self):
        response = self.get_settings("en")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["locale"], "en")
        self.assertEqual(payload["home_page_id"], self.en_home.pk)
        self.assertEqual(payload["home_path"], "/en/")
        self.assertEqual(payload["brand_label"], "Certification Scheme")
        self.assertEqual(payload["site_name"], self.en_content.site_name)
        self.assertEqual(
            payload["footer_introduction"], self.en_content.footer_introduction
        )
        self.assertEqual(
            payload["navigation"],
            [
                {
                    "id": self.en_home.pk,
                    "title": self.en_home.title,
                    "slug": "",
                    "path": "/en/",
                },
                {
                    "id": self.en_resources.pk,
                    "title": "Implementation Resources",
                    "slug": "resources",
                    "path": "/en/resources/",
                },
                {
                    "id": self.en_about.pk,
                    "title": "About the Standard",
                    "slug": "about",
                    "path": "/en/about/",
                },
            ],
        )

    def test_each_locale_uses_its_own_contact_details(self):
        self.en_content.contact_phone = "+1 408 555 0187"
        self.en_content.contact_email = "english@example.com"
        self.en_content.save()

        response = self.get_settings("en")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["contact"]["phone"], "+1 408 555 0187")
        self.assertEqual(
            response.json()["contact"]["phone_href"],
            "tel:+14085550187",
        )
        self.assertEqual(
            response.json()["contact"]["email"],
            "english@example.com",
        )

    def test_missing_locale_defaults_to_traditional_chinese(self):
        response = self.client.get("/api/site-settings/", HTTP_HOST="localhost")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["locale"], "zh-hant")
        self.assertEqual(response.json()["home_page_id"], self.home.pk)

    def test_unsupported_locale_is_rejected(self):
        response = self.get_settings("de")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"error": "Unsupported locale: de"})

    def test_missing_or_unpublished_site_content_does_not_fall_back(self):
        self.en_content.live = False
        self.en_content.save()

        response = self.get_settings("en")

        self.assertEqual(response.status_code, 404)

    def test_missing_or_unpublished_page_translation_does_not_fall_back(self):
        self.en_about.live = False
        self.en_about.save()

        response = self.get_settings("en")

        self.assertEqual(response.status_code, 404)

    def test_restricted_translated_navigation_page_returns_not_found(self):
        PageViewRestriction.objects.create(
            page=self.en_resources,
            restriction_type=PageViewRestriction.PASSWORD,
            password="secret",
        )

        response = self.get_settings("en")

        self.assertEqual(response.status_code, 404)

    def test_invalid_editor_contact_values_do_not_break_the_endpoint(self):
        self.zh_content.contact_phone = "請來信洽詢"
        self.zh_content.contact_email = "not-an-email"
        self.zh_content.save()

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
