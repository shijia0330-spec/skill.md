#!/usr/bin/env python3
"""
秒杀财务 Web 侧栏截图 — 自动遍历侧栏菜单 + 截取弹窗。
适用于有侧边栏导航的 SPA（Ant Design / Element Plus 等）。
也支持本地 HTML 文件模式。

用法 (URL 模式):
  # 首次手动登录
  python capture_web_sidebar.py \
    --base-url http://127.0.0.1:5173 \
    --start-menu 商品管理 \
    --manual-login --headed \
    --storage-state output/.auth/seckill_web_auth.json \
    --out-dir output/site-screenshots/seckill-web \
    --capture-dialogs

  # 后续复用登录态
  python capture_web_sidebar.py \
    --base-url http://127.0.0.1:5173 \
    --start-menu 商品管理 \
    --storage-state output/.auth/seckill_web_auth.json \
    --routes-file routes_seckill_core.txt \
    --out-dir output/site-screenshots/seckill-web \
    --capture-dialogs

用法 (本地 HTML 模式):
  python capture_web_sidebar.py \
    --local-dir /path/to/html-files \
    --out-dir output/site-screenshots/seckill-web \
    --routes-file local_routes.txt

依赖:
  pip install playwright
  playwright install chromium
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

try:
    from playwright.sync_api import sync_playwright, Page
except ImportError:
    print("请安装: pip install playwright && playwright install chromium")
    sys.exit(1)

# 默认截取的按钮文本
DEFAULT_CAPTURE_BUTTONS = [
    "新增", "新建", "创建", "编辑", "修改", "查看", "详情", "删除", "导出", "导入",
    "New", "Create", "Edit", "View", "Detail", "Delete", "Export", "Import", "Add",
]


def parse_args():
    p = argparse.ArgumentParser(
        description="秒杀财务 Web 侧栏截图 — 支持 URL 和本地 HTML",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--base-url", default=None, help="测试环境根地址（URL 模式）")
    p.add_argument("--local-dir", default=None, help="本地 HTML 文件目录（本地模式）")
    p.add_argument("--out-dir", default="output/site-screenshots/seckill-web")
    p.add_argument("--start-menu", default=None, help="侧栏起始菜单名")
    p.add_argument("--manual-login", action="store_true", help="手动登录模式")
    p.add_argument("--headed", action="store_true")
    p.add_argument("--storage-state", default=None)
    p.add_argument("--routes-file", default=None)
    p.add_argument("--viewport", default="1440x900")
    p.add_argument("--wait-ms", type=int, default=1500)
    p.add_argument("--capture-dialogs", action="store_true", default=True,
                   help="截取按钮弹窗（默认开启）")
    p.add_argument("--no-capture-dialogs", action="store_true", default=False,
                   help="关闭按钮弹窗截图")
    p.add_argument("--capture-buttons", default=None,
                   help="要截取的按钮（逗号分隔）")
    p.add_argument("--max-pages", type=int, default=200)
    return p.parse_args()


def resolve_args(args):
    """校验参数。"""
    if args.no_capture_dialogs:
        args.capture_dialogs = False

    if args.local_dir and args.base_url:
        print("错误: --local-dir 和 --base-url 不能同时使用")
        sys.exit(1)

    if not args.local_dir and not args.base_url:
        print("错误: 必须指定 --local-dir 或 --base-url")
        sys.exit(1)

    if args.local_dir:
        p = Path(args.local_dir)
        if not p.exists() or not p.is_dir():
            print(f"错误: 本地目录不存在: {args.local_dir}")
            sys.exit(1)

    if args.base_url:
        args.base_url = args.base_url.rstrip("/")

    if args.capture_buttons:
        args.capture_buttons = [b.strip() for b in args.capture_buttons.split(",") if b.strip()]
    else:
        args.capture_buttons = list(DEFAULT_CAPTURE_BUTTONS)

    return args


def load_routes(path: str | None) -> list[str]:
    """加载路由/文件清单。"""
    if not path:
        return []
    p = Path(path)
    if not p.exists():
        print(f"  警告: 路由文件不存在: {path}")
        return []
    routes = []
    with open(p, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                routes.append(line)
    return routes


def scan_local_html(local_dir: str) -> list[str]:
    """扫描目录下所有 .html / .htm 文件。"""
    d = Path(local_dir)
    files = []
    for ext in ("*.html", "*.htm"):
        files.extend(sorted(d.glob(ext)))
    return [f.name for f in files]


def extract_menu_items(page: Page) -> list[dict]:
    """提取侧栏菜单项（path + 文本）。"""
    return page.evaluate("""() => {
        const items = [];
        const selectors = [
            '.ant-menu-item a', '.el-menu-item a', '.sidebar-nav a',
            'aside nav a', '.layout-sider a[href]'
        ];
        for (const sel of selectors) {
            const els = document.querySelectorAll(sel);
            for (const el of els) {
                const href = el.getAttribute('href') || el.getAttribute('data-path') || '';
                const text = el.textContent?.trim() || el.getAttribute('aria-label') || '';
                if (href && text) {
                    items.push({path: href, text: text});
                }
            }
        }
        return items;
    }""")


def click_menu_and_wait(page: Page, menu_text: str, wait_ms: int = 1500) -> bool:
    """点击侧栏菜单项并等待页面加载。"""
    try:
        locators = [
            page.get_by_role("menuitem", name=menu_text),
            page.get_by_text(menu_text, exact=True),
            page.locator(f'a:has-text("{menu_text}")'),
        ]
        for loc in locators:
            try:
                if loc.first.is_visible():
                    loc.first.click()
                    page.wait_for_timeout(wait_ms)
                    page.wait_for_load_state("domcontentloaded")
                    return True
            except Exception:
                continue
    except Exception:
        pass
    return False


def capture_dialogs(page: Page, out_dir: Path, page_name: str, buttons: list[str], wait_ms: int = 800) -> list[dict]:
    """截取按钮触发的弹窗/抽屉区域。"""
    dialogs = []
    for btn_text in buttons:
        try:
            btn = page.get_by_role("button", name=re.compile(re.escape(btn_text), re.IGNORECASE)).first
            if not btn.is_visible():
                continue
            btn.click()
            page.wait_for_timeout(wait_ms)
            page.wait_for_load_state("domcontentloaded")

            dlg_selectors = [
                '[role="dialog"]', '.ant-modal-content', '.el-dialog__wrapper',
                '.el-dialog', '.modal-content', '[class*="Drawer"]',
                '[class*="modal"]', '.v-dialog',
            ]
            dlg_found = False
            for sel in dlg_selectors:
                try:
                    dlg = page.locator(sel).first
                    if dlg.is_visible():
                        dlg_path = out_dir / f"{page_name}_dialog_{btn_text}.png"
                        dlg.screenshot(path=str(dlg_path))
                        dialogs.append({
                            "button": btn_text,
                            "screenshot": str(dlg_path.relative_to(out_dir.parent)),
                        })
                        dlg_found = True
                        break
                except Exception:
                    continue

            if not dlg_found:
                dlg_path = out_dir / f"{page_name}_after_{btn_text}.png"
                page.screenshot(path=str(dlg_path))
                dialogs.append({
                    "button": btn_text,
                    "screenshot": str(dlg_path.relative_to(out_dir.parent)),
                    "note": "full_page_fallback",
                })

            # 关闭弹窗
            try:
                page.keyboard.press("Escape")
                page.wait_for_timeout(300)
            except Exception:
                pass
            try:
                close_btn = page.get_by_role("button", name=re.compile(r"关闭|取消|Cancel|Close")).first
                if close_btn.is_visible():
                    close_btn.click()
                    page.wait_for_timeout(300)
            except Exception:
                pass
        except Exception:
            continue
    return dialogs


def main():
    args = resolve_args(parse_args())

    is_local = bool(args.local_dir)
    mode_label = f"本地 HTML: {args.local_dir}" if is_local else f"URL: {args.base_url}"

    out_dir = Path(args.out_dir)
    pages_dir = out_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)

    print(f"Web 侧栏截图: {mode_label}")
    print(f"输出目录: {out_dir}")
    print(f"按钮截图: {'开启' if args.capture_dialogs else '关闭'}")

    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=not args.headed)

    context_args = {
        "viewport": {"width": int(args.viewport.split("x")[0]), "height": int(args.viewport.split("x")[1])},
    }
    if args.storage_state and Path(args.storage_state).is_file():
        context_args["storage_state"] = args.storage_state
        print(f"  注入登录态: {args.storage_state}")

    context = browser.new_context(**context_args)
    page = context.new_page()

    # URL 模式：手动登录
    if not is_local and args.manual_login:
        print("  手动登录模式: 请在浏览器中登录，按 Enter 继续...")
        page.goto(args.base_url, wait_until="domcontentloaded")
        input()
        if args.storage_state:
            Path(args.storage_state).parent.mkdir(parents=True, exist_ok=True)
            context.storage_state(path=args.storage_state)
            print(f"  登录态已保存: {args.storage_state}")

    # 加载路由
    routes = load_routes(args.routes_file)

    # 构建待截图列表
    all_items = []  # list of (display_name, text_label, actual_url)

    if is_local:
        # 本地 HTML 模式
        local_dir = Path(args.local_dir).resolve()
        if routes:
            file_list = routes
            print(f"文件清单: {len(file_list)} 个")
        else:
            file_list = scan_local_html(args.local_dir)
            print(f"自动扫描 HTML: {len(file_list)} 个")

        for fname in file_list:
            safe_name = Path(fname).name
            file_path = local_dir / safe_name
            if file_path.exists():
                all_items.append((safe_name, safe_name, f"file://{file_path}"))
            else:
                all_items.append((safe_name, safe_name, None))
    else:
        # URL 模式：提取侧栏菜单
        page.goto(args.base_url, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)
        menu_items = extract_menu_items(page)
        print(f"侧栏菜单: {len(menu_items)} 项")

        # 合并路由 + 菜单
        seen_paths = set()
        for m in menu_items:
            path = m["path"]
            if path.startswith("/"):
                seen_paths.add(path)
                all_items.append((path, m["text"], urljoin(args.base_url, path)))

        for r in routes:
            if r.startswith("/") and r not in seen_paths:
                seen_paths.add(r)
                all_items.append((r, Path(r).name, urljoin(args.base_url, r)))

    # 限制
    all_items = all_items[:args.max_pages]
    print(f"待截图: {len(all_items)} 页")

    # 截图
    manifest = []
    for i, (display_name, text_label, url) in enumerate(all_items):
        safe_name = re.sub(r"[^a-zA-Z0-9_\u4e00-\u9fff.-]", "_", text_label)[:30].rstrip("_")
        out_path = pages_dir / f"{safe_name}.png"

        print(f"  [{i+1}/{len(all_items)}] {display_name}")

        if url is None:
            manifest.append({"url": display_name, "error": "file_not_found", "status": "failed"})
            print(f"    失败: 文件不存在")
            continue

        try:
            if not is_local:
                # URL 模式：尝试点击菜单导航
                clicked = False
                if args.start_menu or text_label:
                    clicked = click_menu_and_wait(page, text_label, args.wait_ms)
                if not clicked:
                    page.goto(url, wait_until="domcontentloaded", timeout=15000)
                    page.wait_for_timeout(args.wait_ms)
            else:
                # 本地模式：直接打开
                page.goto(url, wait_until="domcontentloaded", timeout=15000)
                page.wait_for_timeout(args.wait_ms)

            page.screenshot(path=str(out_path))

            entry = {
                "url": display_name,  # 脱敏：不暴露 file:// 路径
                "text": text_label,
                "screenshot": str(out_path.relative_to(out_dir.parent)),
                "status": "ok",
            }
            print(f"    OK: {out_path.name}")

            # 按钮弹窗截图
            if args.capture_dialogs:
                dialogs = capture_dialogs(page, pages_dir, safe_name, args.capture_buttons)
                if dialogs:
                    print(f"    弹窗/按钮截图: {len(dialogs)} 个")
                    entry["dialog_screenshots"] = dialogs

            manifest.append(entry)
        except Exception as e:
            manifest.append({
                "url": display_name,
                "text": text_label,
                "error": str(e)[:200],
                "status": "failed",
            })
            print(f"    失败: {e}")

    # 保存
    manifest_path = out_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    ok = sum(1 for m in manifest if m.get("status") == "ok")
    fail = sum(1 for m in manifest if m.get("status") == "failed")
    dlg_count = sum(len(m.get("dialog_screenshots", [])) for m in manifest)
    print(f"\n完成: 成功 {ok} 页, 失败 {fail} 页, 弹窗截图 {dlg_count} 个")
    print(f"manifest.json: {manifest_path}")

    page.close()
    context.close()
    browser.close()
    pw.stop()


if __name__ == "__main__":
    main()
