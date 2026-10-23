"""Playwright 步骤解释执行器。"""
from __future__ import annotations

import re
from typing import Any

from playwright.sync_api import Page, expect

from .artifacts import save_failure_artifacts
from .auth import run_ensure_logged_in_step
from .context import UIContext
from .element_ui import expect_form_error, expect_radio_checked, run_click_radio_step
from .expect_healer import is_healable_expect, run_expect_with_healing
from .heal_kb import UIHealKB
from .locator_resolver import (
    click_with_healing,
    fill_with_healing,
    get_locator,
    resolve_string,
)
from .retry import retry_step
from .scopes import resolve_scope
from .selector_registry import merge_registry_step


def _ui_step_title(step: dict[str, Any], step_idx: int) -> str:
    action = str(step.get("action") or "").lower()
    if action == "goto":
        return f"Step {step_idx + 1} · 打开页面 {step.get('path') or '/'}"
    if action in ("ensure_logged_in", "ensure_login"):
        return f"Step {step_idx + 1} · 登录并进入 {step.get('path') or step.get('target_path') or '/'}"
    if action == "click":
        name = step.get("l1_name") or step.get("l1_name_regex") or ""
        return f"Step {step_idx + 1} · 点击「{name}」"
    if action in ("click_radio", "radio_click"):
        return f"Step {step_idx + 1} · 选择 {step.get('value') or ''}"
    if action == "fill":
        label = step.get("l1_label") or step.get("l1_placeholder") or "字段"
        return f"Step {step_idx + 1} · 填写 {label}"
    if action == "wait_timeout_ms":
        return f"Step {step_idx + 1} · 等待 {step.get('ms', 300)}ms"
    return f"Step {step_idx + 1} · {action or 'unknown'}"


_SKIP_STEP_SCREENSHOT = frozenset(
    {
        "wait_timeout_ms",
        "wait_load_state",
        "wait_for_load_state",
        "capture",
    }
)


def _attach_step_screenshot(page: Page, step: dict[str, Any], title: str) -> None:
    from api_lib.allure_helper import attach_page_screenshot, attach_text

    action = str(step.get("action") or "").lower()
    if action in _SKIP_STEP_SCREENSHOT:
        return
    attach_page_screenshot(page, name=f"{title} · 截图")
    if action in ("goto", "ensure_logged_in", "ensure_login"):
        attach_text("当前 URL", page.url)


def _expect_title(ex: dict[str, Any], expect_idx: int) -> str:
    t = str(ex.get("type") or "").strip().lower()
    if t == "visible_text":
        return f"断言 {expect_idx + 1} · 文本可见「{ex.get('text', '')}」"
    if t == "alert_visible":
        return f"断言 {expect_idx + 1} · 提示可见「{ex.get('text', '')}」"
    if t in ("role_visible", "columnheader_visible"):
        return f"断言 {expect_idx + 1} · {ex.get('l1_name') or ex.get('role') or t}"
    if t == "table_row_count":
        return f"断言 {expect_idx + 1} · 表格 {ex.get('count', 0)} 行"
    if t in ("form_error_visible", "form_error"):
        return f"断言 {expect_idx + 1} · 表单错误"
    if t in ("radio_checked", "radio_selected"):
        return f"断言 {expect_idx + 1} · 单选 {ex.get('value', '')}"
    return f"断言 {expect_idx + 1} · {t or 'unknown'}"


