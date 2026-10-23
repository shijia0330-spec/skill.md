#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批量探测控制台路由（非 404）。"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

CANDIDATES = [
    "system/log/operate-log",
    "system/log/login-log",
    "system/oauth2/oauth2/application",
    "system/oauth2/token",
    "system/social/client",
    "system/social/user",
    "system/area",
    "ai/chat",
    "ai/model",
    "ai/image",
    "ai/music",
    "ai/write",
    "ai/mind-map",
    "ai/knowledge",
    "ai/workflow",
    "ai/agent",
    "infra/codegen",
    "infra/codegen/demo",
    "infra/data-source-config",
    "infra/build",
    "infra/swagger",
    "infra/api-access-log",
    "infra/api-error-log",
    "infra/web-socket",
    "infra/file",
    "infra/file-config",
    "infra/job",
    "infra/config",
    "infra/server",
    "infra/druid",
    "infra/redis",
    "infra/skywalking",
    "infra/demo/demo01-contact",
    "infra/demo/demo02-category",
    "infra/demo/demo03-normal",
    "infra/demo/demo03-erp",
    "infra/demo/demo03-inner",
]


def main() -> None:
    default_base = os.environ.get("TEST_BASE_URL", "http://your-server:5001").rstrip("/")
    base = sys.argv[1] if len(sys.argv) > 1 else default_base
    storage = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(
        os.environ.get("UI_STORAGE_STATE", "output/.auth/ui_storage.json")
    )
    out = Path(sys.argv[3]) if len(sys.argv) > 3 else Path(
        "output/site-screenshots/discovered_routes.json"
    )

    ok: list[dict] = []
    seen_paths: set[str] = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(storage_state=str(storage), viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        for path in CANDIDATES:
            page.goto(f"{base.rstrip('/')}/{path.lstrip('/')}", wait_until="domcontentloaded", timeout=30_000)
            page.wait_for_timeout(500)
            if "/auth/login" in page.url:
                print("SESSION_EXPIRED", file=sys.stderr)
                break
            title = page.title()
            norm = urlparse(page.url).path.rstrip("/")
            if "404" in title or norm in seen_paths:
                continue
            seen_paths.add(norm)
            ok.append({"path": path, "url": page.url, "title": title})
            print(f"OK  {path:35} | {title}")
        browser.close()

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(ok, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nFound {len(ok)} routes -> {out}")


if __name__ == "__main__":
    main()
