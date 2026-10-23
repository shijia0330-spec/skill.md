#!/usr/bin/env python3
"""
功能用例 Markdown → ui_pytest_playwright spec（一键流水线）。

Step 1  md_ui_filter.py      筛 A/B 档候选
Step 2  md_to_ui_automation.py  候选 → ui_automation JSON
Step 3  testcase_to_ui_spec.py    JSON → templates/*.md

用法:
  python codegen/md_cases_to_ui_spec.py \\
      -i examples/output_seckill_auth_testcases.md \\
      -o templates/seckill_ui_from_cases.md \\
      --module 秒杀 --tier A,B

  # 已有候选 JSON 时跳过 Step 1
  python codegen/md_cases_to_ui_spec.py \\
      -i output/_pipeline/seckill_ui_candidates.json \\
      -o templates/seckill_ui_from_cases.md \\
      --skip-filter
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
CODEGEN = Path(__file__).resolve().parent

# 秒杀财务 spec 正文环境变量块
SECKILL_ENV_DOC = """
**账号**：`admin / admin123`（秒杀财务系统）

**测试数据铺底**：`POST /api/test/init`（API 默认 `http://your-server:5001`）

| 变量 | 说明 |
|------|------|
| `SECKILL_SEARCH_NAME` | 商品列表搜索 |
| `SECKILL_DUPLICATE_USERNAME` | 重复注册（默认 admin） |

**环境变量**（PowerShell 示例）：

```powershell
$env:TEST_BASE_URL = "http://your-server:5173"
$env:TEST_USERNAME = "admin"
$env:TEST_PASSWORD = "admin123"
$ts = Get-Date -Format 'yyyyMMddHHmmss'
$env:TEST_UNIQUE_ID = "skills-demo-$ts"
$env:SECKILL_PRODUCT_NAME = "秒杀演示商品"
$env:UI_STORAGE_STATE = "output/.auth/ui_storage.json"
```

**生成与执行**：

```powershell
python codegen/run_spec.py {spec_path} -o output/{out_stem}.py
python -m pytest output/{out_stem}.py -v --headed -s
```

