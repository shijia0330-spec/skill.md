"""步骤/断言作用域：dialog、表格首行等。"""
from __future__ import annotations

from typing import Any

from playwright.sync_api import Locator, Page

from .locator_resolver import resolve_string
from .context import UIContext


def resolve_scope(page: Page, spec: dict[str, Any], ctx: UIContext) -> Page | Locator:
    """将 scope 字段解析为 Page 或 Locator 根节点。"""
    scope = str(spec.get("scope") or "").strip().lower()
    if scope == "dialog":
        dlg = page.get_by_role("dialog")
        title = spec.get("dialog_title")
        if title:
            title_text = resolve_string(str(title), ctx)
            exact = bool(spec.get("dialog_title_exact", True))
            dlg = dlg.filter(has=page.get_by_text(title_text, exact=exact))
        return dlg.first
    if scope in ("table_first_row", "first_row"):
        rows = page.locator("main .el-table__body-wrapper tbody tr")
        if rows.count() == 0:
            return page.locator("main table").nth(1).locator("tr").first
        return rows.first
    if scope == "main":
        return page.locator("main")
    return page
