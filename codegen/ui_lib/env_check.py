"""脚本校验与环境修复提示。"""
from __future__ import annotations

import ast
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


def validate_script(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    result: dict[str, Any] = {"path": str(p), "ok": True, "checks": []}

    def _add(name: str, ok: bool, detail: str = "") -> None:
        result["checks"].append({"name": name, "ok": ok, "detail": detail})
        if not ok:
            result["ok"] = False

    if not p.is_file():
        _add("file_exists", False, "文件不存在")
        return result

    src = p.read_text(encoding="utf-8")
    try:
        ast.parse(src)
        _add("syntax", True)
    except SyntaxError as e:
        _add("syntax", False, str(e))

    if "from ui_lib import" in src or "import ui_lib" in src:
        _add("ui_lib_import", True)
    else:
        _add("ui_lib_import", True, "optional")

    return result


def repair_deps_hints() -> list[str]:
    hints = [
        "pip install pytest pytest-playwright PyYAML requests",
        "playwright install chromium",
    ]
    if shutil.which("playwright") is None:
        hints.append("python -m playwright install chromium")
    return hints


def run_repair_deps(*, install: bool = False) -> dict[str, Any]:
    cmds = [
        [sys.executable, "-m", "pip", "install", "pytest", "pytest-playwright", "PyYAML", "requests"],
        [sys.executable, "-m", "playwright", "install", "chromium"],
    ]
    out: dict[str, Any] = {"install": install, "results": []}
    if not install:
        out["hints"] = repair_deps_hints()
        return out
    for cmd in cmds:
        r = subprocess.run(cmd, capture_output=True, text=True)
        out["results"].append({"cmd": cmd, "returncode": r.returncode, "stderr": (r.stderr or "")[-500:]})
    out["ok"] = all(x["returncode"] == 0 for x in out["results"])
    return out
