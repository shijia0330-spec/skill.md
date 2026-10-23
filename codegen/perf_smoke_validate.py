#!/usr/bin/env python3
"""无 k6/JMeter 时的压测冒烟校验（requests + Token，断言 HTTP 与可选 business code）。"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "codegen"))

import yaml  # noqa: E402

from api_lib.http_client import HealingSession  # noqa: E402
from api_lib.variable_pool import VariablePool  # noqa: E402
from har_lib import collect_har_endpoints  # noqa: E402


def _resolve_body(template_obj: dict, *, vu: int, it: int) -> dict:
    raw = json.dumps(template_obj, ensure_ascii=False)
    ts = int(time.time() * 1000)
    raw = raw.replace("{{timestamp}}", str(ts)).replace("{{vu}}", str(vu)).replace("{{iter}}", str(it))
    return json.loads(raw)


def _configure_session(base: str, profile: dict) -> HealingSession:
    pool = VariablePool()
    session = HealingSession(base_url=base, var_pool=pool)
    auth_type = str(profile.get("type") or "bearer_login")
    if auth_type in ("ui_storage_login", "ui_storage_login"):
        session.configure_ui_console_login({**profile, "type": "ui_storage_login"})
    else:
        session.configure_bearer_login(profile)
    return session


def _response_ok(r, *, expect_business_code: bool) -> bool:
    if r.status_code != 200:
        return False
    if not expect_business_code:
        return True
    try:
        data = r.json()
    except Exception:
        return True
    if not isinstance(data, dict):
        return True
    return data.get("code") in (0, "0", None)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-i", "--har", type=Path, required=True)
    ap.add_argument("--base-url", default=os.environ.get("TEST_BASE_URL", "http://your-server:5001"))
    ap.add_argument(
        "--auth-profile",
        type=Path,
        default=ROOT / "templates/auth_profiles/generic_rest.yaml",
    )
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--api-smoke-only", action="store_true", help="仅校验秒杀 /api/ 条目")
    ns = ap.parse_args()

    har_path = ns.har if ns.har.is_absolute() else ROOT / ns.har
    har = json.loads(har_path.read_text(encoding="utf-8"))
    endpoints = collect_har_endpoints(har, filter_api_smoke_only=ns.api_smoke_only)

    profile_path = ns.auth_profile if ns.auth_profile.is_absolute() else ROOT / ns.auth_profile
    profile = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    base = ns.base_url.rstrip("/")
    session = _configure_session(base, profile)
    expect_business = profile.get("type") in ("ui_storage_login", "ui_storage_login")

    weights = [ep.get("weight", 1) for ep in endpoints]
    ok = 0
    fail = 0
    for i in range(ns.rounds):
        ep = random.choices(endpoints, weights=weights, k=1)[0]
        method = ep["method"]
        url = base + ep["path"]
        hdrs = {}
        token = (session.headers.get("Authorization") or "").replace("Bearer ", "", 1).strip()
        for k, v in ep.get("headers", {}).items():
            val = str(v).replace("${PERF_ACCESS_TOKEN}", token)
            if k.lower() == "authorization":
                val = f"Bearer {token}" if token else str(v)
            hdrs[k] = val
        body = None
        if ep.get("json_body"):
            body = _resolve_body(ep["json_body"], vu=1, it=i)
        if method == "GET":
            r = session.get(url, headers=hdrs, timeout=30)
        elif method == "POST":
            r = session.post(url, json=body, headers=hdrs, timeout=30)
        else:
            raise RuntimeError(f"不支持: {method}")
        if _response_ok(r, expect_business_code=expect_business):
            ok += 1
            print(f"OK  {method} {ep['path']}")
        else:
            fail += 1
            print(f"FAIL {method} {ep['path']} status={r.status_code} body={r.text[:200]}", file=sys.stderr)

    session.close()
    print(f"冒烟完成: ok={ok} fail={fail}", file=sys.stderr)
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
