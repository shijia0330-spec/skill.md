#!/usr/bin/env python3
"""解析 Android uiautomator / Appium page_source XML，输出候选定位器 JSON。"""
from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def _attr(el: ET.Element, *names: str) -> str:
    for n in names:
        v = el.get(n)
        if v:
            return v.strip()
    return ""


def _suggest(el: ET.Element) -> tuple[str, str]:
    desc = _attr(el, "content-desc", "contentDescription")
    if desc:
        return "accessibility_id", desc
    rid = _attr(el, "resource-id", "resourceId")
    if rid:
        return "id", rid
    text = _attr(el, "text")
    if text:
        safe = text.replace('"', '\\"')[:40]
        return "android_uiautomator", f'new UiSelector().text("{safe}")'
    cls = _attr(el, "class")
    return "xpath", f"//{cls.split('.')[-1]}" if cls else "//*"


def parse_xml(path: Path) -> list[dict]:
    root = ET.parse(path).getroot()
    out: list[dict] = []
    for el in root.iter():
        clickable = _attr(el, "clickable", "focusable") in ("true", "True", "1")
        text = _attr(el, "text")
        desc = _attr(el, "content-desc", "contentDescription")
        rid = _attr(el, "resource-id", "resourceId")
        if not (clickable or text or desc or rid):
            continue
        by, loc = _suggest(el)
        out.append(
            {
                "tag": _attr(el, "class"),
                "text": text,
                "content_desc": desc,
                "resource_id": rid,
                "clickable": clickable,
                "suggested_by": by,
                "suggested_locator": loc,
            }
        )
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="page source XML → 元素 JSON")
    ap.add_argument("-i", "--input", required=True, help="window_dump.xml 或 page_source 文件")
    ap.add_argument("-o", "--output", default="output/mobile_elements.json")
    args = ap.parse_args()
    src = Path(args.input)
    if not src.is_file():
        print(f"文件不存在: {src}", file=sys.stderr)
        return 1
    elements = parse_xml(src)
    dest = Path(args.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps({"elements": elements}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已写入 {dest}（{len(elements)} 个候选元素）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