def _run_single_expect(page: Page, ex: dict[str, Any], ctx: UIContext) -> None:
    t = str(ex.get("type") or "").strip().lower()
    if is_healable_expect(ex):
        run_expect_with_healing(page, ex, ctx)
        return
    if t == "hidden":
        loc = _expect_scope(page, ex, ctx)
        expect(loc).to_be_hidden(timeout=int(ex.get("timeout_ms") or 5000))
    elif t == "input_value":
        ex = merge_registry_step(ex)
        mini = {
            k: ex[k]
            for k in ("l1_placeholder", "l1_label", "l1_test_id", "l2_css")
            if k in ex
        }
        loc = _loc_l1_on_root(page, mini, ctx)
        if loc is None:
            raise RuntimeError("input_value 需要 l1_placeholder / l1_label 等定位字段")
        expect(loc).to_have_value(resolve_string(ex.get("value", ""), ctx))
    elif t == "table_row_count":
        rows = page.locator("main .el-table__body-wrapper tbody tr")
        if rows.count() == 0:
            rows = page.locator("main table").nth(1).locator("tr")
        expected = int(ex.get("count", 0))
        timeout = int(ex.get("timeout_ms") or 5000)
        page.wait_for_timeout(200)
        deadline = timeout
        while deadline > 0 and rows.count() != expected:
            page.wait_for_timeout(200)
            deadline -= 200
        assert rows.count() == expected, f"期望 {expected} 行，实际 {rows.count()} 行"
    elif t in ("form_error_visible", "form_error"):
        expect_form_error(page, ex, ctx)
    elif t in ("radio_checked", "radio_selected"):
        expect_radio_checked(page, ex, ctx)
    else:
        raise RuntimeError(f"未知 expect type: {t}")


def _expect_scope(page: Page, ex: dict[str, Any], ctx: UIContext) -> Page | Locator:
    return resolve_scope(page, ex, ctx)


def _expect_locator(page: Page, ex: dict[str, Any], ctx: UIContext) -> Locator:
    ex = merge_registry_step(ex)
    root = _expect_scope(page, ex, ctx)
    t = str(ex.get("type") or "").strip().lower()

    if t in ("role_visible", "columnheader_visible"):
        role = ex.get("l1_role") or ex.get("role")
        if t == "columnheader_visible" and not role:
            role = "columnheader"
        if not role:
            raise RuntimeError(f"{t} 需要 l1_role 或 role")
        if ex.get("l1_name_regex"):
            return root.get_by_role(
                str(role),
                name=re.compile(resolve_string(str(ex["l1_name_regex"]), ctx)),
            )
        if ex.get("l1_name"):
            return root.get_by_role(str(role), name=resolve_string(str(ex["l1_name"]), ctx))
        return root.get_by_role(str(role))

    if t == "alert_visible":
        text = resolve_string(ex.get("text", ""), ctx)
        loc = root.get_by_role("alert")
        if text:
            loc = loc.filter(has_text=text)
        return loc.first

    if t == "visible_text":
        text = resolve_string(ex.get("text", ""), ctx)
        exact = bool(ex.get("exact", False))
        loc = root.get_by_text(text, exact=exact)
        if ex.get("use_first", True):
            loc = loc.first
        return loc

    if t in ("locator_visible", "visible"):
        mini = {
            k: ex[k]
            for k in (
                "l1_test_id",
                "l1_label",
                "l1_placeholder",
                "l1_role",
                "l1_name",
                "l1_name_regex",
                "l2_css",
            )
            if k in ex
        }
        if mini:
            if isinstance(root, Page):
                loc = _loc_l1_on_root(root, mini, ctx)
            else:
                loc = _loc_l1_on_root_from_locator(root, mini, ctx)
            if loc is not None:
                return loc
        raise RuntimeError(f"{t} 需要 l1_* 或 l2_css 定位字段")

    raise RuntimeError(f"未知 expect type: {t}")


def _loc_l1_on_root(root: Page, step: dict[str, Any], ctx: UIContext) -> Locator | None:
    if step.get("l1_test_id"):
        return root.get_by_test_id(resolve_string(step["l1_test_id"], ctx))
    if step.get("l1_label"):
        return root.get_by_label(resolve_string(step["l1_label"], ctx))
    if step.get("l1_placeholder"):
        return root.get_by_placeholder(resolve_string(step["l1_placeholder"], ctx))
    role = step.get("l1_role")
    if role and step.get("l1_name_regex"):
        return root.get_by_role(str(role), name=re.compile(resolve_string(step["l1_name_regex"], ctx)))
    if role and step.get("l1_name"):
        return root.get_by_role(str(role), name=resolve_string(step["l1_name"], ctx))
    if step.get("l2_css"):
        return root.locator(resolve_string(step["l2_css"], ctx))
    return None


