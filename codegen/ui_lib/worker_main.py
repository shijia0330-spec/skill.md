#!/usr/bin/env python3
"""UI Worker 子进程入口：python worker_main.py config.json result.json"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_CODEGEN = _ROOT / "codegen"
if str(_CODEGEN) not in sys.path:
    sys.path.insert(0, str(_CODEGEN))

from ui_lib.context import UIContext
from ui_lib.runner import run_ui_flow


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: worker_main.py config.json result.json", file=sys.stderr)
        return 2

    cfg = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    res_path = Path(sys.argv[2])
    steps = cfg.get("steps") or []
    expects = cfg.get("expects") or []
    base_url = cfg.get("base_url") or "http://your-server:5001"
    headless = bool(cfg.get("headless", True))
    heal = bool(cfg.get("heal", True))

    result: dict = {
        "success": False,
        "job_id": cfg.get("job_id"),
        "steps_parsed": steps,
        "expects": expects,
        "step_results": [],
    }

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        result["error"] = str(e)
        result["message"] = "playwright 未安装"
        res_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return 1

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=headless)
            page = browser.new_page()
            ctx = UIContext()
            run_ui_flow(page, steps, expects=expects, base_url=base_url, ctx=ctx, heal=heal)
            browser.close()
        result["success"] = True
        result["message"] = f"worker 完成 {len(steps)} 步"
        result["step_results"] = [{"index": i + 1, "action": s.get("action"), "status": "passed"} for i, s in enumerate(steps)]
    except Exception as e:
        result["success"] = False
        result["error"] = str(e)
        result["message"] = str(e)

    res_path.parent.mkdir(parents=True, exist_ok=True)
    res_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
