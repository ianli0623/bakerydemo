from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType


class SourceValidationError(ValueError):
    """Raised when supplied source content does not match the import contract."""


def freeze_value(value):
    if isinstance(value, Mapping):
        return MappingProxyType(
            {key: freeze_value(child) for key, child in value.items()}
        )
    if isinstance(value, (list, tuple)):
        return tuple(freeze_value(child) for child in value)
    return value


@dataclass(frozen=True)
class SourceAsset:
    filename: str
    path: Path
    data: bytes = field(repr=False)
    sha256: str
    title: str
    alt_text: str
    optional: bool = False


@dataclass(frozen=True)
class SourceLink:
    label: str
    target_slug: str | None
    external_url: str | None
    fragment: str


@dataclass(frozen=True)
class BlockImport:
    type: str
    value: Mapping[str, object] | str

    def __post_init__(self):
        object.__setattr__(self, "value", freeze_value(self.value))


@dataclass(frozen=True)
class HomeImport:
    title: str
    seo_title: str
    search_description: str
    hero_badge: str
    hero_text: str
    hero_cta: str
    hero_cta_link: SourceLink
    secondary_hero_cta: str
    secondary_hero_cta_link: SourceLink
    body: tuple[BlockImport, ...]


@dataclass(frozen=True)
class PageImport:
    slug: str
    title: str
    seo_title: str
    search_description: str
    introduction: str
    section_kicker: str
    section_heading: str
    secondary_section_kicker: str
    secondary_section_heading: str
    secondary_section_introduction: str
    body: tuple[BlockImport, ...]


@dataclass(frozen=True)
class SiteSettingsImport:
    title_suffix: str
    site_name: str
    site_tagline: str
    contact_heading: str
    contact_name: str
    contact_context: str
    contact_phone: str
    contact_email: str
    organisation_text: str
    footer_logo: str | None
    navigation_slugs: tuple[str, ...]


@dataclass(frozen=True)
class ImportWarning:
    code: str
    message: str
    source_name: str = ""


@dataclass(frozen=True)
class ImportCounts:
    pages: int
    blocks: int
    assets: int
    links: int
    rewritten_links: int
    disabled_links: int


@dataclass(frozen=True)
class LoadedSources:
    html_dir: Path
    asset_dir: Path
    html: Mapping[str, str]
    assets: Mapping[str, SourceAsset]
    warnings: tuple[ImportWarning, ...]

    def __post_init__(self):
        object.__setattr__(self, "html", freeze_value(self.html))
        object.__setattr__(self, "assets", freeze_value(self.assets))


@dataclass(frozen=True)
class ImportPlan:
    home: HomeImport
    pages: tuple[PageImport, ...]
    settings: SiteSettingsImport
    assets: tuple[SourceAsset, ...]
    warnings: tuple[ImportWarning, ...]
    counts: ImportCounts

    def page(self, slug: str) -> PageImport:
        for page in self.pages:
            if page.slug == slug:
                return page
        raise KeyError(slug)
