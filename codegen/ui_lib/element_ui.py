"""Element UI / Vben 常用操作（单选、表单校验等）。"""
from __future__ import annotations

from typing import Any

from playwright.sync_api import Locator, Page, expect

from .context import UIContext
from .locator_resolver import resolve_string
from .scopes import resolve_scope


def click_radio(
    root: Page | Locator,
    field_label: str,
    option: str,
    *,
    timeout_ms: int = 15000,
) -> None:
    """在表单项范围内点击单选项（Element UI / Vben / role=radio）。"""
    # 1) Element UI
    item = root.locator(".el-form-item").filter(has_text=field_label)
    if item.count() > 0:
        radio = item.locator(".el-radio").filter(has_text=option)
        if radio.count() > 0:
            radio.first.click(timeout=timeout_ms)
            return
        opt = item.get_by_text(option, exact=True)
        if opt.count() > 0:
            opt.first.click(timeout=timeout_ms)
            return

    # 2) ARIA radio（Vben / shadcn）
    scoped = root.get_by_role("radio", name=option)
    if scoped.count() > 0:
        scoped.first.click(timeout=timeout_ms)
        return

    # 3) 含字段标签的区块内点选项文案
    block = root.locator("div, fieldset, section").filter(has_text=field_label)
    if block.count() > 0:
        opt = block.first.get_by_text(option, exact=True)
        if opt.count() > 0:
            opt.first.click(timeout=timeout_ms)
            return

    # 4) 弹窗内直接点选项（最后兜底）
    root.get_by_text(option, exact=True).first.click(timeout=timeout_ms)


def run_click_radio_step(
    page: Page,
    step: dict[str, Any],
    ctx: UIContext,
    *,
    timeout_ms: int = 15000,
) -> None:
    field = resolve_string(step.get("field_label") or step.get("label") or "", ctx)
    option = resolve_string(step.get("value") or step.get("option") or "", ctx)
    if not option:
        raise RuntimeError("click_radio 需要 value")
    root = resolve_scope(page, step, ctx)
    if not field:
        root.get_by_text(option, exact=True).first.click(
            timeout=int(step.get("timeout_ms") or timeout_ms)
        )
        return
    click_radio(root, field, option, timeout_ms=int(step.get("timeout_ms") or timeout_ms))


def expect_form_error(
    page: Page,
    ex: dict[str, Any],
    ctx: UIContext,
) -> None:
    """断言 .el-form-item__error 可见（可选限定字段 label）。"""
    root = resolve_scope(page, ex, ctx)
    field = ex.get("field_label") or ex.get("label")
    text = resolve_string(ex.get("text", ""), ctx) if ex.get("text") else ""
    timeout = int(ex.get("timeout_ms") or 5000)

    if field:
        item = root.locator(".el-form-item").filter(has_text=resolve_string(str(field), ctx))
        err = item.locator(".el-form-item__error")
    else:
        err = root.locator(".el-form-item__error")

    if text:
        err = err.filter(has_text=text)
    expect(err.first).to_be_visible(timeout=timeout)


def expect_radio_checked(
    page: Page,
    ex: dict[str, Any],
    ctx: UIContext,
) -> None:
    """断言某 form-item 下单选选中项文案。"""
    root = resolve_scope(page, ex, ctx)
    field = resolve_string(str(ex.get("field_label") or ex.get("label") or ""), ctx)
    option = resolve_string(str(ex.get("value") or ex.get("option") or ""), ctx)
    if not field or not option:
        raise RuntimeError("radio_checked 需要 field_label 与 value")
    item = root.locator(".el-form-item").filter(has_text=field)
    checked = item.locator(".el-radio.is-checked, [role='radio'][aria-checked='true']")
    expect(checked.first).to_contain_text(option, timeout=int(ex.get("timeout_ms") or 5000))
