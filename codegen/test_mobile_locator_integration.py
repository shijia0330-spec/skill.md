"""mobile 定位自愈集成自测 — mock driver，无需 Appium 真机。"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_CODEGEN = Path(__file__).resolve().parent
_ROOT = _CODEGEN.parent
if str(_CODEGEN) not in sys.path:
    sys.path.insert(0, str(_CODEGEN))

from mobile_lib.locator_healer import (  # noqa: E402
    MobileLocatorHints,
    click_with_heal,
    find_with_heal,
)
from mobile_lib.selector_registry import record_healed_locator, resolve_l0_attempt  # noqa: E402

try:
    from appium.webdriver.common.appiumby import AppiumBy
    from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException
except ImportError:
    pytest.skip("需要 Appium-Python-Client + selenium", allow_module_level=True)


class FakeElement:
    def __init__(self, *, stale_on_click: bool = False) -> None:
        self._stale_on_click = stale_on_click
        self.clicked = False
        self.keys: list[str] = []

    def is_displayed(self) -> bool:
        return True

    def is_enabled(self) -> bool:
        return True

    def click(self) -> None:
        if self._stale_on_click and not self.clicked:
            self.clicked = True
            raise StaleElementReferenceException("stale")
        self.clicked = True

    def clear(self) -> None:
        pass

    def send_keys(self, text: str) -> None:
        self.keys.append(text)


class FakeSwitchTo:
    def __init__(self, driver: "FakeDriver") -> None:
        self._driver = driver

    def context(self, name: str) -> None:
        self._driver.current_context = name


class FakeDriver:
    """按 (context, AppiumBy, locator) 配置命中表。"""

    def __init__(
        self,
        *,
        contexts: list[str] | None = None,
        hits: dict[tuple[str, object, str], FakeElement | bool] | None = None,
        page_source: str = "",
    ) -> None:
        self.contexts = contexts or ["NATIVE_APP"]
        self.current_context = self.contexts[0]
        self.switch_to = FakeSwitchTo(self)
        self._hits: dict[tuple[str, object, str], FakeElement | bool] = hits or {}
        self.page_source = page_source
        self.find_calls: list[tuple[str, object, str]] = []

    def find_element(self, by: object, value: str) -> FakeElement:
        self.find_calls.append((self.current_context, by, value))
        key = (self.current_context, by, value)
        if key in self._hits:
            hit = self._hits[key]
            if isinstance(hit, FakeElement):
                return hit
            return FakeElement()
        raise NoSuchElementException(f"not found: {key}")


_ANDROID_HOME_XML = """<?xml version="1.0" encoding="UTF-8"?>
<hierarchy>
  <android.widget.TextView text="欢迎" content-desc="home_title" resource-id="com.app:id/home"/>