报告：`output/allure-report-ui/standalone.html`
"""


def _resolve(p: Path) -> Path:
    return p if p.is_absolute() else (ROOT / p).resolve()


def _run_filter(
    md_path: Path,
    candidates_path: Path,
    *,
    base_url: str,
    tier: str,
    priority: str,
    module: str,
    manifest: Path | None,
    specs_json: Path | None,
    screenshots_dir: Path | None,
) -> None:
    cmd = [
        sys.executable,
        str(CODEGEN / "md_ui_filter.py"),
        "-i",
        str(md_path),
        "-o",
        str(candidates_path),
        "--summary",
    ]
    if tier:
        cmd.extend(["--tier", tier])
    if priority:
        cmd.extend(["--priority", priority])
    if module:
        cmd.extend(["--module", module])
    if manifest:
        cmd.extend(["--manifest", str(manifest)])
    if specs_json:
        cmd.extend(["--specs-json", str(specs_json)])
    if screenshots_dir:
        cmd.extend(["--screenshots-dir", str(screenshots_dir)])
    subprocess.run(cmd, cwd=str(ROOT), check=True)


def _run_automation(
    candidates_path: Path,
    automation_path: Path,
    *,
    base_url: str,
    storage_state: str,
    tier: str,
) -> None:
    cmd = [
        sys.executable,
        str(CODEGEN / "md_to_ui_automation.py"),
        "-i",
        str(candidates_path),
        "-o",
        str(automation_path),
        "--base-url",
        base_url,
        "--storage-state",
        storage_state,
        "--strict",
    ]
    if tier:
        cmd.extend(["--tier", tier])
    subprocess.run(cmd, cwd=str(ROOT), check=True)


def _run_spec(
    automation_path: Path,
    spec_path: Path,
    *,
    base_url: str,
    title: str,
) -> None:
    cmd = [
        sys.executable,
        str(CODEGEN / "testcase_to_ui_spec.py"),
        "-i",
        str(automation_path),
        "-o",
        str(spec_path),
        "--base-url",
        base_url,
        "--title",
        title,
    ]
    subprocess.run(cmd, cwd=str(ROOT), check=True)


def _enrich_spec_body(spec_path: Path, *, source_md: Path, case_ids: list[str]) -> None:
    text = spec_path.read_text(encoding="utf-8")
    if "---" not in text:
        return
    parts = text.split("---", 2)
    if len(parts) < 3:
        return
    fm, body = parts[0], parts[2]
    stem = spec_path.stem
    extra = SECKILL_ENV_DOC.format(spec_path=f"templates/{spec_path.name}", out_stem=stem)
    new_body = (
        f"\n# {body.strip().split(chr(10), 1)[0].lstrip('#').strip() or spec_path.stem}\n\n"
        f"> 由 `md_cases_to_ui_spec.py` 于 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} 自动生成\n"
        f"> 源用例：`{source_md.name}` · {', '.join(case_ids)}\n"
        f"{extra}\n"
    )
    spec_path.write_text(f"---{parts[1]}---{new_body}", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-i", "--input", type=Path, required=True, help="功能用例 .md 或 md_ui_filter 候选 JSON")
    ap.add_argument("-o", "--output", type=Path, required=True, help="输出 spec .md 路径")
    ap.add_argument("--skip-filter", action="store_true", help="输入已是候选 JSON，跳过 md_ui_filter")
    ap.add_argument("--base-url", default="http://your-server:5001")
    ap.add_argument("--storage-state", default="output/.auth/ui_storage.json")
    ap.add_argument(
        "--tier",
        default="A,B,C",
        help="筛选+转化档位（逗号分隔）；严 A,B · 默认 A,B,C（模块冒烟 8 条）",
    )
    ap.add_argument("--priority", default="P0,P1", help="优先级过滤")
    ap.add_argument("--module", default="", help="模块关键词，逗号分隔")
    ap.add_argument("--title", default="", help="spec 标题")
    ap.add_argument("--manifest", type=Path, help="截图 manifest.json")
    ap.add_argument("--specs-json", type=Path, help="ui_cases_by_image.json")
    ap.add_argument("--screenshots-dir", type=Path, help="PNG 目录")
    ap.add_argument("--keep-intermediate", action="store_true", help="保留 output/*_candidates.json 等中间文件")
    ns = ap.parse_args()

    inp = _resolve(ns.input)
    out = _resolve(ns.output)
    title = ns.title or f"从功能用例生成的 UI spec · {out.stem}"

    work_dir = ROOT / "output" / "_pipeline"
    work_dir.mkdir(parents=True, exist_ok=True)
    stem = inp.stem.replace("_testcases", "").replace("_ui_candidates", "")
    candidates_path = work_dir / f"{stem}_ui_candidates.json"
    automation_path = work_dir / f"{stem}_ui_automation.json"

    source_md = inp
    if ns.skip_filter or inp.suffix.lower() == ".json":
        if inp.suffix.lower() == ".json":
            candidates_path = inp
        else:
            print("skip-filter 需要 .json 输入", file=sys.stderr)
            return 1
    else:
        if not inp.is_file():
            print(f"输入不存在: {inp}", file=sys.stderr)
            return 1
        _run_filter(
            inp,
            candidates_path,
            base_url=ns.base_url,
            tier=ns.tier,
            priority=ns.priority,
            module=ns.module,
            manifest=_resolve(ns.manifest) if ns.manifest else None,
            specs_json=_resolve(ns.specs_json) if ns.specs_json else None,
            screenshots_dir=_resolve(ns.screenshots_dir) if ns.screenshots_dir else None,
        )

    _run_automation(
        candidates_path,
        automation_path,
        base_url=ns.base_url,
        storage_state=ns.storage_state,
        tier=ns.tier,
    )

    _run_spec(automation_path, out, base_url=ns.base_url, title=title)

    auto_data: dict[str, Any] = json.loads(automation_path.read_text(encoding="utf-8"))
    case_ids = [str(c.get("case_id") or c.get("id") or "") for c in auto_data.get("cases") or []]
    _enrich_spec_body(out, source_md=source_md if source_md.suffix == ".md" else inp, case_ids=case_ids)

    if not ns.keep_intermediate and not ns.skip_filter:
        pass  # 中间文件默认留在 output/_pipeline 便于排查

    print(
        f"流水线完成:\n"
        f"  候选: {candidates_path}\n"
        f"  ui_automation: {automation_path}\n"
        f"  spec: {out}\n"
        f"  下一步: python codegen/run_spec.py {out.relative_to(ROOT)} -o output/{out.stem}.py",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
