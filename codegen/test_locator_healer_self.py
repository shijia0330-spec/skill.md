"""mobile_lib 单元测试（无需真机）。"""
from __future__ import annotations

import sys
from pathlib import Path

_CODEGEN = Path(__file__).resolve().parent
if str(_CODEGEN) not in sys.path:
    sys.path.insert(0, str(_CODEGEN))

from mobile_lib.locator_healer import (  # noqa: E402
    _build_l1_attempts,
    _build_l2_attempts,
    hints_from_primary,
    suggest_from_page_source,
)
from mobile_lib.selector_registry import (  # noqa: E402
    merge_registry_step,
    record_healed_locator,
    resolve_l0_attempt,
)

_SAMPLE_ANDROID = """<?xml version="1.0" encoding="UTF-8"?>
<hierarchy>
  <android.widget.Button text="登录" content-desc="登录按钮" resource-id="com.app:id/login" clickable="true"/>
  <android.widget.EditText text="" resource-id="com.app:id/username" clickable="true"/>
</hierarchy>
"""

_SAMPLE_IOS = """<?xml version="1.0" encoding="UTF-8"?>
<AppiumAUT>
  <XCUIElementTypeButton label="登录" name="loginBtn" visible="true"/>
  <XCUIElementTypeTextField label="用户名" name="username" value="" visible="true"/>
</AppiumAUT>
"""


def test_hints_from_css_name():
    h = hints_from_primary("css", 'input[name="username"]')
    assert h.css == 'input[name="username"]'
    assert h.text == "username"


def test_suggest_from_page_source_login_android():
    cands = suggest_from_page_source(_SAMPLE_ANDROID, text_hint="登录")
    bys = {c[0] for c in cands}
    assert "accessibility_id" in bys or "android_uiautomator" in bys


def test_suggest_from_page_source_ios():
    cands = suggest_from_page_source(_SAMPLE_IOS, text_hint="登录")
    bys = {c[0] for c in cands}
    assert "ios_predicate" in bys or "accessibility_id" in bys


def test_suggest_respects_text_hint():
    cands = suggest_from_page_source(_SAMPLE_ANDROID, text_hint="username")
    assert any("username" in loc for _, loc in cands)


def test_hints_from_accessibility_id():
    h = hints_from_primary("accessibility_id", "提交")
    assert h.accessibility_id == "提交"
    assert h.content_desc == "提交"
    assert h.label == "提交"


def test_l1_includes_ios_predicate_for_text():
    h = hints_from_primary("accessibility_id", "登录")
    attempts = _build_l1_attempts("accessibility_id", "登录", h)
    bys = {a[1] for a in attempts}
    assert "ios_predicate" in bys
    assert "ios_class_chain" in bys


def test_l2_includes_ios_predicate():
    h = hints_from_primary("css", 'input[name="username"]')
    attempts = _build_l2_attempts(h, 'input[name="username"]')
    assert any(a[1] == "ios_predicate" for a in attempts)


def test_hints_from_ios_predicate():
    h = hints_from_primary("ios_predicate", 'label == "登录"')
    assert h.ios_predicate == 'label == "登录"'
    assert h.label == "登录"


def test_selector_registry_roundtrip(tmp_path: Path):
    reg = tmp_path / "mobile_selector_registry.json"
    record_healed_locator(
        "login.submit",
        by="accessibility_id",
        locator="登录按钮",
        strategy="uia_text",
        level="L1",
        primary_by="css",
        primary_locator='button[type="submit"]',
        registry_path_arg=reg,
    )
    l0 = resolve_l0_attempt("login.submit", reg)
    assert l0 == ("accessibility_id", "登录按钮")


def test_merge_registry_step(tmp_path: Path):
    reg = tmp_path / "reg.json"
    record_healed_locator(
        "login.username",
        by="id",
        locator="com.app:id/username",
        strategy="resource_id",
        level="L1",
        primary_by="accessibility_id",
        primary_locator="username_input",
        registry_path_arg=reg,
    )
    step = merge_registry_step({"action": "click", "registry_key": "login.username"}, reg)
    assert step["by"] == "id"
    assert step["value"] == "com.app:id/username"
