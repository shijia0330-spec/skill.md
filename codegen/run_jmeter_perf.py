#!/usr/bin/env python3
"""运行 JMeter 压测：刷新 Token 后通过 -J 传入（Header 使用 ${__P(...)}）。"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = Path(os.environ.get("PERF_TOOLS_ROOT", r"C:\perf-tools"))
JMETER_JAR = TOOLS / "jmeter" / "bin" / "ApacheJMeter.jar"


def find_java() -> Path:
    java_root = TOOLS / "java"
    if java_root.is_dir():
        for p in java_root.rglob("java.exe"):
            if p.match("*/bin/java.exe"):
                return p
    return Path("java")


def refresh_token(env_out: Path) -> None:
    cmd = [
        sys.executable,
        str(ROOT / "codegen" / "fetch_perf_token.py"),
        "--output-env",
        str(env_out),
    ]
    subprocess.run(cmd, check=True, cwd=str(ROOT))


def load_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.lstrip().startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-t", "--jmx", type=Path, default=ROOT / "output" / "har_perf_jmeter.jmx")
    ap.add_argument("-l", "--jtl", type=Path, default=ROOT / "output" / "har_perf_jmeter_result.jtl")
    ap.add_argument("-o", "--report", type=Path, default=ROOT / "output" / "jmeter-report")
    ap.add_argument("--skip-token", action="store_true", help="不刷新 Token，使用已有 .perf_env")
    ns = ap.parse_args()

    env_file = ROOT / "output" / ".perf_env"
    if not ns.skip_token:
        refresh_token(env_file)
    env = load_env(env_file)
    token = env.get("PERF_ACCESS_TOKEN", "")
    tenant = env.get("PERF_TENANT_ID", "1")
    if not token:
        print("缺少 PERF_ACCESS_TOKEN", file=sys.stderr)
        return 1

    jmx = ns.jmx if ns.jmx.is_absolute() else ROOT / ns.jmx
    jtl = ns.jtl if ns.jtl.is_absolute() else ROOT / ns.jtl
    report = ns.report if ns.report.is_absolute() else ROOT / ns.report

    if report.exists():
        import shutil
        shutil.rmtree(report)
    if jtl.exists():
        jtl.unlink()

    java = find_java()
    cmd = [
        str(java), "-Xms256m", "-Xmx512m", "-jar", str(JMETER_JAR),
        "-n", "-t", str(jmx), "-l", str(jtl), "-e", "-o", str(report),
        f"-JPERF_ACCESS_TOKEN={token}",
        f"-JPERF_TENANT_ID={tenant}",
        f"-JPERF_ACCESS_TOKEN={token}",
        f"-JPERF_TENANT_ID={tenant}",
    ]
    run_env = os.environ.copy()
    run_env["JMETER_HOME"] = str(TOOLS / "jmeter")
    print(f"JMeter: {jmx.name}  token={token[:8]}...")
    return subprocess.run(cmd, env=run_env, cwd=str(ROOT)).returncode


if __name__ == "__main__":
    raise SystemExit(main())
