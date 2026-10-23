#!/usr/bin/env python3
"""
HAR → cases JSON（供 testcase_to_api_spec.py / api-skills 执行链路使用）。

用法:
  python codegen/har_to_cases.py -i capture.har -o output/cases_from_har.json \\
      --base-url http://your-server:5001 --auth-profile templates/auth_profiles/generic_rest.yaml
  python codegen/testcase_to_api_spec.py -i output/cases_from_har.json -o templates/imported_api.md
  python codegen/run_spec.py templates/imported_api.md -o output/imported_api.py
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]

_SECKILL_OK = [{"type": "json_path", "path": "code", "expected": 0}]


def _load_auth_profile(path: Path | None) -> dict[str, Any] | None:
    if not path or not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    if path.suffix in (".yaml", ".yml"):
        if yaml is None:
            raise RuntimeError("需要 PyYAML: pip install PyYAML")
        data = yaml.safe_load(text)
    else:
        data = json.loads(text)
    return data if isinstance(data, dict) else None


def _headers_map(entry: dict[str, Any]) -> dict[str, str]:
    return {h["name"].lower(): h["value"] for h in entry.get("request", {}).get("headers") or [] if h.get("name")}


def _parse_json_body(entry: dict[str, Any]) -> dict[str, Any] | None:
    post = entry.get("request", {}).get("postData") or {}
    raw = post.get("text") or ""
    if not raw.strip():
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _unique_create_body(body: dict[str, Any]) -> dict[str, Any]:
    out = dict(body)
    if "username" in out:
        out["username"] = "har-demo-{{timestamp}}"
    if "name" in out and isinstance(out["name"], str):
        out["name"] = "HAR自动化-{{timestamp}}"
    if "description" in out:
        out["description"] = "api-skills HAR 导入"
    return out


def har_entry_to_case(entry: dict[str, Any], *, idx: int) -> dict[str, Any] | None:
    req = entry.get("request") or {}
    method = (req.get("method") or "GET").upper()
    if method == "CONNECT":
        return None
    url = req.get("url") or ""
    if "/api/" not in url:
        return None

    parsed = urlparse(url)
    path = parsed.path
    qs = parse_qs(parsed.query)
    query = {k: v[0] for k, v in qs.items()} if qs else None

    http_status = int((entry.get("response") or {}).get("status") or 0)

    slug = re.sub(r"[^0-9a-zA-Z]+", "-", path.strip("/").split("/")[-1]).strip("-").upper() or f"API-{idx}"

    case: dict[str, Any] = {
        "id": f"TC-HAR-{slug}",
        "name": f"{method} {path}",
        "method": method,
        "path": path,
        "expect_status": http_status if http_status else 200,
        "assertions": [],
    }
    if query:
        case["query"] = query

    body = _parse_json_body(entry)
    if body is not None:
        if "/api/auth/register" in path:
            case["json_body"] = _unique_create_body(body)
            case["id"] = "TC-HAR-REGISTER"
            case["name"] = "用户注册"
        else:
            case["json_body"] = body

    if path.endswith("/api/products") and method == "GET":
        case["id"] = "TC-HAR-PRODUCTS"
        case["name"] = "商品列表"
    elif "/api/auth/login" in path:
        case["id"] = "TC-HAR-LOGIN"
        case["name"] = "用户登录"

    return case


_SMOKE_PATHS = ("/api/products", "/api/auth/login", "/api/auth/profile")


def build_cases_doc(
    har: dict[str, Any],
    *,
    base_url: str,
    auth_profile: dict[str, Any] | None,
    filter_api_smoke_only: bool,
) -> dict[str, Any]:
    entries = har.get("log", {}).get("entries") or []
    cases: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for i, entry in enumerate(entries):
        case = har_entry_to_case(entry, idx=i + 1)
        if not case:
            continue
        if filter_api_smoke_only and not any(p in case["path"] for p in _SMOKE_PATHS):
            continue
        key = (case["method"], case["path"])
        if key in seen:
            continue
        seen.add(key)
        cases.append(case)

    if not cases:
        raise ValueError("HAR 中未找到可转换的秒杀 REST 条目（/api/）")

    doc: dict[str, Any] = {
        "base_url": base_url.rstrip("/"),
        "session_headers": {},
        "cases": cases,
    }
    if auth_profile:
        auth = {k: auth_profile[k] for k in auth_profile if k != "notes"}
        doc["auth"] = auth
        if isinstance(auth_profile.get("session_headers"), dict):
            doc["session_headers"].update(auth_profile["session_headers"])
    else:
        doc["auth"] = {
            "type": "bearer_login",
            "login_path": "/api/auth/login",
            "username_env": "TEST_USERNAME",
            "password_env": "TEST_PASSWORD",
        }
    return doc


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-i", "--input", type=Path, required=True, help="HAR 文件")
    ap.add_argument("-o", "--output", type=Path, required=True, help="输出 cases JSON")
    ap.add_argument("--base-url", default=os.environ.get("TEST_BASE_URL", "http://your-server:5001"))
    ap.add_argument(
        "--auth-profile",
        type=Path,
        default=Path("templates/auth_profiles/generic_rest.yaml"),
        help="auth YAML/JSON",
    )
    ap.add_argument("--api-smoke-only", action="store_true", help="仅保留秒杀 REST /api/ 条目")
    ns = ap.parse_args()

    inp = ns.input if ns.input.is_absolute() else (ROOT / ns.input).resolve()
    out = ns.output if ns.output.is_absolute() else (ROOT / ns.output).resolve()
    auth_src = ns.auth_profile if ns.auth_profile.is_absolute() else (ROOT / ns.auth_profile).resolve()

    har = json.loads(inp.read_text(encoding="utf-8"))
    profile = _load_auth_profile(auth_src)
    doc = build_cases_doc(
        har,
        base_url=ns.base_url,
        auth_profile=profile,
        filter_api_smoke_only=ns.api_smoke_only,
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已写入: {out.resolve()} ({len(doc['cases'])} cases)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