</hierarchy>
"""


def test_l0_registry_cache_hit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    reg = tmp_path / "reg.json"
    record_healed_locator(
        "login.submit",
        by="accessibility_id",
        locator="登录按钮",
        strategy="uia_text",
        level="L1",
        primary_by="accessibility_id",
        primary_locator="login_button",
        registry_path_arg=reg,
    )
    monkeypatch.setenv("MOBILE_SELECTOR_REGISTRY_PATH", str(reg))
    monkeypatch.setenv("MOBILE_SELF_HEAL", "1")

    driver = FakeDriver(
        hits={
            ("NATIVE_APP", AppiumBy.ACCESSIBILITY_ID, "登录按钮"): FakeElement(),
        }
    )
    el = find_with_heal(
        driver,
        "accessibility_id",
        "login_button",
        registry_key="login.submit",
        timeout_sec=1,
    )
    assert el is not None
    assert driver.find_calls[0][2] == "登录按钮"


def test_l1_heal_when_primary_missing(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MOBILE_SELF_HEAL", "1")
    monkeypatch.setenv("MOBILE_HEAL_TIMEOUT_MS", "200")
    driver = FakeDriver(
        hits={
            (
                "NATIVE_APP",
                AppiumBy.ANDROID_UIAUTOMATOR,
                'new UiSelector().textContains("登录")',
            ): FakeElement(),
        }
    )
    el = find_with_heal(
        driver,
        "accessibility_id",
        "old_login_btn",
        hints=MobileLocatorHints(text="登录"),
        timeout_sec=0.5,
    )
    assert el is not None
    assert any("登录" in str(c[2]) for c in driver.find_calls)


def test_webview_context_switch_for_css(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MOBILE_SELF_HEAL", "0")
    monkeypatch.setenv("MOBILE_HEAL_TIMEOUT_MS", "300")
    driver = FakeDriver(
        contexts=["NATIVE_APP", "WEBVIEW_com.chrome"],
        hits={
            ("WEBVIEW_com.chrome", AppiumBy.CSS_SELECTOR, 'input[name="username"]'): FakeElement(),
        },
    )
    el = find_with_heal(driver, "css", 'input[name="username"]', timeout_sec=1)
    assert el is not None
    contexts_used = {c[0] for c in driver.find_calls}
    assert "WEBVIEW_com.chrome" in contexts_used


def test_ios_predicate_in_l1_chain(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MOBILE_SELF_HEAL", "0")
    monkeypatch.setenv("MOBILE_HEAL_TIMEOUT_MS", "300")
    pred = 'label == "登录"'
    driver = FakeDriver(
        hits={
            ("NATIVE_APP", AppiumBy.IOS_PREDICATE, pred): FakeElement(),
        }
    )
    el = find_with_heal(driver, "ios_predicate", pred, timeout_sec=1, wait_mode="clickable")
    assert el is not None


def test_l3_page_source_suggest(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MOBILE_SELF_HEAL", "1")
    monkeypatch.setenv("MOBILE_HEAL_TIMEOUT_MS", "200")
    driver = FakeDriver(
        page_source=_ANDROID_HOME_XML,
        hits={
            ("NATIVE_APP", AppiumBy.ACCESSIBILITY_ID, "home_title"): FakeElement(),
        },
    )
    el = find_with_heal(
        driver,
        "accessibility_id",
        "missing_home",
        hints=MobileLocatorHints(text="欢迎"),
        timeout_sec=0.5,
    )
    assert el is not None


def test_registry_write_after_heal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    reg = tmp_path / "reg.json"
    monkeypatch.setenv("MOBILE_SELECTOR_REGISTRY_PATH", str(reg))
    monkeypatch.setenv("MOBILE_REGISTRY_WRITE", "1")
    monkeypatch.setenv("MOBILE_SELF_HEAL", "1")
    monkeypatch.setenv("MOBILE_HEAL_TIMEOUT_MS", "200")

    driver = FakeDriver(
        hits={
            ("NATIVE_APP", AppiumBy.ACCESSIBILITY_ID, "登录按钮"): FakeElement(),
        }
    )
    find_with_heal(
        driver,
        "accessibility_id",
        "bad_login",
        hints=MobileLocatorHints(text="登录", accessibility_id="登录按钮"),
        registry_key="login.submit",
        timeout_sec=0.5,
    )
    l0 = resolve_l0_attempt("login.submit", reg)
    assert l0 == ("accessibility_id", "登录按钮")


def test_click_with_stale_retry(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MOBILE_SELF_HEAL", "0")
    monkeypatch.setenv("MOBILE_HEAL_TIMEOUT_MS", "300")
    stale_el = FakeElement(stale_on_click=True)
    driver = FakeDriver(
        hits={
            ("NATIVE_APP", AppiumBy.ACCESSIBILITY_ID, "login_button"): stale_el,
        }
    )
    with patch.object(FakeDriver, "find_element", wraps=driver.find_element) as mocked:
        click_with_heal(driver, "accessibility_id", "login_button", timeout_sec=1)
        assert mocked.call_count >= 2


def test_codegen_appium_e2e_has_registry(tmp_path: Path):
    from run_spec import render_appium_pytest

    spec = (_ROOT / "templates/appium_e2e.md").read_text(encoding="utf-8")
    import re

    m = re.match(r"^---\n(.*?)\n---", spec, re.DOTALL)
    assert m
    import yaml

    meta = yaml.safe_load(m.group(1)) or {}
    body = spec[m.end() :]
    out = render_appium_pytest(meta, body)
    assert "MOBILE_SELECTOR_REGISTRY_PATH" in out
    assert 'registry_key="login.username"' in out or "registry_key='login.username'" in out
    assert "def _click(" in out
    assert "def _fill(" in out
    assert "wait_mode=" in out or "click_with_heal" in out


def test_generate_templates(tmp_path: Path):
    """走 generate.sh 链路，确认三份模板可生成且含 registry_key。"""
    import subprocess

    for tpl in ("appium_e2e.md", "appium_seckill_h5.md", "appium_ios_smoke.md"):
        out = subprocess.run(
            ["bash", str(_ROOT / "generate.sh"), f"templates/{tpl}", str(tmp_path / "out")],
            cwd=str(_ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert out.returncode == 0, out.stderr or out.stdout
        py_name = tpl.replace(".md", ".py")
        generated = (tmp_path / "out" / py_name).read_text(encoding="utf-8")
        assert "MOBILE_SELECTOR_REGISTRY_PATH" in generated
        assert "registry_key=" in generated
        assert "def _click(" in generated
