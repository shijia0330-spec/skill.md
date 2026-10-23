"""P2-4/5 与 P1-11：断言核心、batch 池隔离、registry_key。"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests

_CODEGEN = Path(__file__).resolve().parent
if str(_CODEGEN) not in sys.path:
    sys.path.insert(0, str(_CODEGEN))

from api_lib.assertions import run_assertions
from api_lib.batch import run_batch
from api_lib.variable_pool import VariablePool
from run_spec import parse_frontmatter, render_ui_pytest
from ui_lib.selector_registry import merge_registry_step


def _resp(status: int = 200, body: dict | None = None) -> requests.Response:
    r = requests.Response()
    r.status_code = status
    r._content = json.dumps(body or {"data": []}).encode()
    r.headers["Content-Type"] = "application/json"
    return r


def test_assertions_and_or_not():
    resp = _resp(body={"data": {"ok": True, "code": 0}})
    pool: dict = {}
    run_assertions(
        resp,
        [
            {
                "type": "and",
                "items": [
                    {"type": "json_path", "path": "data.ok", "expected": True},
                    {"type": "json_path", "path": "data.code", "expected": 0},
                ],
            }
        ],
        pool,
        0.05,
    )
    run_assertions(
        resp,
        [
            {
                "type": "or",
                "items": [
                    {"type": "json_path", "path": "data.code", "expected": 99},
                    {"type": "json_path", "path": "data.code", "expected": 0},
                ],
            }
        ],
        pool,
        0.05,
    )
    with pytest.raises(AssertionError):
        run_assertions(
            resp,
            [{"type": "not", "item": {"type": "json_path", "path": "data.ok", "expected": True}}],
            pool,
            0.05,
        )
    run_assertions(
        resp,
        [{"type": "not", "item": {"type": "json_path", "path": "data.code", "expected": 99}}],
        pool,
        0.05,
    )


def test_assertions_array_header_regex():
    resp = _resp(body={"items": [{"id": 1}, {"id": 2}]})
    resp.headers["X-Request-Id"] = "req-abc"
    pool: dict = {}
    run_assertions(resp, [{"type": "array_length", "path": "items", "expected": 2}], pool, 0.05)
    run_assertions(resp, [{"type": "array_contains", "path": "items", "item": {"id": 1}}], pool, 0.05)
    run_assertions(
        resp,
        [{"type": "header", "name": "X-Request-Id", "expected": "req-abc"}],
        pool,
        0.05,
    )
    run_assertions(resp, [{"type": "regex", "pattern": r'"id"\s*:\s*1'}], pool, 0.05)


def test_assertions_fuzzy_subset_and_type():
    resp = _resp(body={"data": {"name": "alice", "age": 30, "tags": ["a", "b"]}})
    pool: dict = {}
    run_assertions(resp, [{"type": "fuzzy_subset", "expected": {"data": {"name": "alice"}}}], pool, 0.05)
    run_assertions(resp, [{"type": "type_check", "path": "data.age", "expected_type": "int"}], pool, 0.05)


def test_batch_isolates_variable_pool_when_concurrent(monkeypatch):
    """concurrency>1 时各 case 使用独立 VariablePool 副本。"""
    pool_states: list[dict] = []
    shared = VariablePool({"seed": "root"})

    def fake_run_case(_session, active_pool, case, _base_url, **kwargs):
        active_pool.set("case_id", case.get("id"))
        pool_states.append(dict(active_pool.as_dict()))

    monkeypatch.setattr("api_lib.batch.run_case", fake_run_case)

    cases = [{"id": "A"}, {"id": "B"}, {"id": "C"}]
    run_batch(
        MagicMock(),
        shared,
        "http://localhost",
        cases,
        [],
        {"concurrency": 3, "fail_fast": False},
    )
    assert len(pool_states) == 3
    assert shared.get("case_id") is None
    assert {s["case_id"] for s in pool_states} == {"A", "B", "C"}


def test_merge_registry_step(tmp_path: Path, monkeypatch):
    reg = {
        "version": 1,
        "selectors": {
            "login.submit": {
                "locator": {"l1_role": "button", "l1_name": "登录"},
            }
        },
    }
    reg_file = tmp_path / "selector_registry.json"
    reg_file.write_text(json.dumps(reg), encoding="utf-8")
    monkeypatch.setenv("SELECTOR_REGISTRY_PATH", str(reg_file))

    merged = merge_registry_step({"action": "click", "registry_key": "login.submit"})
    assert merged["l1_role"] == "button"
    assert merged["l1_name"] == "登录"

    explicit = merge_registry_step(
        {
            "action": "click",
            "registry_key": "login.submit",
            "l1_name": "Sign in",
        }
    )
    assert explicit["l1_name"] == "Sign in"


def test_ui_codegen_sets_selector_registry_env():
    spec = """---
kind: ui_test
base_url: http://your-server:5173
selector_registry: output/selector_registry.json
steps:
  - action: click
    registry_key: login.submit
---
"""
    meta, body = parse_frontmatter(spec)
    out = render_ui_pytest(meta, body)
    assert "SELECTOR_REGISTRY_PATH" in out
    assert "_registry_locator" not in out
    assert "run_ui_flow" in out
