"""登录态检测与自动登录（秒杀财务 Web 前端）。"""
from __future__ import annotations

import os
import re
from typing import Any

from playwright.sync_api import Page

from .locator_resolver import resolve_string
from .context import UIContext


_DEFAULT_LOGIN_HINTS = ("/login", "/register", "/auth/login")


def is_login_url(url: str, *, login_paths: tuple[str, ...] | None = None) -> bool:
    path = url.lower()
    hints = login_paths or _DEFAULT_LOGIN_HINTS
    return any(h in path for h in hints)


def ensure_logged_in(
    page: Page,
    base_url: str,
    target_path: str,
    *,
    ctx: UIContext | None = None,
    login_path: str | None = None,
    username: str | None = None,
    password: str | None = None,
    wait_until: str = "networkidle",
    timeout_ms: int = 120_000,
) -> None:
    """打开 target_path；若跳转到登录页则自动填表登录后再进入目标页。"""
    base = base_url.rstrip("/")
    path = target_path if target_path.startswith("/") else "/" + target_path
    timeout_ms = int(timeout_ms)
    session_reuse = os.environ.get("UI_SESSION_PAGE", "").strip().lower() in ("1", "true", "yes", "on")

    if session_reuse and page.url and page.url not in ("about:blank", "") and not is_login_url(page.url):
        if path.rstrip("/") not in page.url.rstrip("/"):
            page.goto(base + path, wait_until="domcontentloaded", timeout=timeout_ms)
        return

    page.goto(base + path, wait_until=wait_until, timeout=timeout_ms)

    login_hints = _DEFAULT_LOGIN_HINTS
    if login_path:
        login_hints = login_hints + (login_path,)

    if not is_login_url(page.url, login_paths=login_hints):
        return

    user = username
    pwd = password
    if ctx is not None:
        if not user:
            v = ctx.get("username")
            user = str(v) if v is not None else None
        if not pwd:
            v = ctx.get("password")
            pwd = str(v) if v is not None else None
    user = user or os.environ.get("TEST_USERNAME", "admin")
    pwd = pwd or os.environ.get("TEST_PASSWORD", "")

    user_input = page.locator(
        'input[placeholder="用户名"], #form_item_username, '
        'input[name="username"], #username, input[autocomplete="username"]'
    ).first
    pwd_input = page.locator(
        'input[placeholder="密码"], #form_item_password, '
        'input[type="password"], input[name="password"]'
    ).first
    user_input.wait_for(state="visible", timeout=timeout_ms)
    pwd_input.wait_for(state="visible", timeout=timeout_ms)
    user_input.fill(user, timeout=timeout_ms)
    pwd_input.fill(pwd, timeout=timeout_ms)
    page.wait_for_timeout(300)
    _click_login_submit(page, timeout_ms=timeout_ms)
    if is_login_url(page.url, login_paths=login_hints):
        page.wait_for_function(
            "() => !/\\/(login|register)(?:\\?|$)/i.test(window.location.pathname)",
            timeout=timeout_ms,
        )
    page.wait_for_load_state(wait_until, timeout=timeout_ms)

    if is_login_url(page.url, login_paths=login_hints):
        raise RuntimeError("ensure_logged_in: 登录失败，请检查 TEST_USERNAME/TEST_PASSWORD 或 storage_state")

    if path not in page.url:
        page.goto(base + path, wait_until=wait_until, timeout=timeout_ms)


def _click_login_submit(page: Page, *, timeout_ms: int) -> None:
    """提交登录表单；优先精确「登录」按钮，避免误点其它入口。"""
    attempts: list[tuple[str, Any]] = [
        ("submit", lambda: page.locator('button[type="submit"]').first),
        ("exact-zh", lambda: page.get_by_role("button", name=re.compile(r"^登\s*录$", re.I)).first),
        ("exact-en", lambda: page.get_by_role("button", name=re.compile(r"^Login$", re.I)).first),
        ("primary", lambda: page.locator("button.bg-primary").first),
    ]
    last_err: Exception | None = None
    for _name, get_loc in attempts:
        try:
            loc = get_loc()
            loc.click(timeout=timeout_ms)
            return
        except Exception as exc:  # noqa: BLE001
            last_err = exc
    raise RuntimeError("ensure_logged_in: 未找到可点击的登录按钮") from last_err


def run_ensure_logged_in_step(
    page: Page,
    step: dict[str, Any],
    *,
    base_url: str,
    ctx: UIContext | None = None,
) -> None:
    path = resolve_string(step.get("path") or step.get("target_path") or "/", ctx or UIContext())
    ensure_logged_in(
        page,
        base_url,
        path,
        ctx=ctx,
        login_path=step.get("login_path"),
        username=step.get("username"),
        password=step.get("password"),
        wait_until=str(step.get("wait_until") or "networkidle"),
        timeout_ms=int(step.get("timeout_ms") or 120_000),
    )
