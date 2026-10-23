#!/usr/bin/env python3
"""获取压测 Token：REST 登录或 UI 控制台登录 + 探针校验。"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "codegen"))

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]

from api_lib.http_client import HealingSession  # noqa: E402
from api_lib.variable_pool import VariablePool  # noqa: E402


def load_auth_profile(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if path.suffix in (".yaml", ".yml"):
        if yaml is None:
            raise RuntimeError("需要 PyYAML")
        data = yaml.safe_load(text)
    else:
        data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("auth profile 须为对象")
    return data


def _probe_rest(session: HealingSession, base_url: str, probe_path: str) -> bool:
    url = f"{base_url.rstrip('/')}{probe_path}"
    try:
        resp = session.get(url, timeout=30)
        if resp.status_code != 200:
            return False
        data = resp.json()
        if isinstance(data, dict) and "code" in data:
            return data.get("code") in (0, "0")
        return True
    except Exception:
        return resp.status_code == 200  # type: ignore[possibly-undefined]


def fetch_token_rest(base_url: str, auth: dict, probe_path: str) -> tuple[str, str]:
    base = base_url.rstrip("/")
    pool = VariablePool()
    session = HealingSession(base_url=base, var_pool=pool)
    session.configure_bearer_login(auth)
    if not _probe_rest(session, base, probe_path):
        raise RuntimeError(f"Token 探针失败: GET {probe_path}")
    token = pool.get("access_token") or pool.get("token") or ""
    session.close()
    if not token:
        raise RuntimeError("REST 登录未获取到 token")
    tenant = str(auth.get("tenant_id") or os.environ.get("PERF_TENANT_ID", "1"))
    return token, tenant


def fetch_token_ui(base_url: str, auth: dict, probe_path: str) -> tuple[str, str]:
    base = base_url.rstrip("/")
    pool = VariablePool()
    session = HealingSession(base_url=base, var_pool=pool)
    ui_auth = {**auth, "type": "ui_storage_login"}
    session.configure_ui_storage_login(ui_auth)

    if not _probe_rest(session, base, probe_path):
        retry_auth = {k: v for k, v in ui_auth.items() if k != "storage_state"}
        saved = os.environ.pop("UI_STORAGE_STATE", None)
        try:
            session.configure_ui_storage_login(retry_auth)
        finally:
            if saved is not None:
                os.environ["UI_STORAGE_STATE"] = saved
        if not _probe_rest(session, base, probe_path):
            raise RuntimeError(f"UI 登录后探针仍失败: GET {probe_path}")

    hdr = session.headers.get("Authorization") or ""
    token = hdr.replace("Bearer ", "", 1).strip()
    session.close()
    if not token:
        raise RuntimeError("UI 登录未捕获 Authorization")
    tenant = str(auth.get("tenant_id") or os.environ.get("PERF_TENANT_ID", "1"))
    return token, tenant


def fetch_token(base_url: str, auth: dict) -> tuple[str, str]:
    probe_path = str(auth.get("probe_path") or "/api/health")
    auth_type = str(auth.get("type") or "bearer_login")
    if auth_type in ("ui_storage_login", "ui_storage_login"):
        return fetch_token_ui(base_url, auth, probe_path)
    return fetch_token_rest(base_url, auth, probe_path)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base-url", default=os.environ.get("TEST_BASE_URL", "http://your-server:5001"))
    ap.add_argument(
        "--auth-profile",
        type=Path,
        default=ROOT / "templates/auth_profiles/generic_rest.yaml",
    )
    ap.add_argument("--probe-path", help="覆盖 profile 中的 probe_path")
    ap.add_argument("-o", "--output-env", type=Path, help="写入 KEY=VALUE（供 run_perf 脚本）")
    ap.add_argument("--json", action="store_true")
    ns = ap.parse_args()

    profile_path = ns.auth_profile if ns.auth_profile.is_absolute() else ROOT / ns.auth_profile
    auth = load_auth_profile(profile_path)
    if ns.probe_path:
        auth["probe_path"] = ns.probe_path

    token, tenant = fetch_token(ns.base_url, auth)

    if ns.output_env:
        out = ns.output_env if ns.output_env.is_absolute() else ROOT / ns.output_env
        out.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            f"PERF_ACCESS_TOKEN={token}",
            f"PERF_TENANT_ID={tenant}",
            f"PERF_ACCESS_TOKEN={token}",
            f"PERF_TENANT_ID={tenant}",
            f"TEST_BASE_URL={ns.base_url.rstrip('/')}",
        ]
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"已写入: {out.resolve()}", file=sys.stderr)

    if ns.json:
        print(json.dumps({"access_token": token, "tenant_id": tenant, "base_url": ns.base_url}, ensure_ascii=False))
    else:
        print(token)
    return 0


if __name__ == "__main__":
    sys.exit(main())
