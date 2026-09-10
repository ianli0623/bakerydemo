from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from django.db import transaction
from wagtail.images import get_image_model
from wagtail.models import Collection, Locale, Page, Site

from bakerydemo.base.i18n import resolve_locale
from bakerydemo.base.models import HomePage, LocalizedSiteContent, StandardPage

from .publisher import (
    COLLECTION_NAME,
    apply_page_content,
    refresh_import_indexes,
)
from .schema import ImportPlan

PAGE_SLUGS = ("about", "resources", "certification", "ecosystem")
LOCALIZED_CONTENT_FIELDS = (
    "brand_label",
    "title_suffix",
    "site_name",
    "site_tagline",
    "contact_heading",
    "contact_name",
    "contact_context",
    "contact_phone",
    "contact_email",
    "footer_introduction",
    "organisation_text",
)


class TranslationPublishError(RuntimeError):
    """Raised when English translations cannot be created safely."""


@dataclass(frozen=True)
class TranslationTargets:
    source_pages: Mapping[str, Page]
    images: Mapping[str, object]
    site: Site
    source_content: LocalizedSiteContent
    source_locale: Locale
    target_locale: Locale | None

    def __post_init__(self):
        object.__setattr__(
            self,
            "source_pages",
            MappingProxyType(dict(self.source_pages)),
        )
        object.__setattr__(self, "images", MappingProxyType(dict(self.images)))


@dataclass(frozen=True)
class TranslationPublishResult:
    page_ids: Mapping[str, int]
    image_ids: Mapping[str, int]
    localized_content_id: int

    def __post_init__(self):
        object.__setattr__(self, "page_ids", MappingProxyType(dict(self.page_ids)))
        object.__setattr__(self, "image_ids", MappingProxyType(dict(self.image_ids)))


def _load_source_pages(home_id: int, *, for_update: bool) -> dict[str, Page]:
    home_query = HomePage.objects
    if for_update:
        home_query = home_query.select_for_update()
    try:
        home = home_query.get(pk=home_id)
    except HomePage.DoesNotExist as error:
        raise TranslationPublishError(
            f"Home ID {home_id} is not an existing HomePage."
        ) from error

    children_query = StandardPage.objects.filter(
        path__startswith=home.path,
        depth=home.depth + 1,
        slug__in=PAGE_SLUGS,
    )
    if for_update:
        children_query = children_query.select_for_update()
    children = {page.slug: page for page in children_query}
    missing = [slug for slug in PAGE_SLUGS if slug not in children]
    if missing:
        raise TranslationPublishError("Missing source pages: " + ", ".join(missing))
    return {"": home, **{slug: children[slug] for slug in PAGE_SLUGS}}


def _load_images(plan: ImportPlan, *, for_update: bool) -> dict[str, object]:
    try:
        collection = Collection.objects.get(name=COLLECTION_NAME)
    except Collection.DoesNotExist as error:
        raise TranslationPublishError(
            f"Image collection {COLLECTION_NAME!r} does not exist."
        ) from error
    except Collection.MultipleObjectsReturned as error:
        raise TranslationPublishError(
            f"Multiple image collections are named {COLLECTION_NAME!r}."
        ) from error

    image_query = get_image_model().objects.filter(collection=collection)
    if for_update:
        image_query = image_query.select_for_update()
    images = {}
    for asset in plan.assets:
        matches = list(image_query.filter(title=asset.title).order_by("pk"))
        if len(matches) != 1:
            raise TranslationPublishError(
                f"Expected one reusable image for {asset.filename}; found {len(matches)}."
            )
        images[asset.filename] = matches[0]
    return images


def _assert_no_existing_translations(
    source_pages: Mapping[str, Page],
    site: Site,
    source_content: LocalizedSiteContent,
    target_locale: Locale | None,
) -> None:
    if target_locale is None:
        return
    existing_page_slugs = []
    for slug, page in source_pages.items():
        if (
            Page.objects.filter(
                translation_key=page.translation_key,
                locale=target_locale,
            )
            .exclude(pk=page.pk)
            .exists()
        ):
            existing_page_slugs.append(slug or "home")
    if existing_page_slugs:
        raise TranslationPublishError(
            "English translation already exists for: " + ", ".join(existing_page_slugs)
        )

    if (
        LocalizedSiteContent.objects.filter(
            site=site,
            locale=target_locale,
        )
        .exclude(pk=source_content.pk)
        .exists()
    ):
        raise TranslationPublishError("English localized site content already exists.")


