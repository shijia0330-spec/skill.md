"""nl_to_ui_spec 单元测试。"""
from __future__ import annotations

import sys
from pathlib import Path

_CODEGEN = Path(__file__).resolve().parent
if str(_CODEGEN) not in sys.path:
    sys.path.insert(0, str(_CODEGEN))

from nl_to_ui_spec import build_markdown, build_spec_meta, nl_text_to_spec, slug_from_text


def test_slug_from_text():
    assert slug_from_text("打开登录页，点击登录").startswith("nl_") or "打开" in slug_from_text("打开登录页")


def test_nl_text_to_spec_markdown():
    md, meta = nl_text_to_spec(
        "打开登录页，用户名：admin，密码：admin123，点击登录",
        base_url="http://your-server:5173",
        parser="regex",
    )
    assert "kind: ui_pytest_playwright" in md
    assert "ui_pytest_playwright" in md or "flows:" in md
    assert meta["base_url"] == "http://your-server:5173"
    assert meta.get("flows") or meta.get("steps")
    assert "healing:" in md


def test_build_markdown_roundtrip():
    meta = build_spec_meta(
        [{"action": "goto", "path": "/login"}],
        [],
        base_url="http://your-server:5173",
        flow_name="login",
    )
    md = build_markdown(meta, title="测试", nl_text="打开登录页")
    assert md.startswith("---")
    assert "login" in md
