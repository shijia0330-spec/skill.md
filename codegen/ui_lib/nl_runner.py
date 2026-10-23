"""自然语言 UI 执行（内置，不依赖外部 NL 服务）。"""
from __future__ import annotations

import traceback
from typing import Any

from .context import UIContext
from .nl_parser import parse_nl, parse_nl_to_flow
from .runner import run_ui_flow


def execute_nl(
    text: str,
    *,
    base_url: str | None = None,
    headless: bool = True,
    heal: bool = True,
    parser: str | None = None,
    isolated: bool | None = None,
) -> dict[str, Any]:
    base = base_url or __import__("os").environ.get("TEST_BASE_URL", "http://your-server:5001")
    steps, expects = parse_nl_to_flow(text, base, parser=parser)

    if not steps:
        return {
            "success": False,
            "message": "未能从自然语言解析出任何步骤",
            "steps_parsed": [],
            "step_results": [],
            "error": "empty_steps",
        }

    use_worker = isolated if isolated is not None else __import__("os").environ.get("UI_WORKER", "0") == "1"
    if use_worker:
        from .worker import run_flow_in_worker

        out = run_flow_in_worker(steps, expects=expects, base_url=base, headless=headless, heal=heal)
        out.setdefault("steps_parsed", steps)
        out.setdefault("expects", expects)
        return out

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        return {
            "success": False,
            "message": "需要 playwright: pip install pytest-playwright && playwright install",
            "steps_parsed": steps,
            "step_results": [],
            "error": str(e),
        }

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=headless)
            page = browser.new_page()
            ctx = UIContext()
            run_ui_flow(page, steps, expects=expects, base_url=base, ctx=ctx, heal=heal)
            browser.close()
        return {
            "success": True,
            "message": f"完成 {len(steps)} 步",
            "steps_parsed": steps,
            "expects": expects,
            "step_results": [
                {"index": i + 1, "action": s.get("action"), "status": "passed"} for i, s in enumerate(steps)
            ],
        }
    except Exception as exc:
        return {
            "success": False,
            "message": str(exc),
            "steps_parsed": steps,
            "expects": expects,
            "step_results": [],
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }


def parse_only(text: str, base_url: str | None = None, *, parser: str | None = None) -> dict[str, Any]:
    return parse_nl(text, base_url, parser=parser)
