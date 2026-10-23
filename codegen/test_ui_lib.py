"""ui_lib 单元测试（不依赖浏览器）。"""
from __future__ import annotations

import sys
from pathlib import Path

_CODEGEN = Path(__file__).resolve().parent
if str(_CODEGEN) not in sys.path:
    sys.path.insert(0, str(_CODEGEN))

from ui_lib.context import UIContext
from ui_lib.heal_kb import UIHealKB
from ui_lib.locator_resolver import build_locator_strategies, resolve_string
from ui_lib.nl_parser import parse_nl_to_flow


class _FakePage:
    pass


def test_ui_context_and_resolve_string():
    ctx = UIContext({"user": "admin"})
    assert resolve_string("{user}", ctx) == "admin"
    assert resolve_string("__ENV__:PATH", ctx) is not None


def test_heal_kb_record_and_lookup():
    kb = UIHealKB(cache_dir=_CODEGEN / "output" / "_test_ui_heal_kb")
    step = {"action": "click", "l1_role": "button", "l1_name": "登录"}
    patched = {"action": "click", "l1_test_id": "login-btn"}
    kb.record_fix(step, patched, {"strategy": "semantic_0"})
    alt = kb.get_alternate_step(step)
    assert alt == patched


def test_heal_kb_legacy_cache_does_not_cross_scope():
    kb = UIHealKB(cache_dir=_CODEGEN / "output" / "_test_ui_heal_kb_legacy")
    kb._index = {
        "fixes": [
            {
                "step_key": "fill|服务器名称",
                "patched_step": {
                    "action": "fill",
                    "l1_label": "商品名称",
                    "scope": "dialog",
                    "dialog_title": "新增商品",
                },
            }
        ]
    }
    page_fill = {"action": "fill", "l1_label": "商品名称"}
    assert kb.get_alternate_step(page_fill) is None


def test_heal_kb_scope_isolated_lookup():
    kb = UIHealKB(cache_dir=_CODEGEN / "output" / "_test_ui_heal_kb_scope")
    dialog_fill = {
        "action": "fill",
        "l1_label": "商品名称",
        "scope": "dialog",
        "dialog_title": "新增商品",
    }
    page_fill = {"action": "fill", "l1_label": "商品名称"}
    kb.record_fix(dialog_fill, dialog_fill, {"strategy": "L1_label"})
    assert kb.get_alternate_step(page_fill) is None
    assert kb.get_alternate_step(dialog_fill) == dialog_fill


def test_nl_parser_login_flow():
    steps, _expects = parse_nl_to_flow(
        "打开 秒杀登录页，用户名 admin，密码 123456，点击登录",
        "http://your-server:5173",
        parser="regex",
    )
    actions = [s.get("action") for s in steps]
    assert "goto" in actions
    assert "fill" in actions
    assert "click" in actions


def test_validate_script_ui_login():
    from ui_lib.env_check import validate_script

    p = _CODEGEN.parent / "output" / "ui_login.py"
    if p.is_file():
        r = validate_script(p)
        assert r["ok"] is True


def test_expect_locator_role_and_scope():
    from ui_lib.runner import _expect_locator, _expect_scope

    class _Loc:
        def __init__(self, name: str):
            self.name = name

        def get_by_role(self, role, name=None):
            return _Loc(f"{self.name}>{role}:{name}")

        def get_by_text(self, text, exact=False):
            return _Loc(f"{self.name}>text:{text}")

        def filter(self, has=None):
            return _Loc(f"{self.name}>filtered")

        @property
        def first(self):
            return _Loc(f"{self.name}.first")

        def get_by_placeholder(self, ph):
            return _Loc(f"{self.name}>ph:{ph}")

    class _Page(_Loc):
        def __init__(self):
            super().__init__("page")

        def locator(self, sel):
            return _Loc(f"page>{sel}")

    page = _Page()
    ctx = UIContext()
    ex = {
        "type": "role_visible",
        "l1_role": "button",
        "l1_name": "搜索",
    }
    loc = _expect_locator(page, ex, ctx)
    assert "button" in loc.name and "搜索" in loc.name

    dlg_ex = {
        "type": "hidden",
        "scope": "dialog",
        "dialog_title": "新增商品",
    }
    scoped = _expect_scope(page, dlg_ex, ctx)
    assert "filtered" in scoped.name


def test_build_locator_strategies_empty_step():
    page = _FakePage()
    ctx = UIContext()
    import ui_lib.locator_resolver as lr

    orig_l1 = lr._loc_l1
    lr._loc_l1 = lambda r, s, c: None
    try:
        strategies = build_locator_strategies(page, {"action": "click"}, ctx)
        assert strategies == []
    finally:
        lr._loc_l1 = orig_l1


def test_is_login_url():
    from ui_lib.auth import is_login_url

    assert is_login_url("http://x/login")
    assert is_login_url("http://x/register")
    assert is_login_url("http://x/auth/login?next=/")
    assert not is_login_url("http://x/products")


def test_resolve_scope_dialog():
    from ui_lib.scopes import resolve_scope

    class _Loc:
        def __init__(self, name: str):
            self.name = name

        def get_by_role(self, role, name=None):
            return _Loc(f"{self.name}>{role}")

        def get_by_text(self, text, exact=False):
            return _Loc(f"{self.name}>text:{text}")

        def filter(self, has=None):
            return _Loc(f"{self.name}>filtered")

        @property
        def first(self):
            return _Loc(f"{self.name}.first")

    page = _Loc("page")
    ctx = UIContext()
    root = resolve_scope(page, {"scope": "dialog", "dialog_title": "新增邮箱账号"}, ctx)
    assert "filtered" in root.name
