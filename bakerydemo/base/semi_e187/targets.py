from dataclasses import dataclass
from typing import Literal

from wagtail.models import Page

from bakerydemo.base.models import HomePage, StandardPage

from .schema import ImportPlan


class TargetValidationError(ValueError):
    """Raised when existing Wagtail pages conflict with the import plan."""


@dataclass(frozen=True)
class PageSnapshot:
    id: int
    path: str
    depth: int
    live: bool
    show_in_menus: bool
    slug: str
    title: str
    parent_id: int | None


@dataclass(frozen=True)
class TargetAction:
    action: Literal["create", "update"]
    slug: str
    page_id: int | None


@dataclass(frozen=True)
class TargetSummary:
    home: HomePage
    pages: tuple[TargetAction, ...]
    untouched: tuple[PageSnapshot, ...]


def _snapshot(page: Page) -> PageSnapshot:
    parent = page.get_parent()
    return PageSnapshot(
        id=page.pk,
        path=page.path,
        depth=page.depth,
        live=page.live,
        show_in_menus=page.show_in_menus,
        slug=page.slug,
        title=page.title,
        parent_id=parent.pk if parent else None,
    )


def validate_targets(plan: ImportPlan, home_id: int) -> TargetSummary:
    home = Page.objects.filter(pk=home_id).specific().first()
    if home is None:
        raise TargetValidationError(f"找不到 Home ID {home_id}。")
    if not isinstance(home, HomePage):
        raise TargetValidationError(
            f"Home ID {home_id} 必須是 HomePage，實際為 {type(home).__name__}。"
        )

    actions = []
    target_ids = set()
    for page_import in plan.pages:
        matches = list(Page.objects.filter(slug=page_import.slug).specific())
        if len(matches) > 1:
            raise TargetValidationError(
                f"slug {page_import.slug} 出現多次，無法判斷匯入目標。"
            )
        if not matches:
            actions.append(TargetAction("create", page_import.slug, None))
            continue

        target = matches[0]
        if not isinstance(target, StandardPage):
            raise TargetValidationError(
                f"slug {page_import.slug} 必須是 StandardPage，"
                f"實際為 {type(target).__name__}。"
            )
        if target.get_parent().pk != home.pk:
            raise TargetValidationError(
                f"slug {page_import.slug} 必須是 Home ID {home.pk} 的直接子頁。"
            )
        target_ids.add(target.pk)
        actions.append(TargetAction("update", page_import.slug, target.pk))

    untouched = tuple(
        _snapshot(page)
        for page in Page.objects.exclude(pk__in={home.pk, *target_ids})
        .exclude(depth=1)
        .order_by("pk")
        .specific()
    )
    return TargetSummary(
        home=home,
        pages=tuple(actions),
        untouched=untouched,
    )


def format_dry_run(plan: ImportPlan, targets: TargetSummary) -> str:
    lines = [
        "SEMI E187 匯入預覽",
        "",
        "輸入",
        "  HTML：index.html、about.html、resources.html、certification.html、ecosystem.html",
        f"  圖片目錄：{plan.assets[0].path.parent if plan.assets else '無'}",
        "",
        "Home",
        f"  Home ID {targets.home.pk}：更新",
        "",
        "頁面",
    ]
    for target in targets.pages:
        action = "建立" if target.action == "create" else "更新"
        suffix = f"（ID {target.page_id}）" if target.page_id else ""
        lines.append(f"  {target.slug}：{action}{suffix}")

    lines.extend(["", "內容區塊"])
    lines.append(f"  Home：{len(plan.home.body)}")
    lines.extend(f"  {page.slug}：{len(page.body)}" for page in plan.pages)
    lines.extend(["", "圖片"])
    lines.extend(f"  {asset.filename}：驗證完成，待匯入" for asset in plan.assets)
    lines.extend(
        [
            "",
            "連結",
            f"  重寫站內連結：{plan.counts.rewritten_links}",
            f"  停用連結：{plan.counts.disabled_links}",
            "",
            "警告",
        ]
    )
    if plan.warnings:
        lines.extend(
            f"  [{warning.code}] {warning.message}" for warning in plan.warnings
        )
    else:
        lines.append("  無")

    lines.extend(["", "不受影響頁面"])
    if targets.untouched:
        lines.extend(
            f"  {page.title}（{page.slug}，ID {page.id}）" for page in targets.untouched
        )
    else:
        lines.append("  無")
    lines.extend(["", "DRY RUN：未寫入資料庫或媒體檔案。"])
    return "\n".join(lines)