def _loc_l1_on_root_from_locator(root: Locator, step: dict[str, Any], ctx: UIContext) -> Locator | None:
    if step.get("l1_role") and step.get("l1_name"):
        return root.get_by_role(str(step["l1_role"]), name=resolve_string(str(step["l1_name"]), ctx))
    if step.get("l1_role") and step.get("l1_name_regex"):
        return root.get_by_role(
            str(step["l1_role"]),
            name=re.compile(resolve_string(str(step["l1_name_regex"]), ctx)),
        )
    if step.get("l1_placeholder"):
        return root.get_by_placeholder(resolve_string(step["l1_placeholder"], ctx))
    if step.get("l1_label"):
        return root.get_by_label(resolve_string(step["l1_label"], ctx))
    if step.get("l2_css"):
        return root.locator(resolve_string(step["l2_css"], ctx))
    return None


def run_ui_expects(page: Page, expects: list[dict[str, Any]], ctx: UIContext) -> None:
    from api_lib.allure_helper import report_step

    for i, ex in enumerate(expects or []):
        title = _expect_title(ex, i)
        with report_step(title):
            _run_single_expect(page, ex, ctx)
            _attach_step_screenshot(page, {"action": "expect"}, title)


def _apply_capture(page: Page, capture: dict[str, Any], ctx: UIContext, step_idx: int) -> None:
    for var_name, spec in capture.items():
        if not isinstance(var_name, str) or not var_name.strip():
            continue
        vn = var_name.strip()
        if spec == "url" or (isinstance(spec, dict) and spec.get("from") == "url"):
            ctx.set(vn, page.url)
        elif spec == "title" or (isinstance(spec, dict) and spec.get("from") == "title"):
            ctx.set(vn, page.title())
        elif isinstance(spec, dict):
            from_type = str(spec.get("from") or "text").lower()
            loc = get_locator(page, spec, ctx)
            if from_type == "text":
                ctx.set(vn, loc.inner_text())
            elif from_type in ("locator_text", "locator.text"):
                ctx.set(vn, loc.inner_text())
            elif from_type == "value":
                ctx.set(vn, loc.input_value())
            elif from_type == "attribute":
                attr = spec.get("attr") or "href"
                ctx.set(vn, loc.get_attribute(str(attr)))
            elif from_type == "url_regex":
                pat = spec.get("pattern") or "(.*)"
                group = int(spec.get("group") or 1)
                m = re.search(str(pat), page.url)
                ctx.set(vn, m.group(group) if m else None)
            else:
                raise RuntimeError(f"未知 capture.from: {from_type}")
        elif isinstance(spec, str):
            if spec == "url":
                ctx.set(vn, page.url)
            elif spec == "title":
                ctx.set(vn, page.title())
            else:
                raise RuntimeError(f"未知 capture 简写: {spec}")


