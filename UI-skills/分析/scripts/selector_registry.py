#!/usr/bin/env python3
"""
选择器注册表 — 跨文件共享 UI 定位器。

用途：
  所有测试文件从统一的 selectors.json 读取定位器，避免碎片化。
  DOM 扫描结果自动导入注册表。

用法:
  # 从 DOM 扫描结果导入
  python selector_registry.py import output/dom-scan/dom_login.json

  # 导出当前注册表
  python selector_registry.py export output/selectors.json

  # 查询选择器
  python selector_registry.py query loginPage username

  # 合并多个 DOM 扫描结果
  python selector_registry.py merge output/dom-scan/*.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REGISTRY_FILE = "output/selectors.json"


def load_registry(path: str | Path | None = None) -> dict:
    """加载选择器注册表。"""
    p = Path(path) if path else Path(REGISTRY_FILE)
    if p.is_file():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"version": 1, "pages": {}}


def save_registry(registry: dict, path: str | Path | None = None) -> None:
    """保存选择器注册表。"""
    p = Path(path) if path else Path(REGISTRY_FILE)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")


def import_dom_scan(dom_file: str | Path, registry_path: str | Path | None = None) -> dict:
    """从 DOM 扫描结果导入选择器注册表。"""
    registry = load_registry(registry_path)
    dom = json.loads(Path(dom_file).read_text(encoding="utf-8"))

    page_info = dom.get("page", {})
    page_name = page_info.get("title", Path(dom_file).stem)
    page_url = page_info.get("url", "")

    if page_name not in registry["pages"]:
        registry["pages"][page_name] = {
            "url": page_url,
            "elements": {},
        }

    page = registry["pages"][page_name]
    if page_url and not page["url"]:
        page["url"] = page_url

    for el in dom.get("elements", []):
        # 生成唯一 key
        testid = el.get("data-testid")
        elem_id = el.get("id")
        name_attr = el.get("name")
        placeholder = el.get("placeholder")
        role = el.get("role")
        text = el.get("text", "")[:50]

        # 优先使用最稳定的标识
        if testid:
            key = f"testid:{testid}"
        elif elem_id:
            key = f"id:{elem_id}"
        elif name_attr:
            key = f"name:{name_attr}"
        elif placeholder:
            key = f"placeholder:{placeholder}"
        elif role and text:
            key = f"role:{role}:text:{text}"
        else:
            continue

        # 生成定位器 hints
        hints = {}
        if testid:
            hints["testid"] = testid
        if role:
            hints["role"] = role
        if el.get("label"):
            hints["label"] = el["label"]
        if placeholder:
            hints["placeholder"] = placeholder
        if el.get("aria-label"):
            hints["aria_label"] = el["aria-label"]
        if el.get("css"):
            hints["css"] = el["css"]

        # 记录元素类型
        tag = el.get("tag", "")
        input_type = el.get("type")
        if tag == "input" and input_type:
            hints["type"] = input_type
        elif tag in ("button",):
            hints["type"] = "button"
        elif tag in ("input", "textarea"):
            hints["type"] = "input"
        elif tag == "select":
            hints["type"] = "select"

        page["elements"][key] = {
            "hints": hints,
            "tag": tag,
            "text": text,
            "disabled": el.get("disabled", False),
            "source": str(Path(dom_file).name),
        }

    save_registry(registry, registry_path)
    added = len(page["elements"])
    print(f"  已导入: {page_name} ({added} 个选择器)")
    return registry


def query_selector(page_name: str, element_key: str, registry_path: str | Path | None = None) -> dict | None:
    """查询选择器。"""
    registry = load_registry(registry_path)
    page = registry.get("pages", {}).get(page_name)
    if not page:
        print(f"  页面不存在: {page_name}")
        return None
    elem = page.get("elements", {}).get(element_key)
    if not elem:
        # 模糊匹配
        for key in page.get("elements", {}):
            if element_key.lower() in key.lower():
                print(f"  模糊匹配: {page_name} -> {key}")
                print(f"    {json.dumps(page['elements'][key], ensure_ascii=False, indent=2)}")
                return page["elements"][key]
        print(f"  元素不存在: {page_name}.{element_key}")
        return None
    print(f"  {page_name}.{element_key}")
    print(f"    {json.dumps(elem, ensure_ascii=False, indent=2)}")
    return elem


def list_pages(registry_path: str | Path | None = None) -> None:
    """列出所有页面。"""
    registry = load_registry(registry_path)
    pages = registry.get("pages", {})
    if not pages:
        print("  注册表为空")
        return
    print(f"  注册表: {len(pages)} 个页面")
    for name, page in pages.items():
        elem_count = len(page.get("elements", {}))
        url = page.get("url", "N/A")
        print(f"  {name}: {elem_count} 个选择器 ({url})")


def main():
    p = argparse.ArgumentParser(
        description="选择器注册表 — 跨文件共享 UI 定位器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = p.add_subparsers(dest="command")

    cmd_import = sub.add_parser("import", help="从 DOM 扫描结果导入")
    cmd_import.add_argument("dom_file", help="DOM 扫描 JSON 文件")
    cmd_import.add_argument("--registry", default=None, help="注册表文件路径")

    cmd_export = sub.add_parser("export", help="导出注册表")
    cmd_export.add_argument("--out", default=REGISTRY_FILE, help="输出路径")
    cmd_export.add_argument("--registry", default=None, help="注册表文件路径")

    cmd_query = sub.add_parser("query", help="查询选择器")
    cmd_query.add_argument("page", help="页面名")
    cmd_query.add_argument("element", help="元素 key")
    cmd_query.add_argument("--registry", default=None, help="注册表文件路径")

    cmd_list = sub.add_parser("list", help="列出所有页面")
    cmd_list.add_argument("--registry", default=None, help="注册表文件路径")

    cmd_merge = sub.add_parser("merge", help="合并多个 DOM 扫描结果")
    cmd_merge.add_argument("dom_files", nargs="+", help="DOM 扫描 JSON 文件列表")
    cmd_merge.add_argument("--registry", default=None, help="注册表文件路径")

    args = p.parse_args()

    if args.command == "import":
        import_dom_scan(args.dom_file, args.registry)
    elif args.command == "export":
        registry = load_registry(args.registry)
        save_registry(registry, args.out)
        print(f"  已导出: {args.out}")
    elif args.command == "query":
        query_selector(args.page, args.element, args.registry)
    elif args.command == "list":
        list_pages(args.registry)
    elif args.command == "merge":
        for f in args.dom_files:
            import_dom_scan(f, args.registry)
        print(f"  合并完成")
    else:
        p.print_help()


if __name__ == "__main__":
    main()
