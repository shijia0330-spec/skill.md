"""保存 UI 控制台 Playwright storage_state（供 spec / 压测复用登录态）。"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

_PKG_ROOT = Path(__file__).resolve().parents[3]
if str(_PKG_ROOT / "codegen") not in sys.path:
    sys.path.insert(0, str(_PKG_ROOT / "codegen"))

from ui_lib.auth import _click_login_submit  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="保存 UI 登录态 storage_state")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("TEST_BASE_URL", "http://your-server:5001"),
    )
    parser.add_argument(
        "--login-path",
        default=os.environ.get("UI_LOGIN_PATH", "/login"),
    )
    parser.add_argument(
        "--out",
        default=os.environ.get("UI_STORAGE_STATE", "output/.auth/ui_storage.json"),
    )
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args()

    user = os.environ.get("TEST_USERNAME", "admin")
    pwd = os.environ.get("TEST_PASSWORD", "admin123")
    out = (_PKG_ROOT / args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    base = args.base_url.rstrip("/")
    login_url = f"{base}{args.login_path}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headed)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        try:
            page.goto(login_url, wait_until="networkidle")
            if page.locator('input[name="username"]').count():
                page.locator('input[name="username"]').fill(user, timeout=15_000)
            elif page.get_by_label("用户名").count():
                page.get_by_label("用户名").fill(user, timeout=15_000)
            else:
                page.get_by_placeholder("用户名").fill(user, timeout=15_000)
            if page.locator('input[type="password"]').count():
                page.locator('input[type="password"]').fill(pwd, timeout=15_000)
            else:
                page.get_by_label("密码").fill(pwd, timeout=15_000)
            _click_login_submit(page, timeout_ms=15_000)
            page.wait_for_load_state("networkidle")
            context.storage_state(path=str(out))
            print(f"已保存: {out}")
        finally:
            browser.close()


if __name__ == "__main__":
    main()
