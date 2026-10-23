#!/usr/bin/env python3
"""Appium 定位自愈 CLI — 离线解析 page_source 或说明用法。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3] / "codegen"
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from mobile_lib.locator_healer import (  # noqa: E402
    hints_from_primary,
    suggest_from_page_source,
)


def main() -> int:
    ap = argparse.ArgumentParser(description="Appium locator healer — 离线候选 / hint 预览")
    ap.add_argument("-i", "--input", help="page_source XML 文件")
    ap.add_argument("--by", default="css", help="主定位 by（与 spec 一致）")
    ap.add_argument("--locator", default='input[name="username"]', help="主定位值")
    ap.add_argument("--text-hint", default="", help="L3 文本过滤")
    ap.add_argument("-o", "--output", default="output/mobile_heal_candidates.json")
    args = ap.parse_args()

    hints = hints_from_primary(args.by, args.locator)
    result: dict = {"hints": hints.__dict__, "candidates": []}

    if args.input:
        src = Path(args.input)
        if not src.is_file():
            print(f"文件不存在: {src}", file=sys.stderr)
            return 1
        xml_text = src.read_text(encoding="utf-8", errors="replace")
        for by_key, loc in suggest_from_page_source(xml_text, text_hint=args.text_hint or hints.text):
            result["candidates"].append({"by": by_key, "locator": loc})
    else:
        print("未指定 -i：仅输出 hints；运行时自愈见 codegen/mobile_lib/locator_healer.py")
        print("环境变量: MOBILE_SELF_HEAL=1, MOBILE_HEAL_TIMEOUT_MS=800")

    dest = Path(args.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已写入 {dest}（{len(result['candidates'])} 个候选）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
