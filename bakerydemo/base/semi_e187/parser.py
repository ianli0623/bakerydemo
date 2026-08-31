import hashlib
import re
from collections.abc import Mapping, Sequence
from io import BytesIO
from pathlib import Path
from types import MappingProxyType

from bs4 import NavigableString, Tag
from PIL import Image as PILImage
from PIL import UnidentifiedImageError

from ..contact import phone_to_href, validate_contact_email
from .html import (
    normalize_text,
    parse_html,
    require_count,
    require_one,
    require_text,
    sanitize_rich_text,
)
from .links import normalize_source_link, validate_fragment
from .schema import (
    BlockImport,
    HomeImport,
    ImportCounts,
    ImportPlan,
    ImportWarning,
    LoadedSources,
    PageImport,
    SiteSettingsImport,
    SourceAsset,
    SourceLink,
    SourceValidationError,
)

REQUIRED_HTML = (
    "index.html",
    "about.html",
    "resources.html",
    "certification.html",
    "ecosystem.html",
)
REQUIRED_ASSETS = ("GPM01.jpg", "contret01.jpg", "GPM+contret.jpg")
OPTIONAL_ASSETS = ("adi-logo-white.png",)
ASSET_METADATA = {
    "GPM01.jpg": ("SEMI E187 — GPM01", "均豪精密 AOI 自動光學檢測設備"),
    "contret01.jpg": ("SEMI E187 — contret01", "東捷科技 OHS 自動搬運系統"),
    "GPM+contret.jpg": ("SEMI E187 — GPM+contret", "SEMI E187 合格性驗證成果"),
    "adi-logo-white.png": ("SEMI E187 — ADI logo", "數位發展部數位產業署 ADI Logo"),
}
PAGE_ORDER = ("about", "resources", "certification", "ecosystem")
SETTINGS_FIELD_LIMITS = {
    "site name": 255,
    "site tagline": 255,
    "contact heading": 255,
    "contact name": 100,
    "contact context": 255,
    "contact phone": 64,
    "contact email": 254,
}


def _text(tag: Tag, source_name: str, section: str) -> str:
    value = normalize_text(tag.get_text(" ", strip=True))
    if not value:
        raise SourceValidationError(f"{source_name}：{section} 不可為空白")
    return value


def _settings_text(value: str, field_name: str, source_name: str) -> str:
    if len(value) > SETTINGS_FIELD_LIMITS[field_name]:
        raise SourceValidationError(
            f"{source_name}：{field_name} 超過 "
            f"{SETTINGS_FIELD_LIMITS[field_name]} 個字元"
        )
    return value


def _next_sibling(tag: Tag, name: str, source_name: str, section: str) -> Tag:
    sibling = tag.find_next_sibling(name)
    if sibling is None:
        raise SourceValidationError(f"{source_name}：{section} 缺少 {name}")
    return sibling


def _page_header(soup, source_name: str) -> tuple[str, str, str]:
    title = require_text(soup, "header h1", source_name)
    heading = require_one(soup, "header h1", source_name)
    introduction = _text(
        _next_sibling(heading, "p", source_name, "header introduction"),
        source_name,
        "header introduction",
    )
    seo_title = require_text(soup, "title", source_name)
    return title, introduction, seo_title


def _section_kicker(section: Tag, source_name: str) -> str:
    return require_text(section, ".section-kicker", source_name)


def _link(tag: Tag, current_slug: str) -> SourceLink:
    return normalize_source_link(
        normalize_text(tag.get_text(" ", strip=True)),
        str(tag.get("href", "")),
        current_slug,
    )


def _card_from_heading(heading: Tag, current_slug: str, number: str = "") -> dict:
    container = heading.parent
    paragraphs = container.find_all("p", recursive=False)
    if not paragraphs:
        paragraph = heading.find_next_sibling("p")
        paragraphs = [paragraph] if paragraph else []
    summary = " ".join(
        normalize_text(paragraph.get_text(" ", strip=True))
        for paragraph in paragraphs
        if paragraph is not None
    )
    if not summary:
        raise SourceValidationError(
            f"card：{normalize_text(heading.get_text(' ', strip=True))} 缺少摘要"
        )
    link_tag = container if container.name == "a" else container.find("a")
    eyebrow_tag = container.find("span")
    return {
        "number": number,
        "eyebrow": (
            normalize_text(eyebrow_tag.get_text(" ", strip=True)) if eyebrow_tag else ""
        ),
        "title": normalize_text(heading.get_text(" ", strip=True)),
        "summary": summary,
        "link": _link(link_tag, current_slug) if link_tag else None,
    }


