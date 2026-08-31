import hashlib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from functools import partial
from io import BytesIO
from pathlib import Path
from types import MappingProxyType

from django.core.files.base import ContentFile
from django.db import transaction
from PIL import Image as PILImage
from wagtail.images import get_image_model
from wagtail.models import Collection, Page, ReferenceIndex, Site
from wagtail.search import index as search_index

from bakerydemo.base.models import HomePage, SiteSettings, StandardPage

from .schema import ImportPlan, SourceLink
from .targets import TargetSummary

COLLECTION_NAME = "SEMI E187"
IMAGE_FIELDS = {"equipment_image", "outcome_image"}


class PublishError(RuntimeError):
    """Raised when validated content cannot be published safely."""


@dataclass(frozen=True)
class PublishResult:
    created_pages: int
    updated_pages: int
    created_images: int
    updated_images: int
    reused_images: int
    page_ids: Mapping[str, int]
    image_ids: Mapping[str, int]
    warnings: tuple[str, ...]

    def __post_init__(self):
        object.__setattr__(self, "page_ids", MappingProxyType(dict(self.page_ids)))
        object.__setattr__(self, "image_ids", MappingProxyType(dict(self.image_ids)))


@dataclass
class StorageWriteTracker:
    created_names: list[str] = field(default_factory=list)
    _storage_by_name: dict[str, object] = field(default_factory=dict, repr=False)

    def record(self, storage, name: str) -> None:
        self.created_names.append(name)
        self._storage_by_name[name] = storage

    def remove_created_files(self) -> None:
        for name in reversed(self.created_names):
            storage = self._storage_by_name[name]
            if storage.exists(name):
                storage.delete(name)


def _stored_sha256(image) -> str:
    with image.file.open("rb") as stored:
        return hashlib.sha256(stored.read()).hexdigest()


def _content_filename(filename: str, sha256: str) -> str:
    source = Path(filename)
    stem = source.stem.replace("+", "-").replace(" ", "-")
    return f"{stem}-{sha256[:12]}{source.suffix.lower()}"


def get_or_create_import_collection() -> Collection:
    matches = list(Collection.objects.filter(name=COLLECTION_NAME).order_by("pk"))
    if len(matches) > 1:
        raise PublishError(f"找到多個 {COLLECTION_NAME} 圖片集合，請先整理後再匯入。")
    if matches:
        return matches[0]
    root = Collection.get_first_root_node()
    return root.add_child(instance=Collection(name=COLLECTION_NAME))


def _write_image_file(image, asset, tracker: StorageWriteTracker) -> None:
    image.file.save(
        _content_filename(asset.filename, asset.sha256),
        ContentFile(asset.data),
        save=False,
    )
    tracker.record(image.file.storage, image.file.name)
    with PILImage.open(BytesIO(asset.data)) as source_image:
        image.width, image.height = source_image.size
    try:
        image._set_image_file_metadata()
    finally:
        image.file.close()


def upsert_import_images(
    plan: ImportPlan,
    collection: Collection,
    tracker: StorageWriteTracker,
) -> dict[str, object]:
    image_model = get_image_model()
    images = {}
    for asset in plan.assets:
        matches = list(
            image_model.objects.filter(
                collection=collection,
                title=asset.title,
            ).order_by("pk")
        )
        if len(matches) > 1:
            raise PublishError(f"圖片標題重複：{asset.title}")

        if not matches:
            image = image_model(
                title=asset.title,
                description=asset.alt_text,
                collection=collection,
            )
            _write_image_file(image, asset, tracker)
            image.save()
            action = "created"
        else:
            image = matches[0]
            if _stored_sha256(image) == asset.sha256:
                action = "reused"
                if image.description != asset.alt_text:
                    image.description = asset.alt_text
                    image.save(update_fields=["description"])
            else:
                old_storage = image.file.storage
                old_name = image.file.name
                _write_image_file(image, asset, tracker)
                image.title = asset.title
                image.description = asset.alt_text
                image.save()
                image.renditions.all().delete()
                transaction.on_commit(partial(old_storage.delete, old_name))
                action = "updated"

        image._semi_import_action = action
        images[asset.filename] = image
    return images


def upsert_page_shells(
    plan: ImportPlan,
    targets: TargetSummary,
) -> dict[str, Page]:
    home = HomePage.objects.get(pk=targets.home.pk)
    pages: dict[str, Page] = {"": home}
    actions = {target.slug: target for target in targets.pages}
    for page_import in plan.pages:
        target = actions[page_import.slug]
        if target.action == "create":
            page = StandardPage(
                title=page_import.title,
                slug=page_import.slug,
                live=False,
                show_in_menus=True,
            )
            home.add_child(instance=page)
        else:
            page = StandardPage.objects.get(pk=target.page_id)
        pages[page_import.slug] = page
    return pages


