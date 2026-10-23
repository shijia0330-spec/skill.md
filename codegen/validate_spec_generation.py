"""关键模板 generate + pytest collect-only 验收（不访问网络）。"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODEGEN = ROOT / "codegen"
OUT = ROOT / "output"
RUN_SPEC = CODEGEN / "run_spec.py"

SPECS: list[tuple[str, str, str]] = [
    ("templates/api_smoke.md", "output/api_smoke.py", "pytest"),
    ("templates/api_chain_vars.md", "output/api_chain_vars.py", "pytest"),
    ("templates/data_factory.md", "output/data_factory.py", "script"),
    ("templates/ui_login.md", "output/ui_login.py", "pytest"),
    ("templates/perf_test.md", "output/perf_test.py", "locust"),
    ("templates/perf_test_k6.md", "output/perf_test_k6.js", "k6"),
    ("templates/jmeter_test.md", "output/jmeter_test.jmx", "jmeter"),
    ("templates/seckill_api_auth.md", "output/seckill_api_auth.py", "pytest"),
]


def main() -> int:
    errors: list[str] = []
    ok: list[str] = []

    for spec_rel, out_rel, kind in SPECS:
        spec = ROOT / spec_rel
        out = ROOT / out_rel
        if not spec.is_file():
            errors.append(f"缺少模板: {spec_rel}")
            continue
        r = subprocess.run(
            [sys.executable, str(RUN_SPEC), str(spec), "-o", str(out)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if r.returncode != 0:
            errors.append(f"生成失败 {spec_rel}: {(r.stderr or r.stdout)[-400:]}")
            continue
        if not out.is_file() or out.stat().st_size < 20:
            errors.append(f"产出为空: {out_rel}")
            continue
        ok.append(f"OK generate {spec_rel} -> {out_rel}")

        if kind == "pytest":
            pr = subprocess.run(
                [sys.executable, "-m", "pytest", str(out), "--collect-only", "-q"],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if pr.returncode != 0:
                errors.append(f"collect-only 失败 {out_rel}: {(pr.stderr or pr.stdout)[-400:]}")
            else:
                line = (pr.stdout or "").strip().splitlines()[-1] if pr.stdout else "?"
                ok.append(f"OK collect {out_rel}: {line}")

    print("=== codegen 验收 ===")
    for line in ok:
        print(line)
    if errors:
        print("\n失败:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"\n全部通过 ({len(SPECS)} 个模板)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