def _card_grid(
    heading: str,
    introduction: str,
    cards: Sequence[dict],
    layout: str,
    eyebrow: str = "",
) -> BlockImport:
    return BlockImport(
        "card_grid",
        {
            "eyebrow": eyebrow,
            "heading": heading,
            "introduction": introduction,
            "layout": layout,
            "cards": tuple(cards),
        },
    )


def _source_asset(path: Path, optional: bool) -> SourceAsset:
    try:
        data = path.read_bytes()
    except OSError as error:
        raise SourceValidationError(f"無法讀取圖片：{path}") from error

    try:
        with PILImage.open(BytesIO(data)) as image:
            image.verify()
            image_format = image.format
    except (OSError, UnidentifiedImageError) as error:
        raise SourceValidationError(f"圖片格式無效：{path.name}") from error

    expected_format = "PNG" if path.suffix.lower() == ".png" else "JPEG"
    if image_format != expected_format:
        raise SourceValidationError(
            f"圖片格式不符：{path.name} 預期 {expected_format}，實際 {image_format}"
        )

    title, alt_text = ASSET_METADATA[path.name]
    return SourceAsset(
        filename=path.name,
        path=path.resolve(),
        data=data,
        sha256=hashlib.sha256(data).hexdigest(),
        title=title,
        alt_text=alt_text,
        optional=optional,
    )


def load_and_validate_sources(html_dir: Path, asset_dir: Path) -> LoadedSources:
    html_dir = Path(html_dir).resolve()
    asset_dir = Path(asset_dir).resolve()
    if not html_dir.is_dir():
        raise SourceValidationError(f"HTML 目錄不存在：{html_dir}")
    if not asset_dir.is_dir():
        raise SourceValidationError(f"圖片目錄不存在：{asset_dir}")

    html = {}
    for filename in REQUIRED_HTML:
        path = html_dir / filename
        if not path.is_file():
            raise SourceValidationError(f"缺少必要 HTML：{filename}")
        try:
            html[filename] = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            raise SourceValidationError(f"無法以 UTF-8 讀取：{filename}") from error

    directory_files = tuple(path for path in asset_dir.iterdir() if path.is_file())
    assets = {}
    for filename in REQUIRED_ASSETS:
        matches = [
            path
            for path in directory_files
            if path.name.casefold() == filename.casefold()
        ]
        if len(matches) != 1 or matches[0].name != filename:
            candidates = ", ".join(str(path.resolve()) for path in matches) or "無"
            raise SourceValidationError(
                f"缺少或名稱不精確的必要圖片：{filename}；候選檔案：{candidates}"
            )
        assets[filename] = _source_asset(matches[0], optional=False)

    warnings = []
    for filename in OPTIONAL_ASSETS:
        matches = [
            path
            for path in directory_files
            if path.name.casefold() == filename.casefold()
        ]
        if not matches:
            warnings.append(
                ImportWarning(
                    "optional-asset-missing",
                    f"未提供選用圖片 {filename}，頁尾將只顯示文字。",
                    filename,
                )
            )
            continue
        if len(matches) != 1 or matches[0].name != filename:
            raise SourceValidationError(f"選用圖片名稱不精確或重複：{filename}")
        assets[filename] = _source_asset(matches[0], optional=True)

    if any("VerB_en.html" in source for source in html.values()):
        warnings.append(
            ImportWarning(
                "language-switch-omitted",
                "未提供 VerB_en.html，英文切換連結不匯入。",
                "VerB_en.html",
            )
        )

    return LoadedSources(
        html_dir=html_dir,
        asset_dir=asset_dir,
        html=MappingProxyType(html),
        assets=MappingProxyType(assets),
        warnings=tuple(warnings),
    )


