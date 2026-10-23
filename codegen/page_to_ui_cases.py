#!/usr/bin/env python3
"""
页面 / 用例表 → ui_automation JSON 草稿（与 openapi_to_cases 对称）。

用法:
  # 从秒杀 UI 用例表生成（无需 URL）
  python codegen/page_to_ui_cases.py --from-examples -o output/seckill_ui_cases.json

  # 有 TEST_BASE_URL 时探测 DOM（可选）
  python codegen/page_to_ui_cases.py --inspect /login -o output/login_dom_hints.json

  python codegen/testcase_to_ui_spec.py -i output/seckill_ui_cases.json -o templates/seckill_ui_draft.md
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent


def _seckill_smoke_ui_draft(base_url: str) -> dict[str, Any]:
    """秒杀财务系统 UI 冒烟条目（占位 testid）。"""
    cases_file = ROOT / "examples" / "cases_with_automation.json"
    return {
        "base_url": base_url.rstrip("/"),
        "viewport": {"width": 1440, "height": 900},
        "meta": {
            "source": "examples/cases_with_automation.json",
            "locator_status": "placeholder — 联调前请 --inspect 或 playwright codegen 对齐",
        },
        "cases": json.loads(cases_file.read_text(encoding="utf-8"))["cases"],
    }


def _inspect_page(base_url: str, path: str) -> dict[str, Any]:
    """用 Playwright 抓取表单控件 hint（需已安装 playwright + chromium）。"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise RuntimeError("DOM 探测需要: pip install pytest-playwright && playwright install chromium") from e

    url = base_url.rstrip("/") + (path if path.startswith("/") else "/" + path)
    hints: list[dict[str, Any]] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        for inp in page.locator("input, textarea, select").all()[:20]:
            try:
                hints.append(
                    {
                        "tag": inp.evaluate("el => el.tagName.toLowerCase()"),
                        "type": inp.get_attribute("type"),
                        "id": inp.get_attribute("id"),
                        "name": inp.get_attribute("name"),
                        "placeholder": inp.get_attribute("placeholder"),
                        "aria_label": inp.get_attribute("aria-label"),
                        "data_testid": inp.get_attribute("data-testid"),
                    }
                )
            except Exception:
                continue
        for btn in page.locator("button, input[type=submit]").all()[:10]:
            try:
                hints.append(
                    {
                        "role": "button",
                        "name": btn.inner_text(timeout=1000) if btn else "",
                        "data_testid": btn.get_attribute("data-testid"),
                    }
                )
            except Exception:
                continue
        browser.close()
    return {"url": url, "dom_hints": hints}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-o", "--output", type=Path, required=True)
    ap.add_argument("--base-url", default=os.environ.get("TEST_BASE_URL", "http://your-server:5001"))
    ap.add_argument("--from-examples", action="store_true", help="从秒杀 UI 用例表生成草稿")
    ap.add_argument("--from-seckill-smoke", action="store_true", help="同 --from-examples")
    ap.add_argument("--inspect", metavar="PATH", help="探测页面 DOM（需 TEST_BASE_URL 可访问）")
    ap.add_argument("--merge-seckill", action="store_true", help="与 --inspect 合用：REST 草稿 + dom_hints")
    ns = ap.parse_args()

    out = ns.output if ns.output.is_absolute() else (ROOT / ns.output).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    if ns.from_examples or ns.from_seckill_smoke or ns.merge_seckill:
        draft = _seckill_smoke_ui_draft(ns.base_url)
    else:
        draft = {"base_url": ns.base_url.rstrip("/"), "cases": []}

    if ns.inspect:
        draft["dom_inspect"] = _inspect_page(ns.base_url, ns.inspect)

    out.write_text(json.dumps(draft, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已写入: {out.resolve()}", file=sys.stderr)
    if ns.inspect and draft.get("dom_inspect", {}).get("dom_hints"):
        print(f"  dom_hints: {len(draft['dom_inspect']['dom_hints'])} 条", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
