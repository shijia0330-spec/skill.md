"""Shared HAR → REST API endpoint parsing (seckill / generic REST)."""
from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import parse_qs, urlparse

_API_PATH_MARKERS = ("/api/",)


def _is_api_url(url: str) -> bool:
    return any(m in url for m in _API_PATH_MARKERS)


def parse_json_body(entry: dict[str, Any]) -> dict[str, Any] | None:
    post = entry.get("request", {}).get("postData") or {}
    raw = post.get("text") or ""
    if not raw.strip():
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def unique_create_body(body: dict[str, Any], *, prefix: str = "har-demo") -> dict[str, Any]:
    out = dict(body)
    if "username" in out:
        out["username"] = f"{prefix}-{{{{timestamp}}}}-{{{{vu}}}}"
    if "name" in out and isinstance(out["name"], str):
        out["name"] = f"{prefix}-{{{{timestamp}}}}"
    if "description" in out:
        out["description"] = "HAR 导入自动化"
    return out


def har_entry_to_endpoint(entry: dict[str, Any], *, idx: int) -> dict[str, Any] | None:
    req = entry.get("request") or {}
    method = (req.get("method") or "GET").upper()
    if method == "CONNECT":
        return None
    url = req.get("url") or ""
    if not _is_api_url(url):
        return None

    parsed = urlparse(url)
    path = parsed.path
    if parsed.query:
        path = f"{path}?{parsed.query}"

    name = f"{method} {path.split('?')[0]}"
    if "/api/products" in path and method == "GET":
        name = "商品列表"
    elif "/api/auth/login" in path:
        name = "用户登录"
    elif "/api/auth/register" in path:
        name = "用户注册"

    weight = 7 if method == "GET" else 3
    ep: dict[str, Any] = {
        "name": name,
        "method": method,
        "path": path.split("?")[0],
        "weight": weight,
        "headers": {
            "Authorization": "Bearer ${PERF_ACCESS_TOKEN}",
        },
        "expect_status": 200,
        "max_response_ms": 3000 if method == "POST" else 2000,
    }

    body = parse_json_body(entry)
    if body is not None:
        if method in ("POST", "PUT", "PATCH"):
            ep["json_body"] = unique_create_body(body, prefix="load") if "/register" in path else body
            ep["headers"]["Content-Type"] = "application/json"

    return ep


def collect_har_endpoints(
    har: dict[str, Any],
    *,
    filter_api_smoke_only: bool = False,
) -> list[dict[str, Any]]:
    entries = har.get("log", {}).get("entries") or []
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    smoke_paths = ("/api/products", "/api/auth/login", "/api/auth/profile")
    for i, entry in enumerate(entries):
        ep = har_entry_to_endpoint(entry, idx=i + 1)
        if not ep:
            continue
        if filter_api_smoke_only and not any(p in ep["path"] for p in smoke_paths):
            continue
        key = (ep["method"], ep["path"])
        if key in seen:
            continue
        seen.add(key)
        out.append(ep)
    if not out:
        raise ValueError("HAR 中未找到可转换的秒杀 REST 条目（/api/）")
    return out


def infer_base_url(har: dict[str, Any], default: str) -> str:
    for entry in har.get("log", {}).get("entries") or []:
        url = (entry.get("request") or {}).get("url") or ""
        if _is_api_url(url):
            parsed = urlparse(url)
            if parsed.scheme and parsed.netloc:
                return f"{parsed.scheme}://{parsed.netloc}"
    return default.rstrip("/")