def parse_home(html: str) -> HomeImport:
    source_name = "index.html"
    soup = parse_html(html)
    header = require_one(soup, "header#home", source_name)
    heading = require_one(header, "h1", source_name)
    badge = heading.find_previous_sibling("div")
    if badge is None:
        raise SourceValidationError(f"{source_name}：hero badge 缺少 div")
    title = _text(heading, source_name, "hero heading")
    tagline_tag = _next_sibling(heading, "p", source_name, "hero tagline")
    _text(tagline_tag, source_name, "hero tagline")
    lead_tag = _next_sibling(
        tagline_tag,
        "p",
        source_name,
        "hero introduction",
    )
    lead = _text(lead_tag, source_name, "hero introduction")
    header_links = header.find_all("a")
    if len(header_links) < 2:
        raise SourceValidationError(f"{source_name}：hero CTA 連結少於 2 個")
    hero_cta = _link(header_links[0], "")
    secondary_hero_cta = _link(header_links[1], "")

    news = require_one(header, 'aside[aria-label="最新消息"]', source_name)
    news_links = news.find_all("a")
    require_count(news_links, 2, source_name, "最新消息")
    news_cards = []
    for link_tag in news_links:
        parts = link_tag.find_all("div", recursive=False)
        require_count(parts, 2, source_name, "最新消息卡片欄位")
        news_cards.append(
            {
                "number": _text(parts[0], source_name, "最新消息日期"),
                "eyebrow": "最新消息",
                "title": _text(parts[1], source_name, "最新消息標題"),
                "summary": _text(parts[1], source_name, "最新消息標題"),
                "link": _link(link_tag, ""),
            }
        )

    topics = require_one(soup, "section#site-sections", source_name)
    topic_links = topics.find_all("a")
    require_count(topic_links, 4, source_name, "site-sections")
    topic_cards = []
    for index, link_tag in enumerate(topic_links, start=1):
        topic_cards.append(
            _card_from_heading(
                require_one(link_tag, "h3", source_name),
                "",
                f"{index:02d}",
            )
        )

    body = (
        _card_grid("最新消息", "", news_cards, "two"),
        _card_grid(
            require_text(topics, "h2", source_name),
            _text(
                _next_sibling(
                    require_one(topics, "h2", source_name),
                    "p",
                    source_name,
                    "site-sections introduction",
                ),
                source_name,
                "site-sections introduction",
            ),
            topic_cards,
            "four",
            "EXPLORE THE SITE",
        ),
    )
    return HomeImport(
        title=title,
        seo_title=require_text(soup, "title", source_name),
        search_description=lead,
        hero_badge=_text(badge, source_name, "hero badge"),
        hero_text=lead,
        hero_cta=hero_cta.label,
        hero_cta_link=hero_cta,
        secondary_hero_cta=secondary_hero_cta.label,
        secondary_hero_cta_link=secondary_hero_cta,
        body=body,
    )


def parse_about(html: str) -> PageImport:
    source_name = "about.html"
    soup = parse_html(html)
    title, introduction, seo_title = _page_header(soup, source_name)
    section = require_one(soup, "section#about", source_name)
    about_heading = require_one(section, "h2", source_name)
    narrative = _next_sibling(
        about_heading,
        "div",
        source_name,
        "about background narrative",
    )
    rich_text = sanitize_rich_text(narrative.contents)
    if not rich_text:
        raise SourceValidationError(f"{source_name}：about background narrative 為空")

    dimension_headings = section.find_all("h4")
    require_count(dimension_headings, 4, source_name, "about dimensions")
    cards = [
        _card_from_heading(heading, "about", f"{index:02d}")
        for index, heading in enumerate(dimension_headings, start=1)
    ]
    dimensions_heading = require_text(section, "h3", source_name)
    return PageImport(
        slug="about",
        title=title,
        seo_title=seo_title,
        search_description=introduction,
        introduction=introduction,
        section_kicker=_section_kicker(section, source_name),
        section_heading=_text(about_heading, source_name, "about heading"),
        secondary_section_kicker="",
        secondary_section_heading="",
        secondary_section_introduction="",
        body=(
            BlockImport("paragraph_block", rich_text),
            _card_grid(dimensions_heading, "", cards, "two"),
        ),
    )


