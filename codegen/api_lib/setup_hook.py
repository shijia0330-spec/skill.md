"""API pytest session 铺底：test_init / data_factory。"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import requests


def _engine_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_api_setup(meta: dict[str, Any]) -> dict[str, Any]:
    """从 api_pytest spec meta 解析 setup 配置。"""
    raw = meta.get("setup")
    if raw is None:
        return {"kind": "test_init", "path": "/api/test/init"}
    if isinstance(raw, str):
        s = raw.strip().lower()
        if s == "none":
            return {"kind": "none"}
        if s in ("test_init", "init"):
            out: dict[str, Any] = {"kind": "test_init", "path": "/api/test/init"}
            if isinstance(meta.get("setup_path"), str):
                out["path"] = meta["setup_path"]
            if meta.get("setup_json_body") is not None:
                out["json_body"] = meta["setup_json_body"]
            return out
        raise ValueError(f"未知 setup 字符串: {raw!r}")
    if isinstance(raw, dict):
        kind = str(raw.get("kind") or "test_init").strip().lower()
        if kind == "none":
            return {"kind": "none"}
        if kind == "data_factory":
            return dict(raw)
        if kind in ("test_init", "init"):
            return {
                "kind": "test_init",
                "path": raw.get("path") or "/api/test/init",
                "json_body": raw.get("json_body"),
                "timeout": raw.get("timeout"),
            }
        raise ValueError(f"未知 setup.kind: {kind!r}")
    raise ValueError("setup 须为 none / test_init 字符串或 YAML 对象")


def _resolve_script_path(script: str | Path) -> Path:
    p = Path(script)
    if p.is_file():
        return p.resolve()
    root = _engine_root()
    cand = root / script
    if cand.is_file():
        return cand.resolve()
    raise FileNotFoundError(f"setup 脚本不存在: {script}")


def run_python_setup_script(script: str | Path) -> None:
    path = _resolve_script_path(script)
    subprocess.run(
        [sys.executable, str(path)],
        check=True,
        cwd=str(_engine_root()),
    )


def run_api_setup(base_url: str, setup_cfg: dict[str, Any] | None) -> None:
    """执行 session 铺底；TEST_SETUP=none 时跳过。"""
    if os.environ.get("TEST_SETUP", "").strip().lower() == "none":
        return

    cfg = setup_cfg or {"kind": "test_init", "path": "/api/test/init"}
    kind = str(cfg.get("kind") or "test_init").strip().lower()
    if kind == "none":
        return

    from .allure_helper import attach_json, attach_text, report_step

    if kind == "test_init":
        with report_step("Step 1 · 环境铺底 (test_init)"):
            path = os.environ.get("TEST_INIT_PATH") or cfg.get("path") or "/api/test/init"
            if not str(path).startswith("/"):
                path = "/" + str(path)
            body_raw = os.environ.get("TEST_INIT_BODY")
            if body_raw is not None and str(body_raw).strip() != "":
                body: Any = json.loads(body_raw)
            else:
                body = cfg.get("json_body")
            timeout = int(cfg.get("timeout") or 30)
            url = base_url.rstrip("/") + path
            attach_text("请求 URL", url)
            if body is not None:
                resp = requests.post(url, json=body, timeout=timeout)
            else:
                resp = requests.post(url, timeout=timeout)
            resp.raise_for_status()
            attach_text("响应", resp.text[:4000])
        return

    if kind == "data_factory":
        spec = cfg.get("spec")
        script = cfg.get("script")
        label = str(script or spec or "data_factory")
        with report_step("Step 1 · 测试数据铺底"):
            with report_step(f"执行: {label}"):
                if spec:
                    from .data_factory_hook import run_data_factory_spec

                    run_data_factory_spec(str(spec))
                elif script:
                    run_python_setup_script(str(script))
                else:
                    raise ValueError("setup.data_factory 需要 spec（.md）或 script（.py）")
            root = _engine_root()
            for seed_base in ("test_seed",):
                seed_json = root / "output" / f"{seed_base}.json"
                seed_env = root / "output" / f"{seed_base}.env"
                if seed_env.is_file():
                    _load_seed_env_file(seed_env)
                if seed_json.is_file():
                    attach_json(f"seed 记录 ({seed_base}.json)", json.loads(seed_json.read_text(encoding="utf-8")))
                if seed_env.is_file():
                    attach_text(f"seed 环境变量 ({seed_base}.env)", seed_env.read_text(encoding="utf-8"))
                if seed_json.is_file() or seed_env.is_file():
                    break
        return

    raise ValueError(f"未知 setup kind: {kind!r}")


def _load_seed_env_file(path: Path) -> None:
    """铺底脚本写入的 KEY=VALUE 行注入 os.environ（不覆盖已有）。"""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip()
        if key:
            os.environ[key] = val
