"""OpenAPI E 层边界用例生成单元测试。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_CODEGEN = Path(__file__).resolve().parent
_ROOT = _CODEGEN.parent
if str(_CODEGEN) not in sys.path:
    sys.path.insert(0, str(_CODEGEN))

from openapi_import import (  # noqa: E402
    _boundary_variants_for_field,
    build_openapi_artifacts,
)
from run_spec import load_openapi  # noqa: E402


def test_boundary_variants_string_max_length_trio():
    prop = {"type": "string", "maxLength": 5}
    variants = _boundary_variants_for_field("name", prop)
    lengths = [(v, ok) for v, ok, *_ in variants]
    assert ("aaaa", True) in lengths
    assert ("aaaaa", True) in lengths
    assert ("aaaaaa", False) in lengths


def test_boundary_variants_integer_range():
    prop = {"type": "integer", "minimum": 1, "maximum": 300}
    variants = _boundary_variants_for_field("timeout", prop)
    by_val = {v: ok for v, ok, *_ in variants}
    assert by_val[0] is False
    assert by_val[1] is True
    assert by_val[300] is True
    assert by_val[301] is False


def test_boundary_variants_enum_invalid():
    prop = {"type": "string", "enum": ["SSE", "HTTP"]}
    variants = _boundary_variants_for_field("transportType", prop)
    invalid = [v for v, ok, *_ in variants if not ok]
    assert invalid and invalid[0] not in ("SSE", "HTTP")


def test_build_openapi_artifacts_includes_e_layer_cases():
    spec_path = _ROOT / "examples" / "mini_openapi_boundaries.json"
    data = load_openapi(str(spec_path))
    art = build_openapi_artifacts(data, base_url="http://your-server:5173", mode="full")
    draft = art["cases_draft"]
    layers = [c.get("layer") for c in draft.get("cases") or []]
    assert "H" in layers
    assert "E" in layers

    e_cases = [c for c in draft["cases"] if c.get("layer") == "E"]
    assert len(e_cases) >= 8

    names = " ".join(c.get("name", "") for c in e_cases)
    assert "maxLength" in names or "长度" in names
    assert "minimum" in names or "timeout" in names.lower() or "300" in names

    fail_cases = [
        c
        for c in e_cases
        if c.get("automation", {}).get("expect_status") in (422, [422, 400])
        or c.get("automation", {}).get("expect_status") == [422, 400]
    ]
    assert fail_cases
    for fc in fail_cases:
        assert fc.get("automation", {}).get("review_required") is True


def test_x_layer_validation_cases_have_review_required_and_multi_status():
    spec_path = _ROOT / "examples" / "mini_openapi_boundaries.json"
    data = load_openapi(str(spec_path))
    art = build_openapi_artifacts(data, mode="full")
    x_val = [
        c
        for c in art["cases_draft"]["cases"]
        if c.get("layer") == "X"
        and "/auth/register" in c.get("automation", {}).get("path", "")
        and "invalid-body" in c.get("automation", {}).get("id", "")
    ]
    assert x_val
    auto = x_val[0]["automation"]
    assert auto.get("review_required") is True
    assert auto.get("expect_status") == [422, 400]


def test_smoke_mode_skips_e_layer():
    spec_path = _ROOT / "examples" / "mini_openapi_boundaries.json"
    data = load_openapi(str(spec_path))
    art = build_openapi_artifacts(data, mode="smoke")
    layers = [c.get("layer") for c in art["cases_draft"].get("cases") or []]
    assert "E" not in layers


def test_no_boundaries_flag_via_include_boundaries_false():
    spec_path = _ROOT / "examples" / "mini_openapi_boundaries.json"
    data = load_openapi(str(spec_path))
    art = build_openapi_artifacts(
        data,
        mode="full",
        include_negatives=False,
        include_boundaries=False,
    )
    layers = [c.get("layer") for c in art["cases_draft"].get("cases") or []]
    assert layers == ["H"]


def test_generic_rest_auth_profile_applied_to_openapi_cases():
    spec_path = _ROOT / "examples" / "mini_openapi_boundaries.json"
    if not spec_path.is_file():
        import pytest

        pytest.skip("examples/mini_openapi_boundaries.json 不存在")
    data = load_openapi(str(spec_path))
    from openapi_import import load_auth_profile

    profile_path = _ROOT / "templates" / "auth_profiles" / "generic_rest.yaml"
    if not profile_path.is_file():
        import pytest

        pytest.skip("generic_rest.yaml 不存在")
    profile = load_auth_profile(profile_path)
    art = build_openapi_artifacts(
        data,
        base_url="http://your-server:5001",
        auth_profile=profile,
        mode="full",
    )
    draft = art["cases_draft"]
    assert draft.get("auth", {}).get("type") == "bearer_login"
    h_cases = [c for c in draft["cases"] if c.get("layer") == "H"]
    assert h_cases


def test_register_h_case_uses_unique_username():
    spec_path = _ROOT / "examples" / "mini_openapi_boundaries.json"
    data = load_openapi(str(spec_path))
    art = build_openapi_artifacts(data, mode="full")
    reg_cases = [
        c
        for c in art["cases_draft"]["cases"]
        if c.get("layer") == "H" and "/auth/register" in (c.get("automation", {}).get("path") or "")
    ]
    assert reg_cases
    username = reg_cases[0]["automation"]["json_body"]["username"]
    assert username != "example"
    assert username.startswith("reg_")

    e_success = [
        c
        for c in art["cases_draft"]["cases"]
        if c.get("layer") == "E"
        and c.get("automation", {}).get("expect_status") == 201
        and "username" in json.dumps(c.get("automation", {}).get("json_body") or {})
    ]
    assert e_success
    usernames = {c["automation"]["json_body"]["username"] for c in e_success}
    assert len(usernames) == len(e_success)