def parse_resources(html: str) -> PageImport:
    source_name = "resources.html"
    soup = parse_html(html)
    title, introduction, seo_title = _page_header(soup, source_name)
    section = require_one(soup, "section#resources", source_name)
    section_heading = require_one(section, "h2", source_name)
    section_intro = _text(
        _next_sibling(
            section_heading,
            "p",
            source_name,
            "resources introduction",
        ),
        source_name,
        "resources introduction",
    )
    articles = section.find_all("article")
    require_count(articles, 3, source_name, "resources cards")
    cards = [
        _card_from_heading(
            require_one(article, "h3", source_name),
            "resources",
            f"{index:02d}",
        )
        for index, article in enumerate(articles, start=1)
    ]

    document_section = require_one(section, "#documents-table", source_name)
    table = require_one(document_section, "table", source_name)
    rows = table.select("tbody tr")
    require_count(rows, 4, source_name, "documents-table rows")
    document_rows = []
    for index, row in enumerate(rows, start=1):
        cells = row.find_all("td", recursive=False)
        require_count(
            cells,
            4,
            source_name,
            f"documents-table row {index}",
        )
        link_tag = cells[3].find("a")
        document_rows.append(
            {
                "number": _text(cells[0], source_name, "document number"),
                "title": _text(cells[1], source_name, "document title"),
                "summary": _text(cells[2], source_name, "document summary"),
                "status": _text(cells[3], source_name, "document status"),
                "link": _link(link_tag, "resources") if link_tag else None,
            }
        )
    direct_heading = document_section.find("div", recursive=False)
    if direct_heading is None:
        raise SourceValidationError(f"{source_name}：documents-table 缺少標題")
    document_table = BlockImport(
        "document_table",
        {
            "heading": _text(direct_heading, source_name, "documents-table heading"),
            "caption": require_text(table, "caption", source_name),
            "anchor_id": validate_fragment(str(document_section.get("id", ""))),
            "rows": tuple(document_rows),
        },
    )
    return PageImport(
        slug="resources",
        title=title,
        seo_title=seo_title,
        search_description=introduction,
        introduction=introduction,
        section_kicker=_section_kicker(section, source_name),
        section_heading=_text(section_heading, source_name, "resources heading"),
        secondary_section_kicker="",
        secondary_section_heading="",
        secondary_section_introduction="",
        body=(
            _card_grid(
                _text(section_heading, source_name, "resources heading"),
                section_intro,
                cards,
                "three",
            ),
            document_table,
        ),
    )


