"""执行前环境检查（readiness / pretest）。"""
from __future__ import annotations

import shutil
import urllib.error
import urllib.request
from typing import Any


def check_readiness(base_url: str, *, timeout: float = 8.0) -> dict[str, Any]:
    result: dict[str, Any] = {"base_url": base_url, "ok": True, "checks": []}

    def _add(name: str, ok: bool, detail: str = "") -> None:
        result["checks"].append({"name": name, "ok": ok, "detail": detail})
        if not ok:
            result["ok"] = False

    try:
        req = urllib.request.Request(base_url.rstrip("/") + "/", method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            _add("base_url_reachable", resp.status < 500, f"status={resp.status}")
    except urllib.error.HTTPError as e:
        _add("base_url_reachable", e.code < 500, f"HTTP {e.code}")
    except Exception as e:
        _add("base_url_reachable", False, str(e))

    _add("playwright_cli", shutil.which("playwright") is not None or True, "optional")

    try:
        import playwright  # noqa: F401

        _add("playwright_python", True)
    except ImportError:
        _add("playwright_python", False, "pip install pytest-playwright")

    return result


def assert_readiness(base_url: str) -> None:
    report = check_readiness(base_url)
    if not report["ok"]:
        failed = [c for c in report["checks"] if not c["ok"]]
        raise RuntimeError(f"UI pretest 未通过: {failed}")
