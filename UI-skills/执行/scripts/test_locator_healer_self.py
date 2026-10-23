"""locator_healer V3.1 自测 — 需 playwright + chromium。"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_FIXTURE = _ROOT / "UI-skills/分析/scripts/fixtures/sample_page.html"
_HEALER = Path(__file__).resolve().parent / "locator_healer.py"

spec = importlib.util.spec_from_file_location("locator_healer", _HEALER)
healer = importlib.util.module_from_spec(spec)
sys.modules["locator_healer"] = healer
assert spec.loader
spec.loader.exec_module(healer)


def _load_page(pw):
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(_FIXTURE.as_uri())
    return browser, page


def test_l1_testid():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser, page = _load_page(pw)
        try:
            hints = healer.LocatorHints(testid="btn-save")
            loc, meta = healer.resolve_locator(page, hints)
            assert meta.strategy == "testid"
            assert meta.level == "L1"
            assert meta.confidence >= 0.9
            loc.click()
        finally:
            browser.close()


def test_l1_aria_label_heal_from_broken_css():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser, page = _load_page(pw)
        try:
            hints = healer.LocatorHints(aria_label="角色", role="combobox")
            meta = healer.click_with_heal(page, hints, primary_css="#old-role-id")
            assert meta.healed is True
            assert meta.strategy in ("aria-label", "label", "id", "name_attr", "role")
            assert meta.level == "L1"
        finally:
            browser.close()


def test_l2_contains_heal():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser, page = _load_page(pw)
        try:
            hints = healer.LocatorHints(
                text="保存",
                context_scope="form",
                role="button",
            )
            meta = healer.click_with_heal(page, hints, primary_css="#nonexistent-btn")
            assert meta.healed is True
            assert meta.strategy in ("text", "role", "testid", "l2_dom", "l2_context")
        finally:
            browser.close()


def test_failure_candidates_and_error():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser, page = _load_page(pw)
        try:
            hints = healer.LocatorHints(text="完全不存在的按钮xyz")
            try:
                healer.resolve_locator(page, hints, primary_css="#also-missing")
                raise AssertionError("应抛出 LocatorResolutionError")
            except healer.LocatorResolutionError as exc:
                assert len(exc.meta.attempts) >= 1
                assert isinstance(exc.meta.candidates, list)
        finally:
            browser.close()


def test_ui_lib_l1_order():
    sys.path.insert(0, str(_ROOT / "codegen"))
    from ui_lib.context import UIContext
    from ui_lib.locator_resolver import build_locator_strategies
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser, page = _load_page(pw)
        try:
            ctx = UIContext()
            step = {
                "action": "click",
                "l1_test_id": "btn-save",
                "l1_label": "用户名",
                "l1_aria_label": "角色",
            }
            names = [n for n, _ in build_locator_strategies(page, step, ctx)]
            assert names[0] in ("L1_testid", "CACHE:L1_testid") or "L1_testid" in names
            assert "L1_testid" in names
            assert "L1_label" in names
            assert "L1_aria_label" in names
        finally:
            browser.close()


def test_ui_lib_click_healing():
    sys.path.insert(0, str(_ROOT / "codegen"))
    from ui_lib.context import UIContext
    from ui_lib.locator_resolver import click_with_healing
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser, page = _load_page(pw)
        try:
            ctx = UIContext()
            step = {"action": "click", "l1_aria_label": "角色"}
            strategy = click_with_healing(page, step, ctx, timeout_ms=5000)
            assert strategy.startswith("L1")
        finally:
            browser.close()


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