def parse_certification(html: str) -> PageImport:
    source_name = "certification.html"
    soup = parse_html(html)
    title, introduction, seo_title = _page_header(soup, source_name)
    section = require_one(soup, "section#certification", source_name)
    overview_heading = require_one(section, "h2", source_name)
    overview = _next_sibling(
        overview_heading,
        "p",
        source_name,
        "certification overview",
    )

    certified_list = require_one(section, "#certified-list", source_name)
    compliance_headings = certified_list.find_all("h3")
    require_count(compliance_headings, 3, source_name, "certified-list")
    compliance_cards = [
        _card_from_heading(heading, "certification") for heading in compliance_headings
    ]

    process = require_one(section, "#vendor-process", source_name)
    role_headings = [
        heading
        for heading in section.find_all("h4")
        if heading.find_parent(id="vendor-process") is None
    ]
    require_count(role_headings, 3, source_name, "role guidance")
    role_cards = [
        _card_from_heading(heading, "certification") for heading in role_headings
    ]
    role_heading = role_headings[0].find_previous("h3")
    if role_heading is None:
        raise SourceValidationError(f"{source_name}：role guidance 缺少標題")

    step_headings = process.find_all("h4")
    require_count(step_headings, 5, source_name, "vendor-process steps")
    steps = []
    for index, heading in enumerate(step_headings, start=1):
        detail_container = heading.parent
        outer = detail_container.parent
        summary = _text(
            _next_sibling(
                heading,
                "p",
                source_name,
                f"vendor-process step {index} summary",
            ),
            source_name,
            f"vendor-process step {index} summary",
        )
        steps.append(
            {
                "number": f"{index:02d}",
                "title": _text(heading, source_name, f"vendor-process step {index}"),
                "summary": summary,
                "checklist": tuple(
                    _text(
                        item,
                        source_name,
                        f"vendor-process step {index} checklist",
                    )
                    .removeprefix("✓")
                    .strip()
                    for item in detail_container.select("ul li")
                ),
                "resource_links": tuple(
                    _link(link_tag, "certification") for link_tag in outer.find_all("a")
                ),
            }
        )
    process_heading = require_one(process, "h3", source_name)
    process_intro = _text(
        _next_sibling(
            process_heading,
            "p",
            source_name,
            "vendor-process introduction",
        ),
        source_name,
        "vendor-process introduction",
    )
    return PageImport(
        slug="certification",
        title=title,
        seo_title=seo_title,
        search_description=introduction,
        introduction=introduction,
        section_kicker=_section_kicker(section, source_name),
        section_heading=_text(
            overview_heading,
            source_name,
            "certification heading",
        ),
        secondary_section_kicker="",
        secondary_section_heading="",
        secondary_section_introduction="",
        body=(
            BlockImport("paragraph_block", sanitize_rich_text([overview])),
            _card_grid(
                "驗證機構與合規名單",
                "",
                compliance_cards,
                "three",
            ),
            _card_grid(
                _text(role_heading, source_name, "role guidance heading"),
                "",
                role_cards,
                "three",
            ),
            BlockImport(
                "process_steps",
                {
                    "heading": _text(
                        process_heading,
                        source_name,
                        "vendor-process heading",
                    ),
                    "introduction": process_intro,
                    "steps": tuple(steps),
                },
            ),
        ),
    )


def _direct_text(tag: Tag) -> str:
    return normalize_text(
        " ".join(
            str(child) for child in tag.children if isinstance(child, NavigableString)
        )
    )


def _metadata_value(article: Tag, label: str, source_name: str) -> str:
    for tag in article.find_all(["div", "dt"]):
        if _direct_text(tag) != label:
            continue
        sibling = tag.find_next_sibling(["div", "dd"])
        if sibling is not None:
            return _text(sibling, source_name, f"case metadata {label}")
    raise SourceValidationError(f"{source_name}：case metadata 缺少 {label}")


def _case_study(
    article: Tag,
    assets: Mapping[str, SourceAsset],
    source_name: str,
) -> BlockImport:
    heading = require_one(article, "h3", source_name)
    product = _next_sibling(heading, "div", source_name, "case product")
    status = _next_sibling(product, "div", source_name, "case status")
    summary = _next_sibling(status, "p", source_name, "case summary")
    images = article.find_all("img")
    require_count(images, 2, source_name, "case-studies images")
    image_names = [Path(str(image.get("src", ""))).name for image in images]
    for filename in image_names:
        if filename not in assets:
            raise SourceValidationError(
                f"{source_name}：case-studies 引用未提供圖片 {filename}"
            )

    case_headings = article.find_all("h4")
    require_count(case_headings, 2, source_name, "case-studies detail headings")
    challenge_heading, solution_heading = case_headings
    challenge = _next_sibling(
        challenge_heading,
        "p",
        source_name,
        "case challenge",
    )
    solution = _next_sibling(
        solution_heading,
        "p",
        source_name,
        "case solution",
    )
    controls_container = solution.find_next_sibling("div")
    if controls_container is None:
        raise SourceValidationError(f"{source_name}：case-studies 缺少資安控制項")
    control_tags = controls_container.find_all("div", recursive=False)
    if not control_tags:
        raise SourceValidationError(f"{source_name}：case-studies 資安控制項不可為空")
    controls = []
    for control in control_tags:
        parts = control.find_all("div", recursive=False)
        require_count(parts, 2, source_name, "case-studies security control")
        controls.append(
            {
                "title": _text(parts[0], source_name, "security control title"),
                "summary": _text(parts[1], source_name, "security control summary"),
            }
        )

    captions = []
    for image in images:
        caption = image.find_next_sibling("span")
        if caption is None:
            raise SourceValidationError(f"{source_name}：case-studies 圖片缺少圖說")
        captions.append(
            re.sub(
                r"^圖說[:：]\s*",
                "",
                _text(caption, source_name, "case image caption"),
            )
        )

    label = article.find("span")
    if label is None:
        raise SourceValidationError(f"{source_name}：case-studies 缺少案例標籤")
    metadata = tuple(
        {
            "label": metadata_label,
            "value": _metadata_value(article, metadata_label, source_name),
        }
        for metadata_label in ("產業", "產品", "專案性質", "檢測單位")
    )
    return BlockImport(
        "case_study",
        {
            "case_label": _text(label, source_name, "case label"),
            "company": _text(heading, source_name, "case company"),
            "product": _text(product, source_name, "case product"),
            "certification_status": _text(status, source_name, "case status"),
            "summary": _text(summary, source_name, "case summary"),
            "metadata": metadata,
            "equipment_image": image_names[0],
            "equipment_caption": captions[0],
            "challenge_heading": _text(
                challenge_heading,
                source_name,
                "case challenge heading",
            ),
            "challenge": sanitize_rich_text([challenge]),
            "solution_heading": _text(
                solution_heading,
                source_name,
                "case solution heading",
            ),
            "solution": sanitize_rich_text([solution]),
            "security_controls_heading": "資安控制重點",
            "security_controls": tuple(controls),
            "outcome_image": image_names[1],
            "outcome_caption": captions[1],
        },
    )


