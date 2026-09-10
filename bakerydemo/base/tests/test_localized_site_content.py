from django.db import IntegrityError, transaction
from django.test import TestCase
from wagtail.models import Locale, Site

from bakerydemo.base.models import LocalizedSiteContent


class LocalizedSiteContentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.site = Site.objects.get(is_default_site=True)
        cls.zh_locale = Locale.objects.get_or_create(language_code="zh-hant")[0]
        cls.en_locale = Locale.objects.get_or_create(language_code="en")[0]
        cls.zh_content = LocalizedSiteContent.objects.create(
            site=cls.site,
            locale=cls.zh_locale,
            brand_label="認驗證制度",
            site_name="SEMI E187 半導體設備資安標準",
        )

    def test_site_content_is_unique_per_site_and_locale(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                LocalizedSiteContent.objects.create(
                    site=self.site,
                    locale=self.zh_locale,
                    site_name="Duplicate",
                )

    def test_published_translation_can_be_edited_independently(self):
        english = self.zh_content.copy_for_translation(self.en_locale)
        english.site_name = "SEMI E187 Cybersecurity Certification"
        english.save()
        english.save_revision().publish()

        self.zh_content.refresh_from_db()
        self.assertEqual(
            self.zh_content.site_name,
            "SEMI E187 半導體設備資安標準",
        )
        self.assertEqual(
            LocalizedSiteContent.for_site_and_locale(self.site, self.en_locale),
            english,
        )

    def test_only_live_site_content_is_returned(self):
        self.zh_content.live = False
        self.zh_content.save()

        self.assertIsNone(
            LocalizedSiteContent.for_site_and_locale(self.site, self.zh_locale)
        )
