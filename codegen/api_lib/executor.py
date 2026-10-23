"""单条 / 链式 API 执行。"""
from __future__ import annotations

import time
from typing import Any

import requests

from .assertions import run_legacy_assertions
from .resolver import fill_body
from .token_utils import extract_token
from .variable_pool import VariablePool


from .json_path import extract_by_path


def apply_capture(response: requests.Response, capture: dict[str, str], pool: VariablePool) -> None:
    try:
        data = response.json()
    except Exception:
        return
    for var_name, dotted in capture.items():
        if isinstance(dotted, str):
            pool.set(var_name, extract_by_path(data, dotted))
    pool.extract_auto(data)


def _apply_extract_vars(response: requests.Response, extract_vars: dict[str, Any], pool: VariablePool) -> None:
    """extract_vars: { pool_var: response_field_or_jsonpath }，如 access_token: token"""
    if not extract_vars:
        return
    try:
        data = response.json()
    except Exception:
        return
    for var_name, source in extract_vars.items():
        if not isinstance(source, str):
            continue
        path = source[2:] if source.startswith("$.") else source
        if "." in path:
            val = extract_by_path(data, path)
        else:
            val = data.get(path)
            if val is None and isinstance(data.get("data"), dict):
                val = data["data"].get(path)
        if val is not None:
            pool.set(var_name, val)


def _merge_headers(session: requests.Session, extra: dict[str, Any] | None, pool: dict[str, Any]) -> dict[str, str]:
    hdr = dict(session.headers)
    if extra:
        resolved = fill_body(extra, pool)
        if isinstance(resolved, dict):
            hdr.update({k: str(v) for k, v in resolved.items()})
    return hdr


def _request(
    session: requests.Session,
    method: str,
    url: str,
    *,
    params: Any = None,
    json_body: Any = None,
    headers: dict[str, str] | None = None,
    timeout: int = 30,
) -> requests.Response:
    kw: dict[str, Any] = {"timeout": timeout}
    if headers:
        kw["headers"] = headers
    if params:
        kw["params"] = params
    m = method.upper()
    if m == "GET":
        return session.get(url, **kw)
    if m == "DELETE":
        return session.delete(url, **kw)
    if m == "POST":
        return session.post(url, json=json_body, **kw)
    if m == "PUT":
        return session.put(url, json=json_body, **kw)
    if m == "PATCH":
        return session.patch(url, json=json_body, **kw)
    raise RuntimeError(f"不支持的方法: {method}")


def run_step(
    session: requests.Session,
    pool: VariablePool,
    step: dict[str, Any],
    base_url: str,
    *,
    timeout_default: int = 30,
    prev_response: Any = None,
    refs_registry: Any = None,
) -> requests.Response:
    action = (step.get("action") or "").strip().lower()
    if action == "sleep":
        sec = float(step.get("seconds") if step.get("seconds") is not None else step.get("sec", 1))
        from .allure_helper import report_step

        with report_step(f"sleep {sec}s"):
            time.sleep(sec)

        class _SleepResponse:
            status_code = 0
            text = ""

            def json(self) -> dict[str, Any]:
                return {}

        return _SleepResponse()  # type: ignore[return-value]

    ctx = pool.as_dict()
    method = (step.get("method") or "GET").upper()
    path_tmpl = step.get("path") or "/"
    path = fill_body(path_tmpl, ctx, prev_response=prev_response)
    if not isinstance(path, str):
        path = str(path)

    params = step.get("query") or step.get("params")
    json_body = step.get("json_body")
    if json_body is not None:
        json_body = fill_body(json_body, ctx, prev_response=prev_response)

    extra = step.get("headers") or {}
    headers = _merge_headers(session, extra, ctx)
    timeout = int(step.get("timeout") or timeout_default)
    url = base_url.rstrip("/") + str(path)

    step_title = f"{method} {path_tmpl}"

    from .allure_helper import attach_http_request, attach_http_response, report_step

    with report_step(step_title):
        attach_http_request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            json_body=json_body,
        )

        t0 = time.perf_counter()
        resp = _request(session, method, url, params=params, json_body=json_body, headers=headers, timeout=timeout)
        elapsed = time.perf_counter() - t0

        attach_http_response(resp, elapsed_sec=elapsed)

        run_legacy_assertions(resp, step, ctx, elapsed)
    pool.update(ctx)

    cap = step.get("capture") or {}
    if cap:
        apply_capture(resp, cap, pool)

    if step.get("save_token"):
        try:
            data = resp.json()
            paths = step.get("token_json_paths")
            token = extract_token(data, paths if isinstance(paths, list) else None)
            if token:
                pool.set("token", token)
                pool.set("access_token", token)
        except Exception:
            pass

    _apply_extract_vars(resp, step.get("extract_vars") or {}, pool)

    if step.get("auto_extract", True):
        try:
            pool.extract_auto(resp.json())
        except Exception:
            pass

    track_ref = step.get("track_ref")
    if track_ref and refs_registry is not None:
        try:
            refs_registry.register_from_response(
                track_ref if isinstance(track_ref, dict) else {},
                resp.json(),
                source=str(step.get("id") or step.get("name") or ""),
            )
        except Exception:
            pass

    return resp


def run_case(
    session: requests.Session,
    pool: VariablePool,
    case: dict[str, Any],
    base_url: str,
    *,
    timeout_default: int = 30,
    refs_registry: Any = None,
) -> requests.Response:
    return run_step(
        session,
        pool,
        case,
        base_url,
        timeout_default=timeout_default,
        refs_registry=refs_registry,
    )


def run_scenario(
    auth_session: requests.Session,
    pool: VariablePool,
    scenario: dict[str, Any],
    base_url: str,
    *,
    anon_session: requests.Session | None = None,
    timeout_default: int = 30,
    refs_registry: Any = None,
) -> None:
    steps = scenario.get("steps") or []
    prev: Any = None
    for step in steps:
        sess = anon_session if step.get("no_auth") and anon_session else auth_session
        resp = run_step(
            sess,
            pool,
            step,
            base_url,
            timeout_default=timeout_default,
            prev_response=prev,
            refs_registry=refs_registry,
        )
        try:
            prev = resp.json()
        except Exception:
            prev = {"text": resp.text[:2000], "status_code": resp.status_code}
