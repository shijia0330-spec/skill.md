"""refs_registry 与 selector_registry 单元测试。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_CODEGEN = Path(__file__).resolve().parent
if str(_CODEGEN) not in sys.path:
    sys.path.insert(0, str(_CODEGEN))

from api_lib.refs_registry import RefsRegistry  # noqa: E402

_SCRIPTS = _CODEGEN.parent / "UI-skills" / "分析" / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from selector_registry import (  # noqa: E402
    element_to_locator_fields,
    load_registry,
    merge_dom_scan,
    register_element,
    resolve,
    save_registry,
)


def test_refs_register_and_cleanup_order():
    deleted: list[str] = []

    class FakeResp:
        def __init__(self, code: int = 204):
            self.status_code = code

    class FakeSession:
        pass

    reg = RefsRegistry()
    reg.register(
        ref_type="user",
        ref_id="u-2",
        delete_step={"method": "DELETE", "path": "/api/users/u-2", "expect_status": 204},
    )
    reg.register(
        ref_type="user",
        ref_id="u-1",
        delete_step={"method": "DELETE", "path": "/api/users/u-1", "expect_status": 204},
    )

    import api_lib.refs_registry as rr

    orig_run_step = rr.run_step

    def fake_run_step(session, pool, step, base_url, **kw):
        deleted.append(step["path"])
        return FakeResp()

    rr.run_step = fake_run_step  # type: ignore[attr-defined]
    try:
        from api_lib.variable_pool import VariablePool

        results = reg.cleanup_all(FakeSession(), VariablePool(), "http://localhost")
    finally:
        rr.run_step = orig_run_step

    assert deleted == ["/api/users/u-1", "/api/users/u-2"]
    assert all(r["ok"] for r in results)
    assert len(reg) == 0


def test_refs_register_from_response():
    reg = RefsRegistry()
    reg.register_from_response(
        {
            "type": "tenant",
            "json_path": "data.id",
            "delete": {"method": "DELETE", "path": "/api/tenants/{tenant_id}"},
        },
        {"data": {"id": "t-99"}},
        source="TC-001",
    )
    assert len(reg) == 1
    assert reg._refs[0]["ref_id"] == "t-99"
    assert "{tenant_id}" in reg._refs[0]["delete_step"]["path"] or "t-99" in reg._refs[0]["delete_step"]["path"]


def test_selector_registry_roundtrip(tmp_path: Path):
    reg_path = tmp_path / "registry.json"
    reg = load_registry(reg_path)
    el = {
        "id": "ctl_001",
        "name": "btn_save",
        "role": "button",
        "text_content": "保存",
        "data_testid": "btn-save",
        "label": "",
        "placeholder": "",
    }
    register_element(reg, "demo.save", el, page="demo", url="http://x")
    save_registry(reg, reg_path)
    loc = resolve("demo.save", reg_path)
    assert loc["l1_test_id"] == "btn-save"
    fields = element_to_locator_fields(el)
    assert fields["l1_role"] == "button"


def test_merge_dom_scan(tmp_path: Path):
    dom = tmp_path / "page.json"
    dom.write_text(
        json.dumps(
            {
                "title": "用户管理",
                "url": "file:///test.html",
                "elements": [
                    {
                        "id": "ctl_001",
                        "name": "username",
                        "role": "textbox",
                        "data_testid": "input-username",
                        "label": "用户名",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    reg_path = tmp_path / "reg.json"
    merge_dom_scan(dom, reg_path, key_prefix="seckill.auth")
    loc = resolve("seckill.auth.username", reg_path)
    assert loc["l1_test_id"] == "input-username"
