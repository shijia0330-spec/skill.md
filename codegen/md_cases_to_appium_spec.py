#!/usr/bin/env python3
"""
功能用例 Markdown → appium_pytest spec（规则映射一键流水线）。

Step 1  md_ui_filter.py           筛 A/B 档候选（与 UI 转化共用）
Step 2  md_to_ui_automation.py    候选 → ui_automation JSON
Step 3  testcase_to_appium_spec.py  JSON → appium spec（UI 步骤规则映射为 Appium）

用法:
  python3 codegen/md_cases_to_appium_spec.py \\
      -i output/seckill_ui_cases.md \\
      -o templates/seckill_appium_from_cases.md \\
      --module 秒杀 --tier A,B \\
      --app-package com.example.app --app-activity .MainActivity
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CODEGEN = Path(__file__).resolve().parent


def _resolve(p: Path) -> Path:
    return p if p.is_absolute() else (ROOT / p).resolve()


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, cwd=str(ROOT), check=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-i", "--input", type=Path, required=True, help="功能用例 .md 或 md_ui_filter 候选 JSON")
    ap.add_argument("-o", "--output", type=Path, required=True, help="输出 appium spec .md")
    ap.add_argument("--skip-filter", action="store_true")
    ap.add_argument("--base-url", default="http://your-server:5173")
    ap.add_argument("--tier", default="A,B", help="筛选档位，逗号分隔")
    ap.add_argument("--priority", default="P0,P1")
    ap.add_argument("--module", default="")
    ap.add_argument("--app-package", default="")
    ap.add_argument("--app-activity", default="")
    ap.add_argument("--title", default="")
    ns = ap.parse_args()

    inp = _resolve(ns.input)
    out = _resolve(ns.output)
    title = ns.title or f"从功能用例生成的 Appium spec · {out.stem}"

    work = ROOT / "output" / "_pipeline"
    work.mkdir(parents=True, exist_ok=True)
    stem = inp.stem.replace("_testcases", "").replace("_ui_candidates", "")
    candidates = work / f"{stem}_ui_candidates.json"
    automation = work / f"{stem}_ui_automation.json"

    if ns.skip_filter or inp.suffix.lower() == ".json":
        if inp.suffix.lower() != ".json":
            print("skip-filter 需要 .json 输入", file=sys.stderr)
            return 1
        automation = inp
    else:
        if not inp.is_file():
            print(f"输入不存在: {inp}", file=sys.stderr)
            return 1
        cmd = [
            sys.executable,
            str(CODEGEN / "md_ui_filter.py"),
            "-i",
            str(inp),
            "-o",
            str(candidates),
            "--summary",
            "--tier",
            ns.tier,
            "--priority",
            ns.priority,
        ]
        if ns.module:
            cmd.extend(["--module", ns.module])
        _run(cmd)
        _run(
            [
                sys.executable,
                str(CODEGEN / "md_to_ui_automation.py"),
                "-i",
                str(candidates),
                "-o",
                str(automation),
                "--base-url",
                ns.base_url,
                "--tier",
                ns.tier,
            ]
        )

    spec_cmd = [
        sys.executable,
        str(CODEGEN / "testcase_to_appium_spec.py"),
        "-i",
        str(automation),
        "-o",
        str(out),
        "--base-url",
        ns.base_url,
        "--title",
        title,
    ]
    if ns.app_package:
        spec_cmd.extend(["--app-package", ns.app_package])
    if ns.app_activity:
        spec_cmd.extend(["--app-activity", ns.app_activity])
    _run(spec_cmd)

    text = out.read_text(encoding="utf-8")
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    if "---" in text:
        parts = text.split("---", 2)
        if len(parts) >= 3:
            note = (
                f"\n> 由 `md_cases_to_appium_spec.py` 于 {stamp} 自动生成（规则映射，需人工校准定位器）\n"
                f"> 源用例：`{inp.name}`\n"
            )
            out.write_text(f"---{parts[1]}---{parts[2].rstrip()}{note}\n", encoding="utf-8")

    print(
        f"流水线完成:\n"
        f"  spec: {out}\n"
        f"  下一步: ./generate.sh {out.relative_to(ROOT)} --env appium\n"
        f"          ./run_appium.sh output/{out.stem}.py",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
