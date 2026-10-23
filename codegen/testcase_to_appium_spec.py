#!/usr/bin/env python3
"""
将 md_to_ui_automation 产出的 ui_automation JSON 转为 appium_pytest spec Markdown。

用法:
  python3 codegen/testcase_to_appium_spec.py \\
      -i output/_pipeline/seckill_ui_automation.json \\
      -o templates/seckill_appium_from_cases.md
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    print("需要 PyYAML: pip install PyYAML", file=sys.stderr)
    sys.exit(1)

from ui_automation_to_appium import convert_ui_flow

META_EXTRA_KEYS = frozenset({"setup", "driver_scope", "appium_server", "api_base_url"})


def _has_ui_automation(obj: dict[str, Any]) -> bool:
    u = obj.get("ui_automation")
    return isinstance(u, dict) and isinstance(u.get("steps"), list) and bool(u["steps"])


def _slug_name(name: str, idx: int) -> str:
    s = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "-", name.strip())[:48].strip("-")
    return s or f"flow-{idx}"


def merge_to_appium_flows(items: list[Any], *, strict: bool) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    skipped: list[str] = []
    for i, raw in enumerate(items):
        if not isinstance(raw, dict):
            skipped.append(f"[{i}] 非对象，已跳过")
            continue
        ui_flow: dict[str, Any] | None = None
        if isinstance(raw.get("steps"), list) and raw["steps"]:
            ui_flow = raw
        elif _has_ui_automation(raw):
            ui_flow = raw["ui_automation"]  # type: ignore[assignment]
            if "name" not in ui_flow:
                ui_flow["name"] = _slug_name(str(raw.get("name") or raw.get("case_id") or "case"), len(out) + 1)
        if ui_flow:
            converted = convert_ui_flow(ui_flow)
            if converted.get("steps"):
                out.append(converted)
            else:
                skipped.append(f"[{i}] {raw.get('name')!r} 无可用 Appium steps")
            continue
        label = raw.get("name") or raw.get("id") or f"#{i}"
        skipped.append(f"[{i}] {label!r} 无 ui_automation，已跳过")
    if skipped and strict:
        for m in skipped:
            print(m, file=sys.stderr)
        raise SystemExit("strict 模式：存在无法转换的条目")
    for m in skipped:
        print(m, file=sys.stderr)
    return out


def default_capabilities(app_package: str, app_activity: str) -> dict[str, Any]:
    caps: dict[str, Any] = {
        "platformName": "Android",
        "automationName": "UiAutomator2",
        "deviceName": "Android Emulator",
    }
    if app_package and app_activity:
        caps["appPackage"] = app_package
        caps["appActivity"] = app_activity
    return caps


def build_markdown(meta_inner: dict[str, Any], title: str) -> str:
    payload: dict[str, Any] = {"kind": "appium_pytest", **meta_inner}
    fm = yaml.safe_dump(
        payload,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    ).rstrip()
    body = (
        f"\n# {title}\n\n"
        "由 `codegen/testcase_to_appium_spec.py` 从 UI 自动化 JSON **规则映射**生成。"
        " 定位器为 accessibility_id 占位，请对照 `mobile_elements.json` 人工校准后 `./generate.sh`。\n"
    )
    return f"---\n{fm}\n---{body}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-i", "--input", type=Path, required=True)
    ap.add_argument("-o", "--output", type=Path, help="输出 .md；省略则 stdout")
    ap.add_argument("--base-url", default="http://your-server:5173")
    ap.add_argument("--app-package", default="", help="Android appPackage")
    ap.add_argument("--app-activity", default="", help="Android appActivity")
    ap.add_argument("--title", default="从功能用例生成的 Appium spec")
    ap.add_argument("--strict", action="store_true")
    ns = ap.parse_args()

    root = Path(__file__).resolve().parent.parent

    def _abs(p: Path) -> Path:
        return p if p.is_absolute() else (root / p).resolve()

    data = json.loads(_abs(ns.input).read_text(encoding="utf-8"))
    meta_inner: dict[str, Any] = {
        "base_url": ns.base_url.rstrip("/"),
        "driver_scope": "class",
        "setup": {"kind": "test_init"},
        "capabilities": default_capabilities(ns.app_package, ns.app_activity),
    }

    flows: list[dict[str, Any]] = []
    if isinstance(data, dict):
        if isinstance(data.get("flows"), list):
            flows.extend(merge_to_appium_flows(data["flows"], strict=ns.strict))
        cases_raw = data.get("cases") if isinstance(data.get("cases"), list) else []
        flows.extend(merge_to_appium_flows(cases_raw, strict=ns.strict))
        for k in META_EXTRA_KEYS:
            if k in data and data[k] is not None:
                meta_inner[k] = data[k]
    elif isinstance(data, list):
        flows = merge_to_appium_flows(data, strict=ns.strict)

    if not flows:
        print("未转换出任何 Appium flow", file=sys.stderr)
        return 1

    meta_inner["flows"] = flows
    md = build_markdown(meta_inner, ns.title)
    out = _abs(ns.output) if ns.output else None
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md, encoding="utf-8")
        print(f"已写入: {out}", file=sys.stderr)
    else:
        print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
