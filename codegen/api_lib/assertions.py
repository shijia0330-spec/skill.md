"""断言引擎：22 种断言类型注册表。"""
from __future__ import annotations

import json
import re
import time
from typing import Any, Callable

import requests

from .resolver import fill_body, resolve_string, _json_get_by_path

AssertionFn = Callable[[requests.Response, dict[str, Any], dict[str, Any], float], None]


def _resp_text_contains(resp: requests.Response, needle: str) -> bool:
    if needle in resp.text:
        return True
    try:
        blob = json.dumps(resp.json(), ensure_ascii=False)
    except Exception:
        return False
    return needle in blob


def _check_json_subset(resp: object, sub: dict) -> None:
    if not isinstance(resp, dict) or not isinstance(sub, dict):
        assert resp == sub
        return
    for k, v in sub.items():
        assert k in resp, (k, list(resp.keys()) if isinstance(resp, dict) else resp)
        if isinstance(v, dict) and isinstance(resp[k], dict):
            _check_json_subset(resp[k], v)
        else:
            assert resp[k] == v


def _resolve_expected(raw: Any, pool: dict[str, Any]) -> Any:
    if isinstance(raw, str):
        if raw == "${not_empty}":
            return "__NOT_EMPTY__"
        if raw == "${not_zero}":
            return "__NOT_ZERO__"
        if raw.startswith("${") and raw.endswith("}"):
            key = raw[2:-1]
            return pool.get(key)
        return resolve_string(raw, pool)
    if isinstance(raw, dict):
        return {k: _resolve_expected(v, pool) for k, v in raw.items()}
    if isinstance(raw, list):
        return [_resolve_expected(x, pool) for x in raw]
    return raw


def _normalize_status_expectation(expected: Any) -> int | list[int]:
    if isinstance(expected, (list, tuple)):
        out = [int(x) for x in expected]
        if not out:
            raise ValueError("expect_status / accept_status 列表不能为空")
        return out
    return int(expected)


def _assert_status_code(r: requests.Response, cfg: dict, pool: dict, _elapsed: float) -> None:
    expected = _normalize_status_expectation(cfg.get("expected", cfg.get("expect", 200)))
    if isinstance(expected, list):
        assert r.status_code in expected, (
            f"期望 {expected} 之一，实际 {r.status_code}: {r.text[:800]}"
        )
        return
    assert r.status_code == expected, f"期望 {expected}，实际 {r.status_code}: {r.text[:800]}"


def _assert_json_path(r: requests.Response, cfg: dict, pool: dict, _elapsed: float) -> None:
    path = cfg.get("path") or cfg.get("json_path") or "$.data"
    expected = _resolve_expected(cfg.get("expected"), pool)
    data = r.json()
    path_clean = path.lstrip("$.").lstrip("$")
    actual = _json_get_by_path(data, path_clean)
    if expected == "__NOT_EMPTY__":
        assert actual not in (None, "", [], {}), f"json_path {path} 为空"
        return
    if expected == "__NOT_ZERO__":
        assert actual != 0, f"json_path {path}: 期望非 0，实际 {actual!r}"
        return
    assert actual == expected, f"json_path {path}: 期望 {expected!r}，实际 {actual!r}"


def _assert_json_schema(r: requests.Response, cfg: dict, pool: dict, _elapsed: float) -> None:
    schema = cfg.get("schema") or cfg.get("expected")
    data = r.json()
    try:
        import jsonschema

        jsonschema.validate(instance=data, schema=schema)
    except ImportError:
        _assert_type_schema(r, {"schema": schema}, pool, _elapsed)


def _assert_response_time(r: requests.Response, cfg: dict, pool: dict, elapsed: float) -> None:
    max_ms = cfg.get("max_ms") or cfg.get("expected")
    if max_ms is None:
        max_ms = 3000
    assert elapsed * 1000 <= float(max_ms), f"响应时间 {elapsed*1000:.0f}ms 超过 {max_ms}ms"


def _assert_regex(r: requests.Response, cfg: dict, pool: dict, _elapsed: float) -> None:
    pattern = cfg.get("pattern") or cfg.get("expected", "")
    flags = re.DOTALL if cfg.get("dotall") else 0
    assert re.search(pattern, r.text, flags), f"regex {pattern!r} 未匹配响应"


def _assert_header(r: requests.Response, cfg: dict, pool: dict, _elapsed: float) -> None:
    name = cfg.get("name") or cfg.get("header")
    expected = _resolve_expected(cfg.get("expected"), pool)
    actual = r.headers.get(name or "")
    if cfg.get("contains"):
        assert expected in actual, f"header {name}: {actual!r} 不含 {expected!r}"
    else:
        assert actual == str(expected), f"header {name}: 期望 {expected!r}，实际 {actual!r}"


def _assert_custom(r: requests.Response, cfg: dict, pool: dict, elapsed: float) -> None:
    expr = cfg.get("expr") or cfg.get("expression")
    if not expr:
        return
    local = {"r": r, "response": r, "pool": pool, "elapsed": elapsed, "json": r.json()}
    assert eval(expr, {"__builtins__": {}}, local), f"custom 断言失败: {expr}"