def parse_ecosystem(
    html: str,
    assets: Mapping[str, SourceAsset],
) -> PageImport:
    source_name = "ecosystem.html"
    soup = parse_html(html)
    title, introduction, seo_title = _page_header(soup, source_name)
    section = require_one(soup, "section#ecosystem", source_name)
    section_heading = require_one(section, "h2", source_name)
    overview_headings = section.find_all("h4")
    require_count(overview_headings, 2, source_name, "ecosystem overview cards")
    overview_cards = [
        _card_from_heading(heading, "ecosystem") for heading in overview_headings
    ]
    cases = require_one(soup, "section#case-studies", source_name)
    cases_heading = require_one(cases, "h2", source_name)
    cases_introduction = _text(
        _next_sibling(
            cases_heading,
            "p",
            source_name,
            "case-studies introduction",
        ),
        source_name,
        "case-studies introduction",
    )
    articles = cases.find_all("article")
    require_count(articles, 2, source_name, "case-studies")
    case_blocks = tuple(
        _case_study(article, assets, source_name) for article in articles
    )
    return PageImport(
        slug="ecosystem",
        title=title,
        seo_title=seo_title,
        search_description=introduction,
        introduction=introduction,
        section_kicker=_section_kicker(section, source_name),
        section_heading=_text(section_heading, source_name, "ecosystem heading"),
        secondary_section_kicker=_section_kicker(cases, source_name),
        secondary_section_heading=_text(
            cases_heading,
            source_name,
            "case-studies heading",
        ),
        secondary_section_introduction=cases_introduction,
        body=(
            _card_grid(
                _text(section_heading, source_name, "ecosystem heading"),
                _text(
                    _next_sibling(
                        section_heading,
                        "p",
                        source_name,
                        "ecosystem introduction",
                    ),
                    source_name,
                    "ecosystem introduction",
                ),
                overview_cards,
                "two",
            ),
            *case_blocks,
        ),
    )


