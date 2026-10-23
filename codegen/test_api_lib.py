"""api_lib 单元测试（不依赖外部服务）。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import requests

_CODEGEN = Path(__file__).resolve().parent
if str(_CODEGEN) not in sys.path:
    sys.path.insert(0, str(_CODEGEN))

from api_lib.assertions import run_assertions
from api_lib.batch import merge_case_with_data_row, topological_sort
from api_lib.resolver import fill_body, resolve_string
from api_lib.setup_hook import parse_api_setup, run_api_setup
from api_lib.token_utils import extract_token
from api_lib.variable_pool import VariablePool


def test_resolve_string_variants():
    pool = {"token": "abc", "user_id": 42}
    assert resolve_string("${token}", pool) == "abc"
    assert resolve_string("{{token}}", pool) == "abc"
    assert resolve_string("/users/{user_id}", pool) == "/users/42"
    prev = {"data": {"token": "xyz"}}
    assert resolve_string("${prev.response.data.token}", pool, prev_response=prev) == "xyz"


def test_parse_api_setup_defaults():
    assert parse_api_setup({}) == {"kind": "test_init", "path": "/api/test/init"}
    assert parse_api_setup({"setup": "none"}) == {"kind": "none"}
    assert parse_api_setup({"setup": "test_init"})["kind"] == "test_init"
    cfg = parse_api_setup(
        {
            "setup": {
                "kind": "test_init",
                "path": "/api/custom/init",
                "json_body": {"seed": True},
            }
        }
    )
    assert cfg["path"] == "/api/custom/init"
    assert cfg["json_body"] == {"seed": True}
    df = parse_api_setup({"setup": {"kind": "data_factory", "script": "output/data_factory.py"}})
    assert df["kind"] == "data_factory"


def test_run_api_setup_skips_on_env(monkeypatch):
    monkeypatch.setenv("TEST_SETUP", "none")
    called = {"n": 0}

    def fake_post(*_a, **_k):
        called["n"] += 1
        return requests.Response()

    monkeypatch.setattr(requests, "post", fake_post)
    run_api_setup("http://your-server:5173", {"kind": "test_init"})
    assert called["n"] == 0


def test_run_api_setup_test_init(monkeypatch):
    monkeypatch.delenv("TEST_SETUP", raising=False)
    seen: dict = {}

    def fake_post(url, **kwargs):
        seen["url"] = url
        seen["kwargs"] = kwargs
        r = requests.Response()
        r.status_code = 200
        return r

    monkeypatch.setattr(requests, "post", fake_post)
    run_api_setup("http://your-server:5173/", {"kind": "test_init", "path": "/api/test/init"})
    assert seen["url"] == "http://your-server:5173/api/test/init"


def test_merge_case_with_data_row():
    case = {
        "id": "TC-LOGIN",
        "method": "POST",
        "json_body": {"username": "", "password": ""},
        "expect_status": 200,
    }
    row = {
        "username": "admin",
        "password": "admin123",
        "expected_status": 401,
        "case_id": "wrong",
    }
    merged = merge_case_with_data_row(case, row)
    assert merged["json_body"] == {"username": "admin", "password": "admin123"}
    assert merged["expect_status"] == 401
    assert "case_id" not in merged["json_body"]


def test_merge_case_with_data_row_resolves_path_placeholders():
    case = {
        "id": "TC-USER",
        "method": "GET",
        "path": "/api/users/${id}",
        "expect_status": 200,
    }
    merged = merge_case_with_data_row(case, {"id": "42", "username": "u1"})
    assert merged["path"] == "/api/users/42"


def test_topological_sort():
    order = topological_sort(
        ["C", "B", "A"],
        {"B": ["A"], "C": ["B"]},
    )
    assert order == ["A", "B", "C"]


def test_assertions_status_and_json_path():
    resp = requests.Response()
    resp.status_code = 200
    resp._content = json.dumps({"data": {"id": 1}}).encode()
    pool: dict = {}
    run_assertions(resp, [{"type": "status_code", "expected": 200}], pool, 0.1)
    run_assertions(resp, [{"type": "json_path", "path": "data.id", "expected": 1}], pool, 0.1)


def test_fill_body_nested():
    pool = {"name": "bob"}
    out = fill_body({"user": "${name}", "tags": ["{name}"]}, pool)
    assert out == {"user": "bob", "tags": ["bob"]}


def test_variable_pool_auto_extract():
    pool = VariablePool()
    pool.extract_auto({"data": {"token": "t1", "id": 9, "session_id": "s1"}})
    assert pool.get("token") == "t1"
    assert pool.get("id") == 9
    assert pool.get("session_id") == "s1"


def test_extract_token_access_token():
    data = {"access_token": "tok_iam", "token": "other"}
    assert extract_token(data) == "tok_iam"
    assert extract_token({"data": {"access_token": "nested"}}, ["data.access_token"]) == "nested"


def test_healing_session_401_refreshes_token(monkeypatch, tmp_path: Path):
    """401 时调用 _login_fn 重登并重试，成功后返回 200。"""
    from api_lib.heal_kb import HealKB
    from api_lib.http_client import HealingSession

    pool = VariablePool()
    kb = HealKB(cache_dir=tmp_path)
    session = HealingSession(
        base_url="http://your-server:5173",
        var_pool=pool,
        heal_kb=kb,
        max_retries=3,
    )

    login_calls = {"n": 0}

    def fake_login() -> str:
        login_calls["n"] += 1
        session.headers["Authorization"] = "Bearer refreshed-token"
        pool.set("token", "refreshed-token")
        return "refreshed-token"

    session._login_fn = fake_login

    http_calls = {"n": 0}

    def fake_super_request(self, method, url, **kwargs):
        http_calls["n"] += 1
        resp = requests.Response()
        resp.status_code = 401 if http_calls["n"] == 1 else 200
        resp._content = b'{"ok": true}'
        return resp

    monkeypatch.setattr(requests.Session, "request", fake_super_request)

    resp = session.request("GET", "http://your-server:5173/api/products")

    assert resp.status_code == 200
    assert http_calls["n"] == 2
    assert login_calls["n"] == 1
    assert session.headers["Authorization"] == "Bearer refreshed-token"
    assert pool.get("token") == "refreshed-token"
    assert any(p.get("type") == "token_refresh" for p in kb.get_patterns("token_refresh"))


def test_healing_session_401_without_login_fn_no_retry(monkeypatch):
    """未配置 _login_fn 时，401 直接返回，不重试。"""
    from api_lib.http_client import HealingSession

    session = HealingSession(base_url="http://your-server:5173", max_retries=3)
    session._login_fn = None

    http_calls = {"n": 0}

    def fake_super_request(self, method, url, **kwargs):
        http_calls["n"] += 1
        resp = requests.Response()
        resp.status_code = 401
        resp._content = b""
        return resp

    monkeypatch.setattr(requests.Session, "request", fake_super_request)

    resp = session.request("GET", "http://your-server:5173/api/products")

    assert resp.status_code == 401
    assert http_calls["n"] == 1


def test_healing_session_401_exhausts_max_retries(monkeypatch, tmp_path: Path):
    """401 持续失败时，最多重登 max_retries 次后返回最后一次 401。"""
    from api_lib.heal_kb import HealKB
    from api_lib.http_client import HealingSession

    kb = HealKB(cache_dir=tmp_path)
    session = HealingSession(
        base_url="http://your-server:5173",
        heal_kb=kb,
        max_retries=2,
    )
    login_calls = {"n": 0}
    session._login_fn = lambda: login_calls.__setitem__("n", login_calls["n"] + 1) or "tok"

    http_calls = {"n": 0}

    def fake_super_request(self, method, url, **kwargs):
        http_calls["n"] += 1
        resp = requests.Response()
        resp.status_code = 401
        resp._content = b""
        return resp

    monkeypatch.setattr(requests.Session, "request", fake_super_request)

    resp = session.request("GET", "http://your-server:5173/api/secure")

    assert resp.status_code == 401
    # attempts 0,1 触发 refresh；attempt 2 不再 refresh → 共 3 次 HTTP
    assert http_calls["n"] == 3
    assert login_calls["n"] == 2
    assert len(kb.get_patterns("token_refresh")) == 2


def test_openapi_build_assertions():
    sys.path.insert(0, str(_CODEGEN))
    from openapi_import import _attach_assertions, _build_assertions_for_case

    data = {"components": {"schemas": {}}}
    responses = {
        "200": {
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "code": {"type": "integer"},
                            "success": {"type": "boolean"},
                        },
                    }
                }
            }
        }
    }
    assertions = _build_assertions_for_case(data, responses, 200, include_json_subset=True)
    assert assertions[0]["type"] == "status_code"
    assert any(a["type"] == "fuzzy_subset" for a in assertions)

    case: dict = {"method": "GET", "path": "/x", "expect_status": 200}
    _attach_assertions(case, data, responses, 200)
    assert "assertions" in case
    assert case["assertions"][0]["expected"] == 200
