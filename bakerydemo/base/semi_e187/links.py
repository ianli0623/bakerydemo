import re
from pathlib import Path
from urllib.parse import urlsplit

from ..link_validation import validate_external_url
from .schema import SourceLink, SourceValidationError

PAGE_SLUGS = {
    "index.html": "",
    "about.html": "about",
    "resources.html": "resources",
    "certification.html": "certification",
    "ecosystem.html": "ecosystem",
}
FRAGMENT_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_-]*\Z")


def validate_fragment(value: str) -> str:
    if not value:
        return ""
    if not FRAGMENT_PATTERN.fullmatch(value):
        raise SourceValidationError(f"不安全的頁面錨點：{value}")
    return value


def normalize_source_link(label: str, href: str, current_slug: str) -> SourceLink:
    label = " ".join(label.split())
    href = href.strip()
    if href == "#":
        return SourceLink(label, None, None, "")
    if href.startswith("//"):
        raise SourceValidationError(f"不允許的跨站連結：{href}")

    parsed = urlsplit(href)
    if parsed.scheme:
        try:
            external_url = validate_external_url(href)
        except ValueError as error:
            raise SourceValidationError(f"不安全的外部連結：{href}") from error
        return SourceLink(label, None, external_url, "")
    if parsed.netloc:
        raise SourceValidationError(f"不允許的跨站連結：{href}")
    if parsed.query:
        raise SourceValidationError(f"站內連結不可包含查詢參數：{href}")

    if not parsed.path:
        target_slug = current_slug
    else:
        filename = Path(parsed.path).name
        if filename not in PAGE_SLUGS:
            raise SourceValidationError(f"未知的站內頁面：{filename}")
        target_slug = PAGE_SLUGS[filename]

    return SourceLink(
        label,
        target_slug,
        None,
        validate_fragment(parsed.fragment),
    )
