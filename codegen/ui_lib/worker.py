"""子进程隔离执行 UI flow（JSON 配置进/结果出）。"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any


def _worker_script() -> Path:
    return Path(__file__).resolve().parent / "worker_main.py"


def run_flow_in_worker(
    steps: list[dict[str, Any]],
    *,
    expects: list[dict[str, Any]] | None = None,
    base_url: str,
    headless: bool = True,
    heal: bool = True,
    timeout_sec: int = 300,
) -> dict[str, Any]:
    job_id = uuid.uuid4().hex[:12]
    tmp = Path(tempfile.gettempdir()) / f"ui_worker_{job_id}"
    tmp.mkdir(parents=True, exist_ok=True)
    cfg_path = tmp / "config.json"
    res_path = tmp / "result.json"
    stop_path = tmp / "stop.flag"

    cfg = {
        "job_id": job_id,
        "steps": steps,
        "expects": expects or [],
        "base_url": base_url,
        "headless": headless,
        "heal": heal,
        "stop_path": str(stop_path),
    }
    cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

    codegen = Path(__file__).resolve().parents[1]
    root = codegen.parent
    proc = subprocess.run(
        [sys.executable, str(_worker_script()), str(cfg_path), str(res_path)],
        cwd=str(root),
        timeout=timeout_sec,
        capture_output=True,
        text=True,
    )

    if res_path.is_file():
        result = json.loads(res_path.read_text(encoding="utf-8"))
        result["worker_exit_code"] = proc.returncode
        if proc.stderr:
            result["worker_stderr"] = proc.stderr[-2000:]
        return result

    return {
        "success": False,
        "message": "worker 未产出 result.json",
        "worker_exit_code": proc.returncode,
        "worker_stdout": (proc.stdout or "")[-2000:],
        "worker_stderr": (proc.stderr or "")[-2000:],
        "steps_parsed": steps,
    }