def validate_translation_targets(
    source_plan: ImportPlan,
    home_id: int,
    *,
    for_update: bool = False,
) -> TranslationTargets:
    source_locale = resolve_locale("zh-hant")
    target_locale = Locale.objects.filter(language_code="en").first()
    if for_update and target_locale is None:
        target_locale = Locale.objects.create(language_code="en")
    source_pages = _load_source_pages(home_id, for_update=for_update)
    sites = list(Site.objects.filter(root_page_id=home_id).order_by("pk"))
    if len(sites) != 1:
        raise TranslationPublishError(
            f"Home ID {home_id} must belong to exactly one site; found {len(sites)}."
        )
    site = sites[0]
    try:
        source_content = LocalizedSiteContent.objects.get(
            site=site,
            locale=source_locale,
            live=True,
        )
    except LocalizedSiteContent.DoesNotExist as error:
        raise TranslationPublishError(
            "Published Traditional Chinese site content is missing."
        ) from error
    _assert_no_existing_translations(
        source_pages,
        site,
        source_content,
        target_locale,
    )
    return TranslationTargets(
        source_pages=source_pages,
        images=_load_images(source_plan, for_update=for_update),
        site=site,
        source_content=source_content,
        source_locale=source_locale,
        target_locale=target_locale,
    )


def set_source_locale(source_pages: Mapping[str, Page], locale: Locale) -> None:
    page_ids = [page.pk for page in source_pages.values()]
    Page.objects.filter(pk__in=page_ids).update(locale=locale)
    for page in source_pages.values():
        page.locale = locale


def copy_translation_tree(
    source_pages: Mapping[str, Page],
    locale: Locale,
) -> dict[str, Page]:
    translated_home = (
        source_pages[""]
        .copy_for_translation(
            locale,
            copy_parents=True,
        )
        .specific
    )
    translated_pages = {"": translated_home}
    for slug in PAGE_SLUGS:
        translated_pages[slug] = (
            source_pages[slug]
            .copy_for_translation(
                locale,
                copy_parents=False,
            )
            .specific
        )
    return translated_pages


def _validate_translated_pages(
    source_pages: Mapping[str, Page],
    translated_pages: Mapping[str, Page],
    target_locale: Locale,
) -> None:
    missing = [slug or "home" for slug in source_pages if slug not in translated_pages]
    if missing:
        raise TranslationPublishError(
            "Missing target translations: " + ", ".join(missing)
        )
    for slug, source in source_pages.items():
        translated = translated_pages[slug]
        if translated.locale_id != target_locale.pk:
            raise TranslationPublishError(
                f"Target translation has the wrong locale: {slug or 'home'}."
            )
        if translated.translation_key != source.translation_key:
            raise TranslationPublishError(
                f"Target translation key mismatch: {slug or 'home'}."
            )


def _publish_localized_content(
    targets: TranslationTargets,
    translated_plan: ImportPlan,
) -> LocalizedSiteContent:
    content = targets.source_content.copy_for_translation(targets.target_locale)
    content.site = targets.site
    for field_name in LOCALIZED_CONTENT_FIELDS:
        setattr(content, field_name, getattr(translated_plan.settings, field_name))
    content.save()
    content.save_revision().publish()
    return content


def _publish_transaction(
    source_plan: ImportPlan,
    translated_plan: ImportPlan,
    home_id: int,
) -> tuple[dict[str, Page], Mapping[str, object], LocalizedSiteContent]:
    with transaction.atomic():
        targets = validate_translation_targets(
            source_plan,
            home_id,
            for_update=True,
        )
        set_source_locale(targets.source_pages, targets.source_locale)
        if targets.target_locale is None:
            raise TranslationPublishError("English locale could not be created.")
        translated_pages = copy_translation_tree(
            targets.source_pages,
            targets.target_locale,
        )
        _validate_translated_pages(
            targets.source_pages,
            translated_pages,
            targets.target_locale,
        )
        apply_page_content(translated_plan, translated_pages, targets.images)
        content = _publish_localized_content(targets, translated_plan)
        for page in translated_pages.values():
            page.save_revision().publish()
    return translated_pages, targets.images, content


def publish_translations(
    source_plan: ImportPlan,
    translated_plan: ImportPlan,
    home_id: int,
) -> TranslationPublishResult:
    translated_pages, images, content = _publish_transaction(
        source_plan,
        translated_plan,
        home_id,
    )
    refresh_import_indexes(translated_pages.values())
    return TranslationPublishResult(
        page_ids={slug: page.pk for slug, page in translated_pages.items()},
        image_ids={filename: image.pk for filename, image in images.items()},
        localized_content_id=content.pk,
    )


def format_translation_dry_run(targets: TranslationTargets) -> str:
    lines = [
        "SEMI E187 English translation preview",
        "Source pages to change to zh-hant: 5",
        "English pages to create and publish: 5",
        f"Images to reuse: {len(targets.images)}",
        "DRY RUN: no data was changed.",
    ]
    return "\n".join(lines)


def format_translation_result(result: TranslationPublishResult) -> str:
    return "\n".join(
        (
            "SEMI E187 English translations published",
            f"Published English pages: {len(result.page_ids)}",
            f"Reused images: {len(result.image_ids)}",
            f"Published localized site content: {result.localized_content_id}",
        )
    )
