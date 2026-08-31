from django.core.exceptions import ObjectDoesNotExist
from wagtail.models import Locale, Page

SUPPORTED_LOCALES = ("zh-hant", "en")
DEFAULT_LOCALE = "zh-hant"


class UnsupportedLocale(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(f"Unsupported locale: {code}")


class TranslationUnavailable(LookupError):
    pass


def resolve_locale(code: str) -> Locale:
    if code not in SUPPORTED_LOCALES:
        raise UnsupportedLocale(code)
    return Locale.objects.get(language_code=code)


def translated_page(page: Page, locale: Locale) -> Page:
    try:
        candidate = (
            page if page.locale_id == locale.pk else page.get_translation(locale)
        )
    except ObjectDoesNotExist as error:
        raise TranslationUnavailable from error

    if not candidate.live or candidate.get_view_restrictions().exists():
        raise TranslationUnavailable
    return candidate.specific
