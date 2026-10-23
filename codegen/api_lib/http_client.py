"""HTTP 客户端：401 刷新 token、500 重试、超时递增。"""
from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Any, Callable

import requests

from .heal_kb import HealKB
from .token_utils import extract_token
from .variable_pool import VariablePool


class HealingSession(requests.Session):
    """带自愈能力的 Session。"""

    def __init__(
        self,
        *,
        base_url: str,
        auth_config: dict[str, Any] | None = None,
        var_pool: VariablePool | None = None,
        heal_kb: HealKB | None = None,
        max_retries: int = 3,
        retry_statuses: tuple[int, ...] = (500, 502, 503, 504),
    ) -> None:
        super().__init__()
        self.base_url = base_url.rstrip("/")
        self.auth_config = auth_config or {}
        self.var_pool = var_pool or VariablePool()
        self.heal_kb = heal_kb or HealKB()
        self.max_retries = max_retries
        self.retry_statuses = retry_statuses
        self._login_fn: Callable[[], str | None] | None = None
        self.headers["Content-Type"] = "application/json"

    def configure_bearer_login(self, auth: dict[str, Any]) -> None:
        login_path = auth.get("login_path", "/api/auth/login")
        uf = auth.get("username_field", "username")
        pf = auth.get("password_field", "password")
        ue = auth.get("username_env", "TEST_USERNAME")
        pe = auth.get("password_env", "TEST_PASSWORD")

        def _login() -> str | None:
            url = self.base_url + login_path
            payload = {
                uf: os.environ.get(ue, ""),
                pf: os.environ.get(pe, ""),
            }
            r = requests.post(url, json=payload, timeout=30)
            r.raise_for_status()
            data = r.json()
            paths = auth.get("token_json_paths")
            token = extract_token(data, paths if isinstance(paths, list) else None)
            if token:
                self.headers["Authorization"] = f"Bearer {token}"
                self.var_pool.set("token", token)
                self.var_pool.set("access_token", token)
            return token

        self._login_fn = _login
        _login()

    def configure_ui_console_login(self, auth: dict[str, Any]) -> None:
        """UI 登录（含 storage_state）后从 XHR 捕获 Bearer Token。路径由 auth profile 配置。"""
        from playwright.sync_api import sync_playwright

        user = os.environ.get(auth.get("username_env", "TEST_USERNAME"), "admin")
        pwd = os.environ.get(auth.get("password_env", "TEST_PASSWORD"), "admin123")
        tenant = auth.get("tenant_id") or os.environ.get("PERF_TENANT_ID")
        if tenant:
            self.headers["tenant-id"] = str(tenant)

        storage_raw = os.environ.get("UI_STORAGE_STATE") or auth.get("storage_state")
        storage_path: Path | None = None
        if storage_raw:
            p = Path(str(storage_raw))
            storage_path = p if p.is_absolute() else (Path.cwd() / p)

        home_path = str(auth.get("home_path") or "/")
        login_path = str(auth.get("login_path") or "/login")
        api_pattern = str(auth.get("api_capture_pattern") or "/api/")
        wait_api_pattern = str(auth.get("wait_api_pattern") or api_pattern)

        captured: dict[str, str] = {}

        def _on_req(req: Any) -> None:
            if api_pattern not in req.url or "authorization" not in req.headers:
                return
            captured["authorization"] = req.headers["authorization"]

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            ctx_kwargs: dict[str, Any] = {"viewport": {"width": 1440, "height": 900}}
            if storage_path and storage_path.is_file():
                ctx_kwargs["storage_state"] = str(storage_path)
            context = browser.new_context(**ctx_kwargs)
            page = context.new_page()
            page.on("request", _on_req)
            base = self.base_url
            page.goto(f"{base}{home_path}", wait_until="domcontentloaded", timeout=60_000)
            login_hint = login_path.strip("/").split("/")[-1] or "login"
            if login_hint in page.url or "auth/login" in page.url:
                page.goto(f"{base}{login_path}", wait_until="domcontentloaded", timeout=60_000)
                page.locator('input[name="username"]').fill(user, timeout=15_000)
                page.locator('input[type="password"]').fill(pwd, timeout=15_000)
                for name in ("login", "登 录", "登录"):
                    btn = page.get_by_role("button", name=name)
                    if btn.count():
                        btn.first.click()
                        break
                else:
                    page.locator("button.bg-primary, button[type='submit']").first.click()
                page.wait_for_url(
                    lambda url: login_hint not in url.split("?")[0] and "auth/login" not in url,
                    timeout=60_000,
                )
                page.goto(f"{base}{home_path}", wait_until="domcontentloaded", timeout=60_000)
            try:
                page.wait_for_response(
                    lambda r: wait_api_pattern in r.url and r.status == 200,
                    timeout=30_000,
                )
            except Exception:
                page.wait_for_timeout(5000)
            browser.close()

        token_hdr = captured.get("authorization")
        if not token_hdr:
            raise RuntimeError("UI 登录失败：未从 XHR 捕获 Authorization 头")
        self.headers["Authorization"] = token_hdr
        token = token_hdr.replace("Bearer ", "", 1).strip()
        if token:
            self.var_pool.set("token", token)
            self.var_pool.set("access_token", token)

        def _refresh() -> str | None:
            self.configure_ui_console_login(auth)
            return self.var_pool.get("access_token")

        self._login_fn = _refresh

    configure_ui_storage_login = configure_ui_console_login

    def request(self, method: str, url: str, **kwargs: Any) -> requests.Response:  # type: ignore[override]
        timeout = kwargs.get("timeout", 30)
        last_exc: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                resp = super().request(method, url, **kwargs)
            except requests.Timeout as e:
                last_exc = e
                kwargs["timeout"] = min(int(timeout) + 10 * attempt, 120)
                self.heal_kb.record("timeout_increase", url, {"timeout": kwargs["timeout"]})
                if attempt >= self.max_retries:
                    raise
                time.sleep(0.5 * (attempt + 1))
                continue
            except requests.RequestException as e:
                last_exc = e
                if attempt >= self.max_retries:
                    raise
                time.sleep(0.5 * (attempt + 1))
                continue

            if resp.status_code == 401 and self._login_fn and attempt < self.max_retries:
                self.heal_kb.record("token_refresh", url, {"attempt": attempt})
                self._login_fn()
                continue

            if resp.status_code == 429 and attempt < self.max_retries:
                self.heal_kb.record("retry_429", url, {"attempt": attempt})
                retry_after = resp.headers.get("Retry-After")
                try:
                    delay = float(retry_after) if retry_after else 0.5 * (attempt + 1)
                except (TypeError, ValueError):
                    delay = 0.5 * (attempt + 1)
                time.sleep(min(delay, 30.0))
                continue

            if resp.status_code in self.retry_statuses and attempt < self.max_retries:
                self.heal_kb.record("retry_5xx", url, {"status": resp.status_code, "attempt": attempt})
                time.sleep(0.5 * (attempt + 1))
                continue

            return resp

        if last_exc:
            raise last_exc
        raise RuntimeError("请求失败且无响应")


def create_api_session(
    base_url: str,
    auth: dict[str, Any] | None,
    var_pool: VariablePool,
    session_headers: dict[str, Any] | None = None,
    *,
    use_healing: bool = True,
    max_retries: int = 3,
) -> requests.Session:
    if use_healing:
        s: requests.Session = HealingSession(
            base_url=base_url,
            auth_config=auth,
            var_pool=var_pool,
            max_retries=max_retries,
        )
    else:
        s = requests.Session()
        s.headers["Content-Type"] = "application/json"

    if session_headers:
        for k, v in session_headers.items():
            s.headers[k] = str(v)

    if auth and isinstance(s, HealingSession):
        if auth.get("type") == "bearer_login":
            s.configure_bearer_login(auth)
        elif auth.get("type") in ("ui_storage_login", "ui_storage_login"):
            s.configure_ui_console_login(auth)

    return s


def create_anon_session(session_headers: dict[str, Any] | None = None) -> requests.Session:
    s = requests.Session()
    s.headers["Content-Type"] = "application/json"
    if session_headers:
        for k, v in session_headers.items():
            s.headers[k] = str(v)
    return s
