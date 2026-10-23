#!/usr/bin/env python3
"""OpenAPI → api_pytest spec / cases JSON（增强：X 层负例、弱 JSON 断言、可配置 auth）。"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import quote

try:
    import yaml
except ImportError:
    yaml = None  # type: type[None]

NEGATIVE_STATUS_CODES = (400, 401, 403, 422)
LOGIN_PATH_HINTS = ("/login", "/auth/login", "/auth/signin", "/signin", "/token", "/oauth/token")
DEFAULT_AUTH_PROFILE: dict[str, Any] = {
    "type": "bearer_login",
    "login_path": "/api/auth/login",
    "username_field": "username",
    "password_field": "password",
    "username_env": "TEST_USERNAME",
    "password_env": "TEST_PASSWORD",
    "token_json_paths": ["token", "data.token", "data.access_token", "access_token"],
}

AUTH_PROFILE_SPEC_KEYS = frozenset(
    {
        "type",
        "login_path",
        "username_field",
        "password_field",
        "username_env",
        "password_env",
        "token_json_paths",
    }
)


def load_auth_profile(source: str | Path | None) -> dict[str, Any]:
    """从 YAML/JSON 加载 auth 配置；省略则返回 DEFAULT_AUTH_PROFILE 副本。"""
    if not source:
        return dict(DEFAULT_AUTH_PROFILE)
    p = Path(source)
    if not p.is_file():
        raise FileNotFoundError(f"auth profile 不存在: {p}")
    text = p.read_text(encoding="utf-8")
    if p.suffix.lower() in (".yaml", ".yml"):
        if yaml is None:
            raise RuntimeError("解析 YAML auth profile 需要 PyYAML")
        data = yaml.safe_load(text)
    else:
        data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("auth profile 须为对象")
    out = dict(DEFAULT_AUTH_PROFILE)
    out.update(data)
    return out


def infer_auth_profile_from_openapi(data: dict[str, Any]) -> dict[str, Any]:
    """从 OpenAPI securitySchemes + paths 推断 login_path（仍可用外部 profile 覆盖）。"""
    profile = dict(DEFAULT_AUTH_PROFILE)
    paths = data.get("paths") if isinstance(data.get("paths"), dict) else {}
    for path in paths:
        norm = path.rstrip("/").lower()
        for hint in LOGIN_PATH_HINTS:
            if norm.endswith(hint) or hint in norm:
                profile["login_path"] = path if path.startswith("/") else f"/{path}"
                break
        if profile["login_path"] != DEFAULT_AUTH_PROFILE["login_path"]:
            break

    components = data.get("components") if isinstance(data.get("components"), dict) else {}
    schemes = components.get("securitySchemes") if isinstance(components.get("securitySchemes"), dict) else {}
    for name, sch in schemes.items():
        if not isinstance(sch, dict):
            continue
        if sch.get("type") == "oauth2" and isinstance(sch.get("flows"), dict):
            for flow in sch["flows"].values():
                if isinstance(flow, dict) and isinstance(flow.get("tokenUrl"), str):
                    tu = flow["tokenUrl"]
                    profile["login_path"] = tu if tu.startswith("/") else f"/{tu.lstrip('/')}"
        if sch.get("type") == "http" and sch.get("scheme") == "bearer":
            _ = name  # bearer scheme present
    return profile


def _requires_bearer(data: dict[str, Any], path_item: dict[str, Any], op: dict[str, Any]) -> bool:
    if "security" in op:
        sec = op.get("security")
        return isinstance(sec, list) and sec != []
    if "security" in path_item:
        sec = path_item.get("security")
        return isinstance(sec, list) and sec != []
    gs = data.get("security")
    return bool(gs)


def _extract_expect_status(responses: dict[str, Any], prefer: str | None = None) -> int:
    if not isinstance(responses, dict):
        return 200
    if prefer and prefer in responses:
        return int(prefer)
    for code in ("201", "200", "202", "204"):
        if code in responses:
            return int(code)
    for code in responses:
        try:
            return int(code)
        except (ValueError, TypeError):
            continue
    return 200


def _response_has_status(responses: dict[str, Any], code: int) -> bool:
    return isinstance(responses, dict) and str(code) in responses


def _dereference_schema(data: dict[str, Any], schema: dict[str, Any], seen: set[str] | None = None) -> dict[str, Any]:
    seen = seen or set()
    if not isinstance(schema, dict):
        return {}
    if "$ref" in schema:
        ref = schema["$ref"]
        if not isinstance(ref, str) or not ref.startswith("#/") or ref in seen:
            return {}
        seen.add(ref)
        parts = ref[2:].split("/")
        node: Any = data
        for p in parts:
            if not isinstance(node, dict):
                return {}
            node = node.get(p)
        if isinstance(node, dict):
            return _dereference_schema(data, node, seen)
        return {}
    out = dict(schema)
    props = out.get("properties")
    if isinstance(props, dict):
        out["properties"] = {
            k: _dereference_schema(data, v, seen) if isinstance(v, dict) else v for k, v in props.items()
        }
    return out


def _schema_example_value(data: dict[str, Any], prop: dict[str, Any]) -> Any:
    prop = _dereference_schema(data, prop)
    if "example" in prop:
        return prop["example"]
    if "default" in prop:
        return prop["default"]
    ptype = prop.get("type", "string")
    if ptype == "boolean":
        return True
    if ptype == "integer":
        return 1
    if ptype == "number":
        return 1.0
    if ptype == "array":
        return []
    if ptype == "object":
        return {}
    return "example"


def _json_body_from_request_body(data: dict[str, Any], request_body: dict[str, Any]) -> dict[str, Any] | None:
    content = request_body.get("content")
    if not isinstance(content, dict):
        return None
    for ck in ("application/json", "application/json; charset=utf-8"):
        if ck not in content:
            continue
        media = content[ck]
        if not isinstance(media, dict):
            continue
        ex = media.get("example")
        if isinstance(ex, dict):
            return dict(ex)
        schema = media.get("schema")
        if isinstance(schema, dict):
            sch = _dereference_schema(data, schema)
            props = sch.get("properties") if isinstance(sch.get("properties"), dict) else {}
            required = sch.get("required") if isinstance(sch.get("required"), list) else []
            req_names = [str(x) for x in required if isinstance(x, str)]
            out: dict[str, Any] = {}
            for name in req_names or list(props.keys())[:8]:
                if name in props and isinstance(props[name], dict):
                    out[name] = _schema_example_value(data, props[name])
            return out if out else None
    return None


def _json_subset_from_response(data: dict[str, Any], responses: dict[str, Any], success_code: int) -> dict[str, Any] | None:
    """从成功响应 schema 生成弱 expect_json_subset（仅顶层标量/布尔，最多 4 字段）。"""
    if not isinstance(responses, dict):
        return None
    resp_obj = responses.get(str(success_code)) or responses.get(str(success_code // 1))
    if not isinstance(resp_obj, dict):
        return None
    content = resp_obj.get("content")
    if not isinstance(content, dict):
        return None
    schema = None
    for ck in ("application/json", "application/json; charset=utf-8"):
        media = content.get(ck)
        if isinstance(media, dict) and isinstance(media.get("schema"), dict):
            schema = media["schema"]
            break
    if not schema:
        return None
    sch = _dereference_schema(data, schema)
    props = sch.get("properties") if isinstance(sch.get("properties"), dict) else {}
    if not props and sch.get("type") == "array" and isinstance(sch.get("items"), dict):
        items = _dereference_schema(data, sch["items"])
        props = items.get("properties") if isinstance(items.get("properties"), dict) else {}
    subset: dict[str, Any] = {}
    required = sch.get("required") if isinstance(sch.get("required"), list) else []
    names = list(dict.fromkeys([*(str(x) for x in required if isinstance(x, str)), *props.keys()]))
    for name in names[:4]:
        if name not in props or not isinstance(props[name], dict):
            continue
        p = props[name]
        ptype = p.get("type")
        if ptype in ("string", "integer", "number", "boolean"):
            subset[name] = _schema_example_value(data, p)
        elif name in ("code", "success", "status") and ptype != "object":
            subset[name] = _schema_example_value(data, p)
    return subset or None


def _build_assertions_for_case(
    data: dict[str, Any],
    responses: dict[str, Any],
    expect_status: int | list[int],
    *,
    include_json_subset: bool = True,
    max_response_ms: int | None = None,
) -> list[dict[str, Any]]:
    """从 OpenAPI 响应生成 assertions[]（与 legacy expect_* 字段并存）。"""
    assertions: list[dict[str, Any]] = [{"type": "status_code", "expected": expect_status}]

    if include_json_subset:
        primary = _status_for_assertions(expect_status)
        sub = _json_subset_from_response(data, responses, primary)
        if sub:
            assertions.append({"type": "fuzzy_subset", "subset": sub, "expected": sub})

    if max_response_ms:
        assertions.append({"type": "response_time", "max_ms": max_response_ms})

    return assertions


def _attach_assertions(
    target: dict[str, Any],
    data: dict[str, Any],
    responses: dict[str, Any],
    expect_status: int | list[int],
    *,
    include_json_subset: bool = True,
) -> None:
    if target.get("assertions"):
        return
    primary = _status_for_assertions(expect_status)
    target["assertions"] = _build_assertions_for_case(
        data,
        responses,
        expect_status,
        include_json_subset=include_json_subset,
    )
    sub = _json_subset_from_response(data, responses, primary)
    if include_json_subset and sub:
        target.setdefault("expect_json_subset", sub)


def _path_param_example_value(param: dict[str, Any]) -> str:
    if "example" in param:
        v = param["example"]
    else:
        schema = param.get("schema") if isinstance(param.get("schema"), dict) else {}
        if "example" in schema:
            v = schema["example"]
        elif schema.get("type") == "integer":
            v = 1
        else:
            v = "example"
    return quote(str(v), safe="")


def resolve_openapi_path(path: str, parameters: list[Any]) -> str:
    out = path
    if not parameters:
        return out
    for param in parameters:
        if not isinstance(param, dict) or (param.get("in") or "").lower() != "path":
            continue
        name = param.get("name")
        if isinstance(name, str):
            token = "{" + name + "}"
            if token in out:
                out = out.replace(token, _path_param_example_value(param), 1)
    m = re.search(r"\{[a-zA-Z_]\w*\}", out)
    if m:
        out = out[: m.start()] + "1" + out[m.end() :]
    return out


def _case_use_no_auth(data: dict[str, Any], path: str, path_item: dict[str, Any], op: dict[str, Any]) -> bool:
    login_paths = {DEFAULT_AUTH_PROFILE["login_path"]}
    if path in login_paths or any(path.rstrip("/").endswith(h) for h in LOGIN_PATH_HINTS):
        return True
    if path.endswith("/register") or "/auth/register" in path:
        return True
    return not _requires_bearer(data, path_item, op)


def _is_register_path(path: str) -> bool:
    p = path.rstrip("/")
    return p.endswith("/register") or "/auth/register" in path


def _is_username_field(name: str) -> bool:
    kl = name.lower()
    return "user" in kl and "password" not in kl and kl not in ("password_hash",)


def _unique_register_username(prefix: str = "reg") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def _unique_bounded_string(value: str, seed: str) -> str:
    """保持原长度，嵌入 seed 哈希，避免 register 重复跑撞用户名。"""
    if not value:
        return value
    n = len(value)
    tag = hashlib.md5(seed.encode()).hexdigest()[: min(8, n)]
    if n <= len(tag):
        return tag[:n]
    return value[: n - len(tag)] + tag


def _apply_login_env_body(path: str, method_upper: str, jb: dict[str, Any]) -> dict[str, Any]:
    is_login = method_upper == "POST" and any(
        path.rstrip("/").endswith(h.rstrip("/")) or h in path for h in LOGIN_PATH_HINTS
    )
    if not is_login:
        return jb
    out = dict(jb)
    for key in list(out.keys()):
        kl = key.lower()
        if "user" in kl or kl in ("email", "account"):
            out[key] = "__ENV__:TEST_USERNAME"
        elif "pass" in kl or "pwd" in kl:
            out[key] = "__ENV__:TEST_PASSWORD"
    return out


def _apply_register_unique_body(path: str, method_upper: str, jb: dict[str, Any]) -> dict[str, Any]:
    if method_upper != "POST" or not _is_register_path(path):
        return jb
    out = dict(jb)
    for key in list(out.keys()):
        if _is_username_field(key) and not str(out[key]).startswith("__ENV__:"):
            out[key] = _unique_register_username()
    return out


def _request_body_schema(data: dict[str, Any], request_body: dict[str, Any]) -> dict[str, Any] | None:
    content = request_body.get("content") if isinstance(request_body.get("content"), dict) else {}
    for ck in ("application/json", "application/json; charset=utf-8"):
        media = content.get(ck)
        if isinstance(media, dict) and isinstance(media.get("schema"), dict):
            return _dereference_schema(data, media["schema"])
    return None


def _validation_error_statuses(responses: dict[str, Any]) -> int | list[int] | None:
    """OpenAPI 同时声明 422/400 时返回列表，避免实现差异假红。"""
    codes = [c for c in (422, 400) if _response_has_status(responses, c)]
    if not codes:
        return None
    return codes[0] if len(codes) == 1 else codes


def _validation_error_status(responses: dict[str, Any]) -> int | None:
    val = _validation_error_statuses(responses)
    if isinstance(val, list):
        return int(val[0])
    return val


def _status_for_assertions(expect_status: int | list[int]) -> int:
    if isinstance(expect_status, list):
        return int(expect_status[0])
    return int(expect_status)


def _expect_sig(expect: Any) -> str:
    if isinstance(expect, list):
        return json.dumps(expect)
    return str(int(expect))


def _str_of_length(n: int) -> str:
    if n <= 0:
        return ""
    return "a" * n


def _slug_token(text: str) -> str:
    s = re.sub(r"[^0-9a-zA-Z_-]+", "-", str(text).strip()).strip("-")
    return s or "field"


def _boundary_variants_for_field(
    field_name: str,
    prop: dict[str, Any],
) -> list[tuple[Any, bool, str, str]]:
    """单字段边界 trio：返回 (值, 是否应成功, id 后缀, 可读描述)。"""
    ptype = prop.get("type", "string")
    variants: list[tuple[Any, bool, str, str]] = []
    seen: set[tuple[Any, bool]] = set()

    def add(value: Any, ok: bool, suffix: str, label: str) -> None:
        key = (value, ok)
        if key in seen:
            return
        seen.add(key)
        variants.append((value, ok, suffix, label))

    min_len = prop.get("minLength")
    max_len = prop.get("maxLength")
    minimum = prop.get("minimum")
    maximum = prop.get("maximum")
    enum_vals = prop.get("enum")

    if ptype == "string":
        if isinstance(max_len, int) and max_len >= 0:
            if max_len >= 1:
                add(
                    _str_of_length(max_len - 1),
                    True,
                    f"{field_name}-len-{max_len - 1}",
                    f"{field_name} 长度 {max_len - 1}（maxLength-1）",
                )
            add(
                _str_of_length(max_len),
                True,
                f"{field_name}-len-{max_len}",
                f"{field_name} 长度 {max_len}（maxLength）",
            )
            add(
                _str_of_length(max_len + 1),
                False,
                f"{field_name}-len-{max_len + 1}",
                f"{field_name} 长度 {max_len + 1}（maxLength+1）",
            )
        if isinstance(min_len, int) and min_len > 0:
            below_val = _str_of_length(min_len - 1) if min_len > 1 else ""
            add(
                below_val,
                False,
                f"{field_name}-below-minlen-{min_len}",
                f"{field_name} 低于 minLength {min_len}",
            )
            add(
                _str_of_length(min_len),
                True,
                f"{field_name}-minlen-{min_len}",
                f"{field_name} 长度 minLength {min_len}",
            )

    elif ptype == "integer":
        if isinstance(minimum, int):
            add(minimum - 1, False, f"{field_name}-lt-min-{minimum}", f"{field_name}={minimum - 1}（minimum-1）")
            add(minimum, True, f"{field_name}-at-min-{minimum}", f"{field_name}={minimum}（minimum）")
        if isinstance(maximum, int):
            add(maximum, True, f"{field_name}-at-max-{maximum}", f"{field_name}={maximum}（maximum）")
            add(maximum + 1, False, f"{field_name}-gt-max-{maximum}", f"{field_name}={maximum + 1}（maximum+1）")
    elif ptype == "number":
        if isinstance(minimum, (int, float)):
            mn = float(minimum)
            add(mn - 0.01, False, f"{field_name}-lt-min", f"{field_name} 低于 minimum {mn}")
            add(mn, True, f"{field_name}-at-min", f"{field_name}={mn}（minimum）")
        if isinstance(maximum, (int, float)):
            mx = float(maximum)
            add(mx, True, f"{field_name}-at-max", f"{field_name}={mx}（maximum）")
            add(mx + 0.01, False, f"{field_name}-gt-max", f"{field_name} 超过 maximum {mx}")

    if isinstance(enum_vals, list) and enum_vals:
        invalid = "__INVALID_ENUM__"
        while invalid in enum_vals:
            invalid += "_"
        add(invalid, False, f"{field_name}-enum-invalid", f"{field_name} 非法枚举值")

    return variants


def _field_has_constraints(prop: dict[str, Any]) -> bool:
    if not isinstance(prop, dict):
        return False
    keys = ("minLength", "maxLength", "minimum", "maximum", "enum")
    return any(k in prop for k in keys)


def _query_from_parameters(data: dict[str, Any], parameters: list[Any]) -> dict[str, str]:
    """从 OpenAPI query 参数生成默认 query 字典（字符串值，与 spec 一致）。"""
    query: dict[str, str] = {}
    for param in parameters:
        if not isinstance(param, dict) or (param.get("in") or "").lower() != "query":
            continue
        name = param.get("name")
        if not isinstance(name, str):
            continue
        schema = param.get("schema") if isinstance(param.get("schema"), dict) else {}
        schema = _dereference_schema(data, schema) if schema else {}
        if "example" in param:
            query[name] = str(param["example"])
        elif "example" in schema:
            query[name] = str(schema["example"])
        elif schema.get("type") == "integer":
            query[name] = str(schema.get("default", schema.get("minimum", 1)))
        elif schema.get("type") == "number":
            query[name] = str(schema.get("default", schema.get("minimum", 1)))
        else:
            query[name] = str(schema.get("default", "example"))
    return query


def _format_query_value(value: Any, prop: dict[str, Any]) -> str:
    ptype = prop.get("type", "string")
    if ptype == "integer":
        return str(int(value))
    if ptype == "number":
        return str(float(value))
    return str(value)


def _query_boundary_cases_for_op(
    data: dict[str, Any],
    path: str,
    resolved_path: str,
    method_upper: str,
    path_item: dict[str, Any],
    op: dict[str, Any],
    base_case: dict[str, Any],
    parameters: list[Any],
    *,
    max_cases: int = 12,
) -> list[dict[str, Any]]:
    """从 query 参数 schema 约束生成 E 层边界用例（GET 等）。"""
    if method_upper != "GET":
        return []
    base_query = base_case.get("query")
    if not isinstance(base_query, dict) or not base_query:
        return []

    responses = op.get("responses") if isinstance(op.get("responses"), dict) else {}
    success_status = int(base_case.get("expect_status") or _extract_expect_status(responses))
    fail_status = _validation_error_statuses(responses)

    out: list[dict[str, Any]] = []
    dedupe: set[tuple[str, str, int]] = set()

    for param in parameters:
        if not isinstance(param, dict) or (param.get("in") or "").lower() != "query":
            continue
        name = param.get("name")
        if not isinstance(name, str) or name not in base_query:
            continue
        schema = param.get("schema") if isinstance(param.get("schema"), dict) else {}
        prop = _dereference_schema(data, schema) if schema else {}
        if not _field_has_constraints(prop):
            continue

        for value, should_succeed, suffix, label in _boundary_variants_for_field(name, prop):
            expect = success_status if should_succeed else fail_status
            if not should_succeed and fail_status is None:
                continue
            if not should_succeed and expect is None:
                continue
            q = dict(base_query)
            q[name] = _format_query_value(value, prop)
            sig = (name, json.dumps(q, sort_keys=True), _expect_sig(expect))
            if sig in dedupe:
                continue
            dedupe.add(sig)

            case_id = f"{base_case['id']}-E-query-{_slug_token(suffix)}"
            ec: dict[str, Any] = {
                "id": case_id,
                "method": method_upper,
                "path": resolved_path,
                "expect_status": expect,
                "query": q,
                "layer": "E",
                "name": f"边界 query.{label} · {method_upper} {path}",
                "review_required": True,
            }
            if base_case.get("no_auth"):
                ec["no_auth"] = True
            out.append(ec)
            if len(out) >= max_cases:
                return out

    return out


def _boundary_cases_for_op(
    data: dict[str, Any],
    path: str,
    resolved_path: str,
    method_upper: str,
    path_item: dict[str, Any],
    op: dict[str, Any],
    base_case: dict[str, Any],
    request_body: dict[str, Any],
    base_body: dict[str, Any],
    *,
    max_cases: int = 24,
) -> list[dict[str, Any]]:
    """从 requestBody schema 约束生成 E 层边界用例（限-1/限/限+1 等）。"""
    if method_upper not in ("POST", "PUT", "PATCH") or not base_body:
        return []

    schema = _request_body_schema(data, request_body)
    if not schema:
        return []

    responses = op.get("responses") if isinstance(op.get("responses"), dict) else {}
    success_status = int(base_case.get("expect_status") or _extract_expect_status(responses))
    fail_status = _validation_error_statuses(responses)

    props = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
    out: list[dict[str, Any]] = []
    dedupe: set[tuple[str, str, int]] = set()

    for field_name, raw_prop in props.items():
        if not isinstance(raw_prop, dict):
            continue
        if isinstance(base_body.get(field_name), str) and str(base_body[field_name]).startswith("__ENV__:"):
            continue
        prop = _dereference_schema(data, raw_prop)
        if not _field_has_constraints(prop):
            continue

        for value, should_succeed, suffix, label in _boundary_variants_for_field(field_name, prop):
            expect = success_status if should_succeed else fail_status
            if not should_succeed and fail_status is None:
                continue
            if not should_succeed and expect is None:
                continue
            body = dict(base_body)
            body[field_name] = value
            case_id = f"{base_case['id']}-E-{_slug_token(suffix)}"
            if _is_register_path(path) and should_succeed:
                for uname_key in list(body.keys()):
                    if not _is_username_field(uname_key):
                        continue
                    if field_name == uname_key:
                        body[uname_key] = _unique_bounded_string(str(value), case_id)
                    else:
                        body[uname_key] = _unique_register_username()
                    break
            sig = (field_name, json.dumps(body, sort_keys=True, ensure_ascii=False), _expect_sig(expect))
            if sig in dedupe:
                continue
            dedupe.add(sig)
            ec: dict[str, Any] = {
                "id": case_id,
                "method": method_upper,
                "path": resolved_path,
                "expect_status": expect,
                "json_body": body,
                "layer": "E",
                "name": f"边界 {label} · {method_upper} {path}",
                "review_required": True,
            }
            if base_case.get("no_auth"):
                ec["no_auth"] = True
            out.append(ec)
            if len(out) >= max_cases:
                return out

    return out


def _build_invalid_body(data: dict[str, Any], request_body: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(request_body, dict):
        return None
    full = _json_body_from_request_body(data, request_body)
    if not full:
        return {}
    content = request_body.get("content") if isinstance(request_body.get("content"), dict) else {}
    schema = None
    for ck in ("application/json",):
        media = content.get(ck)
        if isinstance(media, dict) and isinstance(media.get("schema"), dict):
            schema = _dereference_schema(data, media["schema"])
            break
    if not schema:
        key = next(iter(full))
        bad = dict(full)
        bad.pop(key, None)
        return bad if bad else {}
    required = schema.get("required") if isinstance(schema.get("required"), list) else []
    if required:
        bad = dict(full)
        bad.pop(str(required[0]), None)
        return bad
    bad = dict(full)
    k = next(iter(bad))
    bad[k] = None
    return bad


def _negative_cases_for_op(
    data: dict[str, Any],
    path: str,
    resolved_path: str,
    method_upper: str,
    path_item: dict[str, Any],
    op: dict[str, Any],
    base_case: dict[str, Any],
    request_body: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    responses = op.get("responses") if isinstance(op.get("responses"), dict) else {}
    out: list[dict[str, Any]] = []
    needs_auth = _requires_bearer(data, path_item, op) and not base_case.get("no_auth")

    if needs_auth and (_response_has_status(responses, 401) or _response_has_status(responses, 403)):
        expect = 401 if _response_has_status(responses, 401) else 403
        nc: dict[str, Any] = {
            "id": f"{base_case['id']}-X-{expect}-no-auth",
            "method": method_upper,
            "path": resolved_path,
            "expect_status": expect,
            "no_auth": True,
            "layer": "X",
            "name": f"未鉴权访问 {method_upper} {path} → {expect}",
        }
        if base_case.get("json_body") is not None and method_upper in ("POST", "PUT", "PATCH"):
            nc["json_body"] = base_case["json_body"]
        if base_case.get("query"):
            nc["query"] = base_case["query"]
        out.append(nc)

    fail_expect = _validation_error_statuses(responses)

    if method_upper in ("POST", "PUT", "PATCH") and fail_expect is not None:
        bad_body = _build_invalid_body(data, request_body)
        if bad_body is not None:
            nc422: dict[str, Any] = {
                "id": f"{base_case['id']}-X-422-invalid-body",
                "method": method_upper,
                "path": resolved_path,
                "expect_status": fail_expect,
                "json_body": bad_body,
                "layer": "X",
                "name": f"非法请求体 {method_upper} {path} → {fail_expect}",
                "review_required": True,
            }
            if base_case.get("no_auth"):
                nc422["no_auth"] = True
            out.append(nc422)

    if _response_has_status(responses, 400) and method_upper in ("POST", "PUT", "PATCH"):
        nc400: dict[str, Any] = {
            "id": f"{base_case['id']}-X-400-empty-body",
            "method": method_upper,
            "path": resolved_path,
            "expect_status": 400,
            "json_body": {},
            "layer": "X",
            "name": f"空/缺字段请求体 {method_upper} {path} → 400",
            "review_required": True,
        }
        if base_case.get("no_auth"):
            nc400["no_auth"] = True
        out.append(nc400)

    return out


def _chain_list_prefix(paths: dict[str, Any], templated_path: str) -> tuple[str, str] | None:
    if templated_path.count("{") != 1 or templated_path.count("}") != 1:
        return None
    i = templated_path.index("{")
    j = templated_path.index("}")
    param = templated_path[i + 1 : j]
    prefix = templated_path[:i].rstrip("/") or "/"
    pi = paths.get(prefix)
    if not isinstance(pi, dict) or "get" not in pi:
        return None
    return prefix, param


def _build_list_chain_scenario(
    data: dict[str, Any],
    paths: dict[str, Any],
    path: str,
    method_upper: str,
    path_item: dict[str, Any],
    op: dict[str, Any],
    expect_status: int,
    request_body: Any,
) -> dict[str, Any] | None:
    hit = _chain_list_prefix(paths, path)
    if not hit:
        return None
    prefix, param_name = hit
    path_item_p = paths[prefix]
    get_op = path_item_p.get("get")
    if not isinstance(get_op, dict):
        return None
    list_no_auth = not _requires_bearer(data, path_item_p, get_op)
    jb2 = _json_body_from_request_body(data, request_body) if isinstance(request_body, dict) else None
    step1: dict[str, Any] = {
        "method": "GET",
        "path": prefix,
        "expect_status": 200,
        "capture": {param_name: "0.id"},
    }
    if list_no_auth:
        step1["no_auth"] = True
    step2: dict[str, Any] = {"method": method_upper, "path": path, "expect_status": expect_status}
    if jb2 is not None and method_upper in ("POST", "PUT", "PATCH"):
        step2["json_body"] = jb2
    responses = op.get("responses") if isinstance(op.get("responses"), dict) else {}
    list_responses = get_op.get("responses") if isinstance(get_op.get("responses"), dict) else {}
    _attach_assertions(step1, data, list_responses, 200, include_json_subset=False)
    _attach_assertions(step2, data, responses, expect_status, include_json_subset=True)
    return {"name": f"链式-{method_upper}-{path}", "steps": [step1, step2]}


def build_openapi_artifacts(
    data: dict[str, Any],
    *,
    base_url: str = "http://your-server:port",
    auth_profile: dict[str, Any] | None = None,
    include_negatives: bool = True,
    include_boundaries: bool | None = None,
    include_json_subset: bool = True,
    mode: str = "full",
) -> dict[str, Any]:
    """返回 { spec_meta, cases_draft, mode }；mode=smoke 时不含 X/E 层扩展用例。"""
    paths = data.get("paths")
    if not isinstance(paths, dict) or not paths:
        raise ValueError("OpenAPI 缺少 paths")

    profile = auth_profile or infer_auth_profile_from_openapi(data)
    valid_methods = {"get", "post", "put", "delete", "patch"}
    cases: list[dict[str, Any]] = []
    scenarios: list[dict[str, Any]] = []
    cases_draft: list[dict[str, Any]] = []
    any_bearer = False

    for _p, _pi in paths.items():
        if not isinstance(_pi, dict):
            continue
        for _m, _op in _pi.items():
            if _m.lower() in valid_methods and isinstance(_op, dict) and _requires_bearer(data, _pi, _op):
                any_bearer = True
                break
        if any_bearer:
            break

    do_negatives = include_negatives and mode != "smoke"
    do_boundaries = (mode != "smoke") if include_boundaries is None else include_boundaries

    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        path_level = path_item.get("parameters") if isinstance(path_item.get("parameters"), list) else []
        for method, op in path_item.items():
            if method.lower() not in valid_methods or not isinstance(op, dict):
                continue

            method_upper = method.upper()
            responses = op.get("responses") if isinstance(op.get("responses"), dict) else {}
            expect_status = _extract_expect_status(responses)
            request_body = op.get("requestBody")

            chain = _build_list_chain_scenario(
                data, paths, path, method_upper, path_item, op, expect_status,
                request_body if isinstance(request_body, dict) else None,
            )
            if chain is not None:
                scenarios.append(chain)
                cases_draft.append(
                    {
                        "name": chain["name"],
                        "layer": "H",
                        "priority": "P1",
                        "automation": {"kind": "scenario", **chain},
                    }
                )
                continue

            op_level = op.get("parameters") if isinstance(op.get("parameters"), list) else []
            all_params = path_level + op_level
            resolved_path = resolve_openapi_path(path, all_params)
            cid = f"TC-{method_upper}-{path}".replace("/", "-").replace("{", "").replace("}", "")

            case: dict[str, Any] = {
                "id": cid,
                "method": method_upper,
                "path": resolved_path,
                "expect_status": expect_status,
            }
            query = _query_from_parameters(data, all_params)
            if query:
                case["query"] = query
            if isinstance(request_body, dict):
                jb = _json_body_from_request_body(data, request_body)
                if jb:
                    jb = _apply_login_env_body(path, method_upper, jb)
                    jb = _apply_register_unique_body(path, method_upper, jb)
                    case["json_body"] = jb
            if _case_use_no_auth(data, path, path_item, op):
                case["no_auth"] = True

            if include_json_subset:
                sub = _json_subset_from_response(data, responses, expect_status)
                if sub:
                    case["expect_json_subset"] = sub

            _attach_assertions(case, data, responses, expect_status, include_json_subset=include_json_subset)

            cases.append(case)
            cases_draft.append(
                {
                    "name": f"{method_upper} {path} 主路径",
                    "layer": "H",
                    "priority": "P1",
                    "automation": {k: v for k, v in case.items() if k != "layer"},
                }
            )

            if do_negatives:
                for nc in _negative_cases_for_op(
                    data, path, resolved_path, method_upper, path_item, op, case,
                    request_body if isinstance(request_body, dict) else None,
                ):
                    _attach_assertions(
                        nc, data, responses, nc["expect_status"], include_json_subset=False
                    )
                    cases.append({k: v for k, v in nc.items() if k not in ("layer", "name")})
                    cases_draft.append(
                        {
                            "name": nc.get("name", nc["id"]),
                            "layer": "X",
                            "priority": "P1",
                            "automation": {k: v for k, v in nc.items() if k not in ("layer", "name")},
                        }
                    )

            if do_boundaries and isinstance(request_body, dict) and case.get("json_body"):
                for ec in _boundary_cases_for_op(
                    data,
                    path,
                    resolved_path,
                    method_upper,
                    path_item,
                    op,
                    case,
                    request_body,
                    case["json_body"],
                ):
                    _attach_assertions(
                        ec, data, responses, ec["expect_status"], include_json_subset=False
                    )
                    cases.append({k: v for k, v in ec.items() if k not in ("layer", "name")})
                    cases_draft.append(
                        {
                            "name": ec.get("name", ec["id"]),
                            "layer": "E",
                            "priority": "P2",
                            "automation": {k: v for k, v in ec.items() if k not in ("layer", "name")},
                        }
                    )

            if do_boundaries and case.get("query"):
                for ec in _query_boundary_cases_for_op(
                    data,
                    path,
                    resolved_path,
                    method_upper,
                    path_item,
                    op,
                    case,
                    all_params,
                ):
                    _attach_assertions(
                        ec, data, responses, ec["expect_status"], include_json_subset=False
                    )
                    cases.append({k: v for k, v in ec.items() if k not in ("layer", "name")})
                    cases_draft.append(
                        {
                            "name": ec.get("name", ec["id"]),
                            "layer": "E",
                            "priority": "P2",
                            "automation": {k: v for k, v in ec.items() if k not in ("layer", "name")},
                        }
                    )

    spec_meta: dict[str, Any] = {
        "kind": "api_pytest",
        "base_url": base_url.rstrip("/"),
        "import_mode": mode,
        "cases": cases,
    }
    if scenarios:
        spec_meta["scenarios"] = scenarios
    if profile.get("type"):
        spec_meta["auth"] = {k: v for k, v in profile.items() if k != "notes"}
        sh = profile.get("session_headers")
        if isinstance(sh, dict) and sh:
            spec_meta["session_headers"] = sh

    cases_draft_root: dict[str, Any] = {
        "base_url": base_url.rstrip("/"),
        "import_mode": mode,
        "auth": spec_meta.get("auth"),
        "cases": cases_draft,
        "scenarios": scenarios,
    }
    if spec_meta.get("session_headers"):
        cases_draft_root["session_headers"] = spec_meta["session_headers"]

    return {
        "spec_meta": spec_meta,
        "cases_draft": cases_draft_root,
        "mode": mode,
    }


def spec_meta_to_markdown(spec_meta: dict[str, Any], *, title: str | None = None) -> str:
    if yaml is None:
        raise RuntimeError("需要 PyYAML")
    mode = spec_meta.get("import_mode", "full")
    fm = yaml.dump(spec_meta, allow_unicode=True, default_flow_style=False, sort_keys=False).rstrip()
    if title is None:
        title = "OpenAPI 导入 - 自动生成（冒烟模式）" if mode == "smoke" else "OpenAPI 导入 - 自动生成（含 X/E 层扩展）"
    body = f"\n# {title}\n\n"
    if mode == "smoke":
        body += (
            "> **import_mode: smoke** — 仅主路径连通性；正式回归请走 "
            "`OpenAPI → 用例表评审 → testcase_to_api_spec → generate.sh`（见 `api-skills/执行/references/openapi_pipeline.md`）。\n"
        )
    else:
        body += (
            "> 含 H 主路径 + X 层负例骨架 + E 层 schema 边界（min/maxLength、minimum/maximum、enum）；请评审后再纳入准出。\n"
            "> 推荐：`python codegen/openapi_to_cases.py` 产出 JSON → 人工/AI 补全 → `testcase_to_api_spec.py`。\n"
        )
    return f"---\n{fm}\n---{body}"


def write_cases_draft_json(draft: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(draft, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
