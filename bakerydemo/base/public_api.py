from urllib.parse import urlsplit

from django.http import Http404, JsonResponse
from django.views.decorators.http import require_GET
from wagtail.models import Page, Site

from .blocks import get_image_api_representation
from .contact import phone_to_href, validate_contact_email
from .models import SiteSettings


def serialize_navigation_page(page: Page, site_root_id: int) -> dict[str, object]:
    page = page.specific
    if page.pk == site_root_id:
        path = "/"
        title = "首頁"
    else:
        root_url_path = Page.objects.only("url_path").get(pk=site_root_id).url_path
        if page.url_path.startswith(root_url_path):
            path = f"/{page.url_path.removeprefix(root_url_path).lstrip('/')}"
        else:
            page_url = page.get_url() or "/"
            path = urlsplit(page_url).path or "/"
        title = page.title

    return {"id": page.pk, "title": title, "path": path}


def serialize_public_settings(
    settings: SiteSettings,
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
        "site_name": settings.site_name,
        "site_tagline": settings.site_tagline,
        "contact": {
            "heading": settings.contact_heading,
            "name": settings.contact_name,
            "context": settings.contact_context,
            "phone": settings.contact_phone,
            "phone_href": phone_href,
            "email": email,
        },
        "organisation_text": settings.organisation_text,
        "footer_logo": footer_logo,
        "navigation": navigation,
    }


@require_GET
def public_site_settings(request):
    site = Site.find_for_request(request)
    if site is None:
        raise Http404

    settings = SiteSettings.objects.filter(site=site).first()
    if settings is None:
        settings = SiteSettings(site=site)

    public_navigation_ids = set(
        Page.objects.live()
        .public()
        .descendant_of(site.root_page, inclusive=True)
        .filter(
            content_type__app_label="base",
            content_type__model__in=("homepage", "standardpage"),
        )
        .values_list("pk", flat=True)
    )
    navigation = [
        serialize_navigation_page(child.value, site.root_page_id)
        for child in settings.primary_navigation
        if child.block_type == "page"
        and child.value
        and child.value.pk in public_navigation_ids
    ]
    return JsonResponse(serialize_public_settings(settings, navigation))
