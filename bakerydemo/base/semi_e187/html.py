import re
from collections.abc import Iterable, Sequence
from html import escape
from urllib.parse import urlsplit

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

from ..link_validation import validate_external_url
from .schema import SourceValidationError

ALLOWED_TAGS = {"p", "br", "strong", "b", "em", "i", "ul", "ol", "li", "a"}
ALLOWED_ATTRIBUTES = {"a": {"href"}}
DISCARDED_TAGS = {"script", "style"}


def parse_html(source_html: str) -> BeautifulSoup:
    return BeautifulSoup(source_html, "html.parser")


def require_one(root: Tag | BeautifulSoup, selector: str, source_name: str) -> Tag:
    matches = root.select(selector)
    if len(matches) != 1:
        raise SourceValidationError(
            f"{source_name}：{selector} 預期 1 個，實際 {len(matches)} 個"
        )
    return matches[0]


def require_text(root: Tag | BeautifulSoup, selector: str, source_name: str) -> str:
    tag = require_one(root, selector, source_name)
    value = normalize_text(tag.get_text(" ", strip=True))
    if not value:
        raise SourceValidationError(f"{source_name}：{selector} 不可為空白")
    return value


def require_count(
    items: Sequence[Tag],
    expected: int,
    source_name: str,
    section: str,
) -> None:
    if len(items) != expected:
        raise SourceValidationError(
            f"{source_name}：{section} 預期 {expected} 個，實際 {len(items)} 個"
        )


def normalize_text(value: str) -> str:
    return " ".join(value.split())


def _safe_href(value: str) -> bool:
    if not value or value.startswith("//"):
        return False
    parsed = urlsplit(value)
    if not parsed.scheme:
        return True
    try:
        validate_external_url(value)
    except ValueError:
        return False
    return True


def _render_node(node: Tag | NavigableString) -> str:
    if isinstance(node, Comment):
        return ""
    if isinstance(node, NavigableString):
        return escape(re.sub(r"\s+", " ", str(node)))
    if node.name in DISCARDED_TAGS:
        return ""

    content = "".join(_render_node(child) for child in node.children)
    if node.name not in ALLOWED_TAGS:
        return content
    if node.name == "br":
        return "<br>"
    if node.name == "a":
        href = str(node.get("href", "")).strip()
        if not _safe_href(href):
            return content
        return f'<a href="{escape(href, quote=True)}">{content.strip()}</a>'
    return f"<{node.name}>{content.strip()}</{node.name}>"


def sanitize_rich_text(nodes: Iterable[Tag | NavigableString]) -> str:
    rendered = "".join(_render_node(node) for node in nodes).strip()
    return re.sub(r">\s+<", "><", rendered)