def _parse_settings(html: str, assets: Mapping[str, SourceAsset]) -> SiteSettingsImport:
    source_name = "index.html"
    soup = parse_html(html)
    heading = require_one(soup, "header#home h1", source_name)
    heading_text = _text(heading, source_name, "hero heading")
    site_name = heading_text.partition(" 與認驗證制度")[0]
    site_tagline = _text(
        _next_sibling(heading, "p", source_name, "hero tagline"),
        source_name,
        "hero tagline",
    )
    footer = require_one(soup, "footer#contact", source_name)
    contact_heading = require_text(footer, "h2", source_name)
    contact = require_text(footer, "h3", source_name)
    contact_match = re.fullmatch(r"(.+?)[（(](.+?)[）)]", contact)
    if contact_match is None:
        raise SourceValidationError(f"{source_name}：contact 聯絡人格式不符")
    phone_tag = require_one(footer, 'a[href^="tel:"]', source_name)
    email_tag = require_one(footer, 'a[href^="mailto:"]', source_name)
    paragraphs = footer.find_all("p")
    if len(paragraphs) < 2:
        raise SourceValidationError(f"{source_name}：contact 缺少組織說明")
    phone = re.sub(
        r"^電話[:：]\s*",
        "",
        _text(phone_tag, source_name, "contact phone"),
    )
    email_href = str(email_tag.get("href", ""))
    email = email_href.removeprefix("mailto:").strip()
    if not email:
        raise SourceValidationError(f"{source_name}：contact email 不可為空白")
    try:
        phone_to_href(phone)
    except ValueError as error:
        raise SourceValidationError(f"{source_name}：contact phone 格式不符") from error
    try:
        validate_contact_email(email)
    except ValueError as error:
        raise SourceValidationError(f"{source_name}：contact email 格式不符") from error
    return SiteSettingsImport(
        title_suffix="SEMI E187",
        site_name=_settings_text(site_name, "site name", source_name),
        site_tagline=_settings_text(site_tagline, "site tagline", source_name),
        contact_heading=_settings_text(
            contact_heading,
            "contact heading",
            source_name,
        ),
        contact_name=_settings_text(
            contact_match.group(1).strip(),
            "contact name",
            source_name,
        ),
        contact_context=_settings_text(
            contact_match.group(2).strip(),
            "contact context",
            source_name,
        ),
        contact_phone=_settings_text(phone, "contact phone", source_name),
        contact_email=_settings_text(email, "contact email", source_name),
        organisation_text=_text(paragraphs[-1], source_name, "organisation text"),
        footer_logo=("adi-logo-white.png" if "adi-logo-white.png" in assets else None),
        navigation_slugs=("", *PAGE_ORDER),
    )


def _iter_links(value):
    if isinstance(value, SourceLink):
        yield value
    elif isinstance(value, Mapping):
        for child in value.values():
            yield from _iter_links(child)
    elif isinstance(value, (tuple, list)):
        for child in value:
            yield from _iter_links(child)


def assemble_import_plan(
    home: HomeImport,
    pages: Sequence[PageImport],
    sources: LoadedSources,
) -> ImportPlan:
    pages = tuple(pages)
    if tuple(page.slug for page in pages) != PAGE_ORDER:
        raise SourceValidationError(
            "頁面順序必須為 about、resources、certification、ecosystem"
        )
    blocks = (*home.body, *(block for page in pages for block in page.body))
    links = [home.hero_cta_link]
    for block in blocks:
        links.extend(_iter_links(block.value))
    disabled = [
        link for link in links if link.target_slug is None and link.external_url is None
    ]
    warnings = list(sources.warnings)
    warnings.extend(
        ImportWarning(
            "placeholder-link",
            f"「{link.label}」未提供目的地，前台將顯示即將提供。",
        )
        for link in disabled
    )
    return ImportPlan(
        home=home,
        pages=pages,
        settings=_parse_settings(sources.html["index.html"], sources.assets),
        assets=tuple(sources.assets.values()),
        warnings=tuple(warnings),
        counts=ImportCounts(
            pages=1 + len(pages),
            blocks=len(blocks),
            assets=len(sources.assets),
            links=len(links),
            rewritten_links=sum(link.target_slug is not None for link in links),
            disabled_links=len(disabled),
        ),
    )


def parse_source_site(html_dir: Path, asset_dir: Path) -> ImportPlan:
    """Validate and parse all supplied files without database/storage writes."""
    sources = load_and_validate_sources(html_dir, asset_dir)
    home = parse_home(sources.html["index.html"])
    pages = (
        parse_about(sources.html["about.html"]),
        parse_resources(sources.html["resources.html"]),
        parse_certification(sources.html["certification.html"]),
        parse_ecosystem(sources.html["ecosystem.html"], sources.assets),
    )
    return assemble_import_plan(home, pages, sources)