def _assert_fuzzy_text(r: requests.Response, cfg: dict, pool: dict, _elapsed: float) -> None:
    expected = str(_resolve_expected(cfg.get("expected"), pool))
    threshold = float(cfg.get("threshold", 0.8))
    text = r.text
    if expected in text:
        return
    ratio = len(set(expected) & set(text)) / max(len(set(expected)), 1)
    assert ratio >= threshold, f"fuzzy_text 相似度 {ratio:.2f} < {threshold}"


def _assert_fuzzy_number(r: requests.Response, cfg: dict, pool: dict, _elapsed: float) -> None:
    path = cfg.get("path", "data")
    expected = float(_resolve_expected(cfg.get("expected"), pool))
    tolerance = float(cfg.get("tolerance", 0.01))
    actual = float(_json_get_by_path(r.json(), path.lstrip("$.")))
    assert abs(actual - expected) <= tolerance, f"fuzzy_number: {actual} vs {expected}"


def _assert_fuzzy_subset(r: requests.Response, cfg: dict, pool: dict, _elapsed: float) -> None:
    sub = _resolve_expected(cfg.get("expected") or cfg.get("subset"), pool)
    _check_json_subset(r.json(), sub)


def _assert_array_contains(r: requests.Response, cfg: dict, pool: dict, _elapsed: float) -> None:
    path = (cfg.get("path") or "data").lstrip("$.")
    item = _resolve_expected(cfg.get("item") or cfg.get("expected"), pool)
    arr = _json_get_by_path(r.json(), path)
    assert isinstance(arr, list), f"{path} 不是数组"
    assert item in arr, f"{item!r} 不在数组中"


def _assert_array_length(r: requests.Response, cfg: dict, pool: dict, _elapsed: float) -> None:
    path = (cfg.get("path") or "data").lstrip("$.")
    expected = int(_resolve_expected(cfg.get("expected"), pool))
    arr = _json_get_by_path(r.json(), path)
    assert isinstance(arr, list), f"{path} 不是数组"
    assert len(arr) == expected, f"数组长度 {len(arr)} != {expected}"


def _assert_array_sorted(r: requests.Response, cfg: dict, pool: dict, _elapsed: float) -> None:
    path = (cfg.get("path") or "data").lstrip("$.")
    key = cfg.get("key")
    arr = _json_get_by_path(r.json(), path)
    assert isinstance(arr, list), f"{path} 不是数组"
    if key:
        vals = [x.get(key) if isinstance(x, dict) else x for x in arr]
    else:
        vals = arr
    assert vals == sorted(vals, reverse=bool(cfg.get("desc"))), "数组未按预期排序"


def _assert_type_check(r: requests.Response, cfg: dict, pool: dict, _elapsed: float) -> None:
    path = (cfg.get("path") or "data").lstrip("$.")
    expected_type = cfg.get("expected_type") or cfg.get("expected")
    val = _json_get_by_path(r.json(), path)
    type_map = {
        "string": str,
        "str": str,
        "number": (int, float),
        "int": int,
        "integer": int,
        "float": float,
        "bool": bool,
        "boolean": bool,
        "array": list,
        "list": list,
        "object": dict,
        "dict": dict,
        "null": type(None),
    }
    py_type = type_map.get(str(expected_type).lower(), str)
    if isinstance(py_type, tuple):
        assert isinstance(val, py_type), f"{path} 类型 {type(val)} != {expected_type}"
    else:
        assert isinstance(val, py_type) or (val is None and py_type is type(None)), (
            f"{path} 类型 {type(val)} != {expected_type}"
        )


def _assert_type_schema(r: requests.Response, cfg: dict, pool: dict, _elapsed: float) -> None:
    schema = cfg.get("schema") or cfg.get("expected") or {}
    data = r.json()
    if not isinstance(schema, dict):
        return
    for key, typ in schema.items():
        assert key in data, f"缺少字段 {key}"
        _assert_type_check(
            r,
            {"path": key, "expected_type": typ},
            pool,
            _elapsed,
        )


def _assert_time_trend(_r: requests.Response, cfg: dict, pool: dict, elapsed: float) -> None:
    history_key = cfg.get("history_key", "_response_times")
    times: list = pool.setdefault(history_key, [])
    times.append(elapsed)
    max_samples = int(cfg.get("max_samples", 5))
    if len(times) > max_samples:
        times.pop(0)
    if len(times) >= 2 and cfg.get("direction") == "decreasing":
        assert times[-1] <= times[-2] * float(cfg.get("factor", 1.5)), "响应时间趋势未下降"


def _assert_time_between(r: requests.Response, cfg: dict, pool: dict, elapsed: float) -> None:
    min_ms = float(cfg.get("min_ms", 0))
    max_ms = float(cfg.get("max_ms", 60000))
    ms = elapsed * 1000
    assert min_ms <= ms <= max_ms, f"响应时间 {ms:.0f}ms 不在 [{min_ms}, {max_ms}]"


