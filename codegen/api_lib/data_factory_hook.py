"""执行 data_factory spec（批量/场景执行前造数）。"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _engine_root() -> Path:
    return Path(__file__).resolve().parents[2]


def run_data_factory_spec(spec_path: str | Path, *, out_name: str = "_batch_data_factory.py") -> None:
    """解析 data_factory spec → 生成脚本 → 执行。"""
    root = _engine_root()
    spec = Path(spec_path)
    if not spec.is_file():
        spec = root / spec_path
    if not spec.is_file():
        raise FileNotFoundError(f"data_factory spec 不存在: {spec_path}")

    run_spec = root / "codegen" / "run_spec.py"
    out = root / "output" / out_name
    out.parent.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        [sys.executable, str(run_spec), str(spec), "-o", str(out)],
        check=True,
        cwd=str(root),
    )
    subprocess.run([sys.executable, str(out)], check=True, cwd=str(root))
