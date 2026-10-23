#!/usr/bin/env python3
"""
将「评审用例 JSON」中带 automation 块的部分，合并为 api_pytest 的 spec Markdown，
再交给 ./generate.sh 生成 pytest。

用法:
  python3 codegen/testcase_to_api_spec.py -i examples/cases_with_automation.json \\
      -o templates/from_cases_demo.md --base-url http://your-server:5000
  export TEST_USERNAME=admin TEST_PASSWORD=admin123
  ./generate.sh templates/from_cases_demo.md

输入支持两种顶层形状:

1) JSON 数组: 与原先一致，每项为 API 形状或带 automation 的 test_case 形状。

2) JSON 对象: 须含 \"cases\" 数组；可选 \"base_url\"、\"auth\"（如 bearer_login）、
   \"session_headers\"、\"default_headers\"、\"timeout_default\"（与 templates 里 YAML 顶层一致）。
   用于「管理员登录后再拉采购列表」等场景。

无 automation 且非 api 形状的条目在非 --strict 下会跳过并在 stderr 打警告。
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

# 写入 spec YAML cases 时允许的键（与 run_spec emit_case 对齐）
API_CASE_KEYS = frozenset(
    {
        "id",
        "name",
        "method",
        "path",
        "expect_status",
        "accept_status",
        "params",
        "query",
        "json_body",
        "headers",
        "timeout",
        "no_auth",
        "save_token",
        "expect_body_substrings",
        "expect_json_subset",
        "layer",
        "priority",
        "review_required",
        "skip",
        "skip_reason",
    }
)

# 顶层除 cases 外可透传到 spec meta（与 parse_frontmatter 后 meta 对齐）
META_EXTRA_KEYS = frozenset(
    {
        "auth",
        "session_headers",
        "default_headers",
        "timeout_default",
        "setup",
        "scenarios",
    }
)


def _is_api_shape(obj: dict[str, Any]) -> bool:
    return isinstance(obj.get("method"), str) and isinstance(obj.get("path"), str)


def _has_automation(obj: dict[str, Any]) -> bool:
    a = obj.get("automation")
    return isinstance(a, dict) and isinstance(a.get("method"), str) and isinstance(a.get("path"), str)


def _slug_id(name: str, idx: int) -> str:
    s = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "-", name.strip())[:48].strip("-")
    if not s:
        s = "case"
    return f"TC-AUTO-{idx:03d}-{s}"


def merge_to_api_cases(items: list[Any], *, strict: bool) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    skipped: list[str] = []
    for i, raw in enumerate(items):
        if not isinstance(raw, dict):
            skipped.append(f"[{i}] 非对象，已跳过")
            continue
        if _is_api_shape(raw):
            case = {k: raw[k] for k in API_CASE_KEYS if k in raw}
            if "id" not in case:
                case["id"] = _slug_id(str(case.get("name") or "api"), len(out) + 1)
            out.append(case)
            continue
        if _has_automation(raw):
            auto = raw["automation"]
            assert isinstance(auto, dict)
            case = {k: auto[k] for k in API_CASE_KEYS if k in auto}
            for k in ("layer", "priority", "review_required", "skip", "skip_reason"):
                if k not in case and k in raw:
                    case[k] = raw[k]
            if "id" not in case:
                case["id"] = _slug_id(str(raw.get("name") or "case"), len(out) + 1)
            if "name" not in case and isinstance(raw.get("name"), str):
                case["name"] = raw["name"]
            out.append(case)
            continue
        label = raw.get("name") or raw.get("id") or f"#{i}"
        skipped.append(f"[{i}] {label!r} 无 method+path 且无 automation，已跳过")
    if skipped and strict:
        for m in skipped:
            print(m, file=sys.stderr)
        raise SystemExit("strict 模式：存在无法转换的条目")
    for m in skipped:
        print(m, file=sys.stderr)
    return out


def build_markdown(meta_inner: dict[str, Any], title: str) -> str:
    payload: dict[str, Any] = {"kind": "api_pytest", **meta_inner}
    payload["kind"] = "api_pytest"
    fm = yaml.safe_dump(
        payload,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    ).rstrip()
    body = (
        f"\n# {title}\n\n"
        "由 `codegen/testcase_to_api_spec.py` 从用例 JSON 生成。"
        " 下一步: `./generate.sh` 指向本文件。\n"
    )
    return f"---\n{fm}\n---{body}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-i", "--input", type=Path, required=True, help="用例 JSON 文件路径")
    ap.add_argument("-o", "--output", type=Path, help="输出 .md 路径；省略则打印到 stdout")
    ap.add_argument("--base-url", default="http://your-server:5000", help="未在 JSON 对象中写 base_url 时的默认值")
    ap.add_argument("--title", default="从用例合并的 API spec", help="Markdown 正文标题")
    ap.add_argument("--strict", action="store_true", help="任一条目无法转换则退出码 1")
    ns = ap.parse_args()

    repo_root = Path(__file__).resolve().parent.parent

    def _abs(p: Path) -> Path:
        return p if p.is_absolute() else (repo_root / p).resolve()

    inp = _abs(ns.input)
    out = _abs(ns.output) if ns.output else None

    data = json.loads(inp.read_text(encoding="utf-8"))

    if isinstance(data, dict) and isinstance(data.get("cases"), list):
        cases = merge_to_api_cases(data["cases"], strict=ns.strict)
        meta_inner: dict[str, Any] = {"cases": cases}
        for k in META_EXTRA_KEYS:
            if k in data and data[k] is not None:
                meta_inner[k] = data[k]
        bu = data.get("base_url")
        if isinstance(bu, str) and bu.strip():
            meta_inner["base_url"] = bu.strip().rstrip("/")
        else:
            meta_inner["base_url"] = ns.base_url.rstrip("/")
    elif isinstance(data, list):
        cases = merge_to_api_cases(data, strict=ns.strict)
        meta_inner = {"base_url": ns.base_url.rstrip("/"), "cases": cases}
    else:
        print(
            "输入须为 JSON 数组，或含 \"cases\" 数组的对象（可含 auth、base_url）",
            file=sys.stderr,
        )
        sys.exit(1)

    if not meta_inner.get("cases"):
        print("没有可写入的 API 用例（请为条目补充 method+path 或 automation 块）", file=sys.stderr)
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
