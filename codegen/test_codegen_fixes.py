"""P0/P1 修复回归：ref、extract_vars、depends_on、429。"""
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
from api_lib.executor import _apply_extract_vars, run_step
from api_lib.http_client import HealingSession
from api_lib.variable_pool import VariablePool
from run_spec import parse_frontmatter, render_api_pytest, render_data_factory


def test_data_factory_ref_codegen_fixed():
    meta, body = parse_frontmatter(
        ( _CODEGEN.parent / "templates" / "data_factory.md").read_text(encoding="utf-8")
    )
    out = render_data_factory(meta, body)
    assert 'key = strategy[4:-1].strip().strip' in out
    assert 'refs["users.id"]' in out or "refs['users.id']" in out


def test_api_chain_vars_depends_on_codegen():
    meta, body = parse_frontmatter(
        (_CODEGEN.parent / "templates" / "api_chain_vars.md").read_text(encoding="utf-8")
    )
    out = render_api_pytest(meta, body)
    assert "_case_outcomes" in out
    assert "_check_case_depends" in out
    assert "_case_outcomes[" in out


def test_api_case_data_source_parametrize_codegen():
    spec_path = _CODEGEN.parent / "templates" / "api_user_ddt.md"
    meta, body = parse_frontmatter(spec_path.read_text(encoding="utf-8"))
    out = render_api_pytest(meta, body, spec_path=spec_path.resolve())
    assert "@pytest.mark.parametrize" in out
    assert "_CASE_0_ROWS" in out
    assert "_CASE_0_IDS" in out
    assert "_row_case" in out
    assert '"/api/users/' in out
    assert "data_source" not in out.split("_CASE_0_ROWS")[1].split("def test_")[0]


def test_api_review_required_skip_codegen():
    meta = {
        "kind": "api_pytest",
        "base_url": "http://127.0.0.1:5001",
        "cases": [
            {
                "id": "TC-REVIEW-001",
                "method": "POST",
                "path": "/api/auth/register",
                "expect_status": [422, 400],
                "review_required": True,
                "no_auth": True,
                "json_body": {"password": "x"},
            }
        ],
    }
    out = render_api_pytest(meta, "")
    assert "REVIEW_REQUIRED_RUN" in out
    assert "@pytest.mark.skipif" in out
    assert "[422, 400]" in out or "422, 400" in out


def test_assertions_status_accepts_multiple_codes():
    resp = requests.Response()
    resp._content = b'{"error":"bad"}'
    pool: dict = {}
    resp.status_code = 400
    run_assertions(resp, [{"type": "status_code", "expected": [422, 400]}], pool, 0.1)
    resp.status_code = 422
    run_assertions(resp, [{"type": "status_code", "expected": [422, 400]}], pool, 0.1)
    resp.status_code = 500
    with pytest.raises(AssertionError):
        run_assertions(resp, [{"type": "status_code", "expected": [422, 400]}], pool, 0.1)


def test_extract_vars_writes_pool():
    pool = VariablePool()
    resp = requests.Response()
    resp.status_code = 201
    resp._content = json.dumps({"token": "abc123", "data": {"id": 9}}).encode()
    _apply_extract_vars(resp, {"access_token": "token"}, pool)
    assert pool.get("access_token") == "abc123"


def test_healing_session_429_retry(monkeypatch, tmp_path: Path):
    from api_lib.heal_kb import HealKB

    kb = HealKB(cache_dir=tmp_path)
    session = HealingSession(base_url="http://localhost", heal_kb=kb, max_retries=2)
    calls = {"n": 0}

    def fake_super_request(self, method, url, **kwargs):
        calls["n"] += 1
        r = requests.Response()
        r.status_code = 429 if calls["n"] == 1 else 200
        r.headers["Retry-After"] = "0"
        r._content = b"{}"
        return r

    monkeypatch.setattr(requests.Session, "request", fake_super_request)
    resp = session.request("GET", "http://localhost/api/x")
    assert resp.status_code == 200
    assert calls["n"] == 2
