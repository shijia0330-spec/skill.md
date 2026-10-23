"""Appium codegen 增强测试。"""
from __future__ import annotations

import sys
from pathlib import Path

_CODEGEN = Path(__file__).resolve().parent
if str(_CODEGEN) not in sys.path:
    sys.path.insert(0, str(_CODEGEN))

from run_spec import parse_frontmatter, render_appium_pytest  # noqa: E402


def test_appium_codegen_steps_and_setup():
    spec_path = _CODEGEN.parent / "templates" / "appium_e2e.md"
    meta, body = parse_frontmatter(spec_path.read_text(encoding="utf-8"))
    out = render_appium_pytest(meta, body)
    assert 'scope="class"' in out
    assert "_setup_test_data" in out
    assert "pytest_runtest_makereport" in out
    assert "allure_layer" in out
    assert "_swipe(" in out or "_scroll(" in out or "_handle_permission" in out
    assert "APPIUM_ARTIFACTS_DIR" in out
    assert "BASE_URL" in out


def test_appium_seckill_h5_codegen():
    spec_path = _CODEGEN.parent / "templates" / "appium_seckill_h5.md"
    meta, body = parse_frontmatter(spec_path.read_text(encoding="utf-8"))
    out = render_appium_pytest(meta, body)
    assert "_open_url" in out
    assert "browserName" in out or "Chrome" in out
    assert "API_BASE_URL" in out
    assert "find_with_heal" in out or "mobile_lib.locator_healer" in out
    assert "test_init" in out
    assert "192.168" in out or "TEST_BASE_URL" in out


def test_emit_swipe_scroll_permission_in_custom_spec():
    meta = {
        "kind": "appium_pytest",
        "capabilities": {"platformName": "Android", "appPackage": "com.t", "appActivity": ".A"},
        "setup": "none",
        "steps": [
            {"action": "permission_allow"},
            {"action": "swipe", "start_x": 1, "start_y": 2, "end_x": 3, "end_y": 4},
            {"action": "scroll", "direction": "down"},
            {"action": "tap", "x": 10, "y": 20},
        ],
        "expect": [],
    }
    out = render_appium_pytest(meta, "")
    assert "_handle_permission" in out
    assert "_swipe(driver" in out
    assert "_scroll(driver" in out
    assert "_tap(driver" in out
