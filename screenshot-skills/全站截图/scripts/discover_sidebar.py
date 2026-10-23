#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从侧栏展开并收集可访问路由。"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from playwright.sync_api import sync_playwright

PARENTS = [
    "商品管理", "订单管理", "库存管理", "采购管理", "销售管理",
    "财务结算", "用户权限", "系统设置",
]


def expand_parents(page) -> None:
    aside = page.locator("aside").first
    for label in PARENTS:
        el = aside.get_by_text(label, exact=True)
        if el.count():
            try:
                el.first.click(timeout=2000)
                page.wait_for_timeout(350)
            except Exception:
                pass
    # 再点一遍带 chevron 的 button（展开折叠组）
    for btn in aside.locator("button").all():
        try:
            if btn.is_visible():
                btn.click(timeout=500)
                page.wait_for_timeout(120)
        except Exception:
            pass


def is_login(url: str) -> bool:
    p = urlparse(url).path.lower().rstrip("/")
    return p.endswith("/login") or p.endswith("/register")


def main() -> None:
    default_base = os.environ.get("TEST_BASE_URL", "http://your-server:5001").rstrip("/")
    base = sys.argv[1] if len(sys.argv) > 1 else default_base
    storage = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(
        os.environ.get("UI_STORAGE_STATE", "output/.auth/ui_storage.json")
    )
    start = sys.argv[3] if len(sys.argv) > 3 else "首页"
    out = Path(sys.argv[4]) if len(sys.argv) > 4 else Path(
        "output/site-screenshots/discovered_sidebar_routes.json"
    )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(storage_state=str(storage), viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        page.goto(urljoin(base.rstrip("/") + "/", "products"), wait_until="networkidle", timeout=120_000)

        for _ in range(4):
            expand_parents(page)
            page.wait_for_timeout(500)

        aside = page.locator("aside").first
        lines = [ln.strip() for ln in aside.inner_text().splitlines() if ln.strip()]
        print(f"侧栏共 {len(lines)} 项")

        hrefs: list[dict] = []
        for a in aside.locator("a[href]").all():
            try:
                text = re.sub(r"\s+", " ", a.inner_text(timeout=500).strip())
                href = a.get_attribute("href") or ""
                if text and href and not href.startswith("#"):
                    hrefs.append({"text": text, "href": href})
            except Exception:
                pass
        print(f"侧栏链接 {len(hrefs)} 个")

        try:
            idx = lines.index(start)
        except ValueError:
            idx = next((i for i, ln in enumerate(lines) if start in ln), 0)

        routes: list[dict] = []
        seen: set[str] = set()
        for label in lines[idx:]:
            expand_parents(page)
            try:
                el = aside.get_by_text(label, exact=True).first
                if not el.is_visible():
                    continue
                el.click(timeout=5000)
                page.wait_for_timeout(1000)
                url = page.url
                if is_login(url) or url in seen:
                    continue
                seen.add(url)
                title = page.title()
                routes.append({"label": label, "url": url, "title": title, "path": urlparse(url).path})
                print(f"  {label} -> {url} | {title}")
            except Exception as ex:
                print(f"  skip {label}: {ex}")

        browser.close()

    payload = {"lines": lines, "hrefs": hrefs, "routes": routes}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n收集 {len(routes)} 条路由 -> {out}")


if __name__ == "__main__":
    main()