def _thaw_value(
    value, pages: Mapping[str, Page], images: Mapping[str, object], key=None
):
    if key == "link" and value is None:
        return {}
    if isinstance(value, SourceLink):
        return {
            "label": value.label,
            "internal_page": (
                pages[value.target_slug] if value.target_slug is not None else None
            ),
            "external_url": value.external_url or "",
            "fragment": value.fragment,
        }
    if isinstance(value, Mapping):
        return {
            child_key: _thaw_value(child, pages, images, child_key)
            for child_key, child in value.items()
        }
    if isinstance(value, tuple):
        return [_thaw_value(child, pages, images) for child in value]
    if key in IMAGE_FIELDS and isinstance(value, str):
        return images[value]
    return value


def _stream_value(blocks, pages: Mapping[str, Page], images: Mapping[str, object]):
    return [(block.type, _thaw_value(block.value, pages, images)) for block in blocks]


def apply_page_content(
    plan: ImportPlan,
    pages: Mapping[str, Page],
    images: Mapping[str, object],
) -> None:
    home = pages[""]
    home.title = plan.home.title
    home.seo_title = plan.home.seo_title
    home.search_description = plan.home.search_description
    home.hero_text = plan.home.hero_text
    home.hero_cta = plan.home.hero_cta
    home.hero_cta_link = pages[plan.home.hero_cta_link.target_slug]
    home.body = _stream_value(plan.home.body, pages, images)
    home.lead_image = None
    home.lead_title = ""
    home.lead_text = ""
    for index in range(1, 4):
        setattr(home, f"featured_section_{index}_title", "")
        setattr(home, f"featured_section_{index}", None)

    for page_import in plan.pages:
        page = pages[page_import.slug]
        page.title = page_import.title
        page.seo_title = page_import.seo_title
        page.search_description = page_import.search_description
        page.introduction = page_import.introduction
        page.image = None
        page.body = _stream_value(page_import.body, pages, images)
        page.show_in_menus = True


def apply_site_settings(
    plan: ImportPlan,
    pages: Mapping[str, Page],
    images: Mapping[str, object],
) -> None:
    sites = list(Site.objects.filter(root_page_id=pages[""].pk).order_by("pk"))
    if len(sites) != 1:
        raise PublishError(
            f"Home ID {pages[''].pk} 必須對應一個網站，實際 {len(sites)} 個。"
        )
    settings = SiteSettings.for_site(sites[0])
    source = plan.settings
    settings.title_suffix = source.title_suffix
    settings.site_name = source.site_name
    settings.site_tagline = source.site_tagline
    settings.contact_heading = source.contact_heading
    settings.contact_name = source.contact_name
    settings.contact_context = source.contact_context
    settings.contact_phone = source.contact_phone
    settings.contact_email = source.contact_email
    settings.organisation_text = source.organisation_text
    settings.footer_logo = images.get(source.footer_logo)
    settings.primary_navigation = [
        ("page", pages[slug]) for slug in source.navigation_slugs
    ]
    settings.save()
    if ReferenceIndex.is_indexed(settings._meta.model):
        ReferenceIndex.create_or_update_for_object(settings)


def refresh_import_indexes(pages: Iterable[Page]) -> None:
    pages = tuple(pages)
    with transaction.atomic():
        for page in pages:
            if ReferenceIndex.is_indexed(page._meta.model):
                ReferenceIndex.create_or_update_for_object(page)
    for page in pages:
        search_index.insert_or_update_object(page)


def build_publish_result(
    plan: ImportPlan,
    targets: TargetSummary,
    pages: Mapping[str, Page],
    images: Mapping[str, object],
) -> PublishResult:
    image_actions = [image._semi_import_action for image in images.values()]
    return PublishResult(
        created_pages=sum(target.action == "create" for target in targets.pages),
        updated_pages=1 + sum(target.action == "update" for target in targets.pages),
        created_images=image_actions.count("created"),
        updated_images=image_actions.count("updated"),
        reused_images=image_actions.count("reused"),
        page_ids={slug: page.pk for slug, page in pages.items()},
        image_ids={filename: image.pk for filename, image in images.items()},
        warnings=tuple(warning.message for warning in plan.warnings),
    )


def publish_import(plan: ImportPlan, targets: TargetSummary) -> PublishResult:
    tracker = StorageWriteTracker()
    try:
        with transaction.atomic():
            collection = get_or_create_import_collection()
            images = upsert_import_images(plan, collection, tracker)
            pages = upsert_page_shells(plan, targets)
            apply_page_content(plan, pages, images)
            apply_site_settings(plan, pages, images)
            revisions = [page.save_revision() for page in pages.values()]
            for revision in revisions:
                revision.publish()
    except Exception:
        tracker.remove_created_files()
        raise

    refresh_import_indexes(pages.values())
    for image in images.values():
        search_index.insert_or_update_object(image)
    return build_publish_result(plan, targets, pages, images)


def format_publish_result(result: PublishResult) -> str:
    lines = [
        "SEMI E187 發佈完成",
        f"建立頁面：{result.created_pages}",
        f"更新頁面：{result.updated_pages}",
        f"建立圖片：{result.created_images}",
        f"更新圖片：{result.updated_images}",
        f"重用圖片：{result.reused_images}",
    ]
    if result.warnings:
        lines.extend(["警告：", *(f"  {warning}" for warning in result.warnings)])
    return "\n".join(lines)
