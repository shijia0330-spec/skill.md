#!/usr/bin/env python3
"""
将「评审用例 JSON」中带 ui_automation 块的部分，合并为 ui_pytest_playwright 的 spec Markdown，
再交给 ./generate.sh 生成 pytest-playwright。

用法:
  python codegen/testcase_to_ui_spec.py -i examples/cases_with_ui_automation.json \\
      -o templates/from_ui_cases_demo.md --base-url http://your-server:5001
  ./generate.sh templates/from_ui_cases_demo.md

输入支持两种顶层形状:

1) JSON 数组: 每项为 UI flow 形状或带 ui_automation 的 test_case 形状。

2) JSON 对象: 须含 \"cases\" 数组；可选 \"base_url\"、\"viewport\"、\"flows\"、\"scenarios\"
   （与 templates 里 YAML 顶层一致）。cases 中带 ui_automation 的条目会合并进 flows。
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

UI_STEP_KEYS = frozenset(
    {
        "action",
        "path",
        "value",
        "wait_until",
        "l1_test_id",
        "l1_label",
        "l1_placeholder",
        "l1_role",
        "l1_name",
        "l1_name_regex",
        "l2_css",
        "key",
        "ms",
        "capture",
        "from",
        "attr",
        "pattern",
        "group",
        "wait_until",
        "state",
        "timeout_ms",
        "url_regex",
        "file",
        "frame",
        "frame_selector",
    }
)

UI_EXPECT_KEYS = frozenset({"type", "text", "pattern", "exact"})

UI_FLOW_KEYS = frozenset(
    {
        "name",
        "steps",
        "expect",
        "parametrize",
    }
)

META_EXTRA_KEYS = frozenset({"viewport", "storage_state", "setup", "batch"})


def _is_ui_flow_shape(obj: dict[str, Any]) -> bool:
    return isinstance(obj.get("steps"), list) and bool(obj["steps"])


def _has_ui_automation(obj: dict[str, Any]) -> bool:
    u = obj.get("ui_automation")
    return isinstance(u, dict) and isinstance(u.get("steps"), list) and bool(u["steps"])


def _slug_name(name: str, idx: int) -> str:
    s = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "-", name.strip())[:48].strip("-")
    if not s:
        s = f"flow-{idx}"
    return s


def _pick_keys(src: dict[str, Any], allowed: frozenset[str]) -> dict[str, Any]:
    return {k: src[k] for k in allowed if k in src}


def merge_to_ui_flows(items: list[Any], *, strict: bool) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    skipped: list[str] = []
    for i, raw in enumerate(items):
        if not isinstance(raw, dict):
            skipped.append(f"[{i}] 非对象，已跳过")
            continue
        if _is_ui_flow_shape(raw):
            flow = _pick_keys(raw, UI_FLOW_KEYS)
            if "name" not in flow:
                flow["name"] = _slug_name(str(raw.get("name") or f"flow-{len(out)+1}"), len(out) + 1)
            out.append(flow)
            continue
        if _has_ui_automation(raw):
            auto = raw["ui_automation"]
            assert isinstance(auto, dict)
            flow = _pick_keys(auto, UI_FLOW_KEYS)
            if "name" not in flow:
                flow["name"] = _slug_name(str(raw.get("name") or "case"), len(out) + 1)
            out.append(flow)
            continue
        label = raw.get("name") or raw.get("id") or f"#{i}"
        skipped.append(f"[{i}] {label!r} 无 steps 且无 ui_automation，已跳过")
    if skipped and strict:
        for m in skipped:
            print(m, file=sys.stderr)
        raise SystemExit("strict 模式：存在无法转换的条目")
    for m in skipped:
        print(m, file=sys.stderr)
    return out


def build_markdown(meta_inner: dict[str, Any], title: str) -> str:
    payload: dict[str, Any] = {"kind": "ui_pytest_playwright", **meta_inner}
    payload["kind"] = "ui_pytest_playwright"
    fm = yaml.safe_dump(
        payload,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    ).rstrip()
    body = (
        f"\n# {title}\n\n"
        "由 `codegen/testcase_to_ui_spec.py` 从用例 JSON 生成。"
        " 下一步: `./generate.sh` 指向本文件。\n"
    )
    return f"---\n{fm}\n---{body}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-i", "--input", type=Path, required=True, help="用例 JSON 文件路径")
    ap.add_argument("-o", "--output", type=Path, help="输出 .md 路径；省略则打印到 stdout")
    ap.add_argument("--base-url", default="http://your-server:5001", help="未在 JSON 中写 base_url 时的默认值")
    ap.add_argument("--title", default="从用例合并的 UI spec", help="Markdown 正文标题")
    ap.add_argument("--strict", action="store_true", help="任一条目无法转换则退出码 1")
    ns = ap.parse_args()

    repo_root = Path(__file__).resolve().parent.parent

    def _abs(p: Path) -> Path:
        return p if p.is_absolute() else (repo_root / p).resolve()

    inp = _abs(ns.input)
    out = _abs(ns.output) if ns.output else None

    data = json.loads(inp.read_text(encoding="utf-8"))

    meta_inner: dict[str, Any] = {}

    if isinstance(data, dict):
        if isinstance(data.get("flows"), list):
            meta_inner["flows"] = [f for f in data["flows"] if isinstance(f, dict)]
        if isinstance(data.get("scenarios"), list):
            meta_inner["scenarios"] = [f for f in data["scenarios"] if isinstance(f, dict)]
        cases_raw = data.get("cases") if isinstance(data.get("cases"), list) else []
        merged = merge_to_ui_flows(cases_raw, strict=ns.strict)
        if merged:
            existing = list(meta_inner.get("flows") or [])
            meta_inner["flows"] = existing + merged
        for k in META_EXTRA_KEYS:
            if k in data and data[k] is not None:
                meta_inner[k] = data[k]
        bu = data.get("base_url")
        if isinstance(bu, str) and bu.strip():
            meta_inner["base_url"] = bu.strip().rstrip("/")
        else:
            meta_inner["base_url"] = ns.base_url.rstrip("/")
    elif isinstance(data, list):
        flows = merge_to_ui_flows(data, strict=ns.strict)
        meta_inner = {"base_url": ns.base_url.rstrip("/"), "flows": flows}
    else:
        print('输入须为 JSON 数组，或含 "cases"/"flows" 的对象', file=sys.stderr)
        sys.exit(1)

    if not meta_inner.get("flows") and not meta_inner.get("scenarios") and not meta_inner.get("steps"):
        print("没有可写入的 UI flow（请为条目补充 steps 或 ui_automation 块）", file=sys.stderr)
        sys.exit(1)

    md = build_markdown(meta_inner, ns.title)
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md, encoding="utf-8")
        print(f"已写入: {out.resolve()}", file=sys.stderr)
    else:
        sys.stdout.write(md)


if __name__ == "__main__":
    main()