def _assert_and(r: requests.Response, cfg: dict, pool: dict, elapsed: float) -> None:
    for sub in cfg.get("items") or cfg.get("assertions") or []:
        run_assertions(r, [sub], pool, elapsed)


def _assert_or(r: requests.Response, cfg: dict, pool: dict, elapsed: float) -> None:
    items = cfg.get("items") or cfg.get("assertions") or []
    errors: list[str] = []
    for sub in items:
        try:
            run_assertions(r, [sub], pool, elapsed)
            return
        except AssertionError as e:
            errors.append(str(e))
    assert False, "or 断言全部失败: " + "; ".join(errors)


def _assert_not(r: requests.Response, cfg: dict, pool: dict, elapsed: float) -> None:
    sub = cfg.get("item") or (cfg.get("items") or [None])[0]
    if not sub:
        return
    try:
        run_assertions(r, [sub], pool, elapsed)
    except AssertionError:
        return
    assert False, f"not 断言不应成功: {sub}"


def _assert_llm_semantic(r: requests.Response, cfg: dict, pool: dict, _elapsed: float) -> None:
    from .llm_client import llm_judge

    prompt = cfg.get("prompt") or cfg.get("expected") or "响应语义是否符合预期？"
    try:
        payload = json.dumps(r.json(), ensure_ascii=False)
    except Exception:
        payload = r.text[:8000]
    passed, reason = llm_judge(
        system=(
            "你是 API 测试断言助手。根据用户描述判断 API 响应是否语义正确。"
            "只输出 JSON：{\"pass\": true/false, \"reason\": \"...\"}"
        ),
        user=str(prompt),
        response_payload=payload,
    )
    assert passed, f"llm_semantic 未通过: {reason}"


def _assert_llm_business(r: requests.Response, cfg: dict, pool: dict, _elapsed: float) -> None:
    from .llm_client import llm_judge

    rule = cfg.get("rule") or cfg.get("expected") or "响应符合业务规则"
    try:
        payload = json.dumps(r.json(), ensure_ascii=False)
    except Exception:
        payload = r.text[:8000]
    passed, reason = llm_judge(
        system=(
            "你是 API 业务规则校验助手。根据业务规则判断响应是否合规。"
            "只输出 JSON：{\"pass\": true/false, \"reason\": \"...\"}"
        ),
        user=str(rule),
        response_payload=payload,
    )
    assert passed, f"llm_business 未通过: {reason}"


ASSERTION_REGISTRY: dict[str, AssertionFn] = {
    "status_code": _assert_status_code,
    "json_schema": _assert_json_schema,
    "json_path": _assert_json_path,
    "response_time": _assert_response_time,
    "regex": _assert_regex,
    "header": _assert_header,
    "custom": _assert_custom,
    "fuzzy_text": _assert_fuzzy_text,
    "fuzzy_number": _assert_fuzzy_number,
    "fuzzy_subset": _assert_fuzzy_subset,
    "array_contains": _assert_array_contains,
    "array_length": _assert_array_length,
    "array_sorted": _assert_array_sorted,
    "type_check": _assert_type_check,
    "type_schema": _assert_type_schema,
    "time_trend": _assert_time_trend,
    "time_between": _assert_time_between,
    "and": _assert_and,
    "or": _assert_or,
    "not": _assert_not,
    "llm_semantic": _assert_llm_semantic,
    "llm_business": _assert_llm_business,
}


def run_assertions(
    response: requests.Response,
    assertions: list[dict[str, Any]],
    pool: dict[str, Any],
    elapsed: float,
) -> None:
    for item in assertions:
        atype = (item.get("type") or item.get("assertion") or "status_code").lower()
        fn = ASSERTION_REGISTRY.get(atype)
        if fn is None:
            raise ValueError(f"未知断言类型: {atype}")
        fn(response, item, pool, elapsed)


def run_legacy_assertions(
    response: requests.Response,
    case: dict[str, Any],
    pool: dict[str, Any],
    elapsed: float,
) -> None:
    """兼容旧 spec：expect_status / accept_status / expect_body_substrings / expect_json_subset。"""
    expect = case.get("accept_status")
    if expect is None:
        expect = case.get("expect_status")
    if expect is not None:
        run_assertions(response, [{"type": "status_code", "expected": expect}], pool, elapsed)
    elif not case.get("assertions"):
        run_assertions(response, [{"type": "status_code", "expected": 200}], pool, elapsed)

    for sub in case.get("expect_body_substrings") or []:
        assert _resp_text_contains(response, str(sub)), f"响应体不含: {sub!r}"

    subj = case.get("expect_json_subset")
    if subj is not None:
        resolved = fill_body(subj, pool)
        _check_json_subset(response.json(), resolved)

    extra = case.get("assertions") or []
    if extra:
        run_assertions(response, extra, pool, elapsed)

    max_ms = case.get("max_response_ms")
    if max_ms:
        run_assertions(response, [{"type": "response_time", "max_ms": max_ms}], pool, elapsed)
