from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404, JsonResponse
from django.views.decorators.http import require_GET
from wagtail.models import Page, Site

from .blocks import get_image_api_representation
from .contact import phone_to_href, validate_contact_email
from .i18n import (
    DEFAULT_LOCALE,
    TranslationUnavailable,
    UnsupportedLocale,
    resolve_locale,
    translated_page,
)
from .models import LocalizedSiteContent, SiteSettings


def localized_path(locale_code: str, slug: str = "") -> str:
    prefix = "/en" if locale_code == "en" else "/zh-tw"
    return f"{prefix}/{slug}/" if slug else f"{prefix}/"


def serialize_navigation_page(
    page: Page,
    locale_code: str,
    home_page_id: int,
) -> dict[str, object]:
    page = page.specific
    slug = "" if page.pk == home_page_id else page.slug

    return {
        "id": page.pk,
        "title": page.title,
        "slug": slug,
        "path": localized_path(locale_code, slug),
    }


def serialize_public_settings(
    settings: SiteSettings,
    localized_content: LocalizedSiteContent,
    locale_code: str,
    home_page: Page,
    navigation: list[dict[str, object]],
) -> dict[str, object]:
    try:
        phone_href = phone_to_href(settings.contact_phone)
    except ValueError:
        phone_href = ""
    try:
        email = validate_contact_email(settings.contact_email)
    except ValueError:
        email = ""
    footer_logo = (
        get_image_api_representation(settings.footer_logo, "max-320x96")
        if settings.footer_logo
        else None
    )
    return {
        "locale": locale_code,
        "home_page_id": home_page.pk,
        "home_path": localized_path(locale_code),
        "brand_label": localized_content.brand_label,
        "title_suffix": localized_content.title_suffix,
        "site_name": localized_content.site_name,
        "site_tagline": localized_content.site_tagline,
        "contact": {
            "heading": localized_content.contact_heading,
            "name": localized_content.contact_name,
            "context": localized_content.contact_context,
            "phone": settings.contact_phone,
            "phone_href": phone_href,
            "email": email,
        },
        "footer_introduction": localized_content.footer_introduction,
        "organisation_text": localized_content.organisation_text,
        "footer_logo": footer_logo,
        "navigation": navigation,
    }


@require_GET
def public_site_settings(request):
    site = Site.find_for_request(request)
    if site is None:
        raise Http404

    locale_code = request.GET.get("locale", DEFAULT_LOCALE)
    try:
        locale = resolve_locale(locale_code)
    except UnsupportedLocale as error:
        return JsonResponse({"error": str(error)}, status=400)
    except ObjectDoesNotExist as error:
        raise Http404 from error

    try:
        home_page = translated_page(site.root_page.specific, locale)
    except TranslationUnavailable as error:
        raise Http404 from error

    localized_content = LocalizedSiteContent.for_site_and_locale(site, locale)
    if localized_content is None:
        raise Http404

    settings = SiteSettings.objects.filter(site=site).first()
    if settings is None:
        settings = SiteSettings(site=site)

    canonical_navigation_ids = set(
        Page.objects.descendant_of(site.root_page, inclusive=True)
        .filter(
            content_type__app_label="base",
            content_type__model__in=("homepage", "standardpage"),
        )
        .values_list("pk", flat=True)
    )
    navigation = []
    try:
        for child in settings.primary_navigation:
            if (
                child.block_type != "page"
                or not child.value
                or child.value.pk not in canonical_navigation_ids
            ):
                continue
            page = translated_page(child.value.specific, locale)
            navigation.append(
                serialize_navigation_page(page, locale_code, home_page.pk)
            )
    except TranslationUnavailable as error:
        raise Http404 from error

    return JsonResponse(
        serialize_public_settings(
            settings,
            localized_content,
            locale_code,
            home_page,
            navigation,
        )
    )