def run_ui_step(
    page: Page,
    step: dict[str, Any],
    *,
    ctx: UIContext,
    base_url: str,
    step_idx: int = 0,
    heal_kb: UIHealKB | None = None,
    default_retries: int = 3,
    save_artifacts_on_fail: bool = True,
) -> None:
    action = (step.get("action") or "").lower()
    retries = int(step.get("retry") if step.get("retry") is not None else default_retries)
    timeout_ms = int(step.get("timeout_ms") or 15000)

    def _run() -> None:
        if action == "capture":
            cap = step.get("capture") or {}
            if not cap:
                raise RuntimeError("capture action 需要 capture 字典")
            _apply_capture(page, cap, ctx, step_idx)
            return

        if action == "goto":
            path = resolve_string(step.get("path") or "/", ctx)
            url = base_url.rstrip("/") + path
            page.goto(url)
            page.wait_for_load_state(step.get("wait_until") or "domcontentloaded")
        elif action in ("ensure_logged_in", "ensure_login"):
            run_ensure_logged_in_step(page, step, base_url=base_url, ctx=ctx)
        elif action in ("click_radio", "radio_click"):
            run_click_radio_step(page, step, ctx, timeout_ms=timeout_ms)
        elif action == "fill":
            val = resolve_string(step.get("value", ""), ctx)
            fill_with_healing(page, step, val, ctx, heal_kb=heal_kb, timeout_ms=timeout_ms)
        elif action == "click":
            click_with_healing(page, step, ctx, heal_kb=heal_kb, timeout_ms=timeout_ms)
        elif action == "select_option":
            val = resolve_string(step.get("value", ""), ctx)
            get_locator(page, step, ctx, heal_kb=heal_kb).select_option(val, timeout=timeout_ms)
        elif action == "press":
            page.keyboard.press(resolve_string(step.get("key", "Enter"), ctx))
        elif action == "wait_timeout_ms":
            page.wait_for_timeout(int(step.get("ms", 300)))
        elif action in ("wait_load_state", "wait_for_load_state"):
            page.wait_for_load_state(step.get("wait_until") or "domcontentloaded")
        elif action == "wait_selector":
            get_locator(page, step, ctx, heal_kb=heal_kb).wait_for(
                state=step.get("state") or "visible",
                timeout=int(step.get("timeout_ms") or 15000),
            )
        elif action == "wait_response":
            pat = resolve_string(step.get("url_regex") or step.get("pattern") or ".*", ctx)
            page.wait_for_response(re.compile(pat), timeout=int(step.get("timeout_ms") or 30000))
        elif action == "hover":
            get_locator(page, step, ctx, heal_kb=heal_kb).hover(timeout=timeout_ms)
        elif action == "upload":
            fp = resolve_string(step.get("file") or step.get("path") or "", ctx)
            get_locator(page, step, ctx, heal_kb=heal_kb).set_input_files(fp, timeout=timeout_ms)
        elif action == "frame_click":
            frame_sel = resolve_string(step.get("frame") or step.get("frame_selector") or "", ctx)
            fl = page.frame_locator(frame_sel)
            if step.get("l2_css"):
                fl.locator(resolve_string(step["l2_css"], ctx)).click(timeout=timeout_ms)
            elif step.get("l1_test_id"):
                fl.get_by_test_id(resolve_string(step["l1_test_id"], ctx)).click(timeout=timeout_ms)
            else:
                raise RuntimeError("frame_click: 需要 frame + l2_css 或 l1_test_id")
        else:
            raise RuntimeError(f"未知 action: {action}")

        cap = step.get("capture")
        if isinstance(cap, dict) and cap:
            _apply_capture(page, cap, ctx, step_idx)

    from api_lib.allure_helper import report_step

    title = _ui_step_title(step, step_idx)
    try:
        with report_step(title):
            retry_step(_run, max_retries=retries)
            _attach_step_screenshot(page, step, title)
    except Exception:
        if save_artifacts_on_fail:
            try:
                save_failure_artifacts(page, f"step_{step_idx}_{action}")
            except Exception:
                pass
        raise


def run_ui_flow(
    page: Page,
    steps: list[dict[str, Any]],
    *,
    expects: list[dict[str, Any]] | None = None,
    base_url: str,
    ctx: UIContext | None = None,
    heal: bool = True,
    default_retries: int = 3,
    pretest: bool = False,
) -> UIContext:
    context = ctx or UIContext()
    kb = UIHealKB() if heal else None

    if pretest:
        from .pretest import assert_readiness

        assert_readiness(base_url)

    for i, step in enumerate(steps):
        run_ui_step(
            page,
            step,
            ctx=context,
            base_url=base_url,
            step_idx=i,
            heal_kb=kb,
            default_retries=default_retries,
        )

    if expects:
        run_ui_expects(page, expects, context)

    return context
