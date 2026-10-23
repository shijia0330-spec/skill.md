#!/usr/bin/env python3
"""
全站页面截图 — 主执行脚本。
批量截取 SPA 页面或本地 HTML 文件为 PNG，产出 manifest.json + INDEX.md。

支持两种模式：
  1. URL 模式：截取已部署的 Web 系统
  2. 本地模式：截取本地 HTML 文件（自动点击按钮截取弹窗）

用法 (URL 模式):
  python crawl_and_capture.py \
    --base-url http://your-server:8080 \
    --out-dir output/site-screenshots/demo \
    --routes-file templates/routes.example.txt \
    --auth-profile templates/auth_ui_login.example.yaml \
    --viewport 1440x900 \
    --wait-ms 1500

用法 (本地 HTML 模式):
  python crawl_and_capture.py \
    --local-dir /path/to/html-files \
    --out-dir output/site-screenshots/local \
    --routes-file templates/local_routes.txt \
    --viewport 1440x900 \
    --wait-ms 1500

依赖:
  pip install playwright pyyaml
  playwright install chromium
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

try:
    import yaml
except ImportError:
    print("请安装: pip install pyyaml")
    sys.exit(1)

try:
    from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page
except ImportError:
    print("请安装: pip install playwright && playwright install chromium")
    sys.exit(1)

# 默认截取的按钮文本（中英文）
DEFAULT_CAPTURE_BUTTONS = [
    "新增", "新建", "创建", "编辑", "修改", "查看", "详情", "删除", "导出", "导入",
    "New", "Create", "Edit", "View", "Detail", "Delete", "Export", "Import", "Add",
]


def parse_args():
    p = argparse.ArgumentParser(
        description="全站页面截图 — 支持 URL 和本地 HTML",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # URL 模式
  python crawl_and_capture.py --base-url http://your-server:8080 --routes-file routes.txt

  # 本地 HTML 模式（自动扫描目录下所有 .html）
  python crawl_and_capture.py --local-dir ./html-files

  # 本地 HTML 模式（指定文件列表）
  python crawl_and_capture.py --local-dir ./html-files --routes-file local_routes.txt

  # 自定义要截取的按钮
  python crawl_and_capture.py --local-dir ./html-files --capture-buttons "新增,编辑,详情"

  # 不截取按钮弹窗
  python crawl_and_capture.py --local-dir ./html-files --no-capture-dialogs
        """,
    )
    p.add_argument("--base-url", default=None, help="测试环境根地址（URL 模式必填）")
    p.add_argument("--local-dir", default=None, help="本地 HTML 文件目录（本地模式必填）")
    p.add_argument("--out-dir", default="output/site-screenshots", help="输出目录")
    p.add_argument("--routes-file", default=None, help="路由/文件清单（每行一个 path 或文件名）")
    p.add_argument("--crawl-menu", action="store_true", help="从侧栏菜单爬取链接（仅 URL 模式）")
    p.add_argument("--crawl-bfs", action="store_true", help="站内 BFS 爬取（仅 URL 模式）")
    p.add_argument("--max-depth", type=int, default=2, help="BFS 最大深度")
    p.add_argument("--max-pages", type=int, default=500, help="最大截图页数")
    p.add_argument("--auth-profile", default=None, help="登录配置文件 (YAML，仅 URL 模式)")
    p.add_argument("--storage-state", default=None, help="登录态 JSON 路径")
    p.add_argument("--viewport", default="1440x900", help="视口尺寸 (宽x高)")
    p.add_argument("--full-page", action="store_true", help="长页面完整截图")
    p.add_argument("--wait-ms", type=int, default=1500, help="截图前等待毫秒")
    p.add_argument("--ready-selector", default=None, help="就绪选择器（替代 wait-ms）")
    p.add_argument("--headed", action="store_true", help="有头模式（调试用）")
    p.add_argument("--capture-dialogs", action="store_true", default=True,
                   help="截取按钮弹窗（默认开启，用 --no-capture-dialogs 关闭）")
    p.add_argument("--no-capture-dialogs", action="store_true", default=False,
                   help="关闭按钮弹窗截图")
    p.add_argument("--capture-buttons", default=None,
                   help="要截取的按钮（逗号分隔，默认截所有常见按钮）")
    p.add_argument("--start-menu", default=None, help="侧栏起始菜单名")
    p.add_argument("--concurrency", type=int, default=1, help="并发数（当前仅串行）")
    return p.parse_args()


def resolve_args(args):
    """校验并处理参数互斥关系。"""
    # --no-capture-dialogs 覆盖 --capture-dialogs
    if args.no_capture_dialogs:
        args.capture_dialogs = False

    # 模式校验
    if args.local_dir and args.base_url:
        print("错误: --local-dir 和 --base-url 不能同时使用")
        sys.exit(1)

    if not args.local_dir and not args.base_url:
        print("错误: 必须指定 --local-dir（本地 HTML 模式）或 --base-url（URL 模式）")
        sys.exit(1)

    # 本地模式校验
    if args.local_dir:
        local_path = Path(args.local_dir)
        if not local_path.exists():
            print(f"错误: 本地目录不存在: {args.local_dir}")
            sys.exit(1)
        if not local_path.is_dir():
            print(f"错误: 不是目录: {args.local_dir}")
            sys.exit(1)

    # URL 模式校验
    if args.base_url:
        args.base_url = args.base_url.rstrip("/")

    # 解析按钮列表
    if args.capture_buttons:
        args.capture_buttons = [b.strip() for b in args.capture_buttons.split(",") if b.strip()]
    else:
        args.capture_buttons = list(DEFAULT_CAPTURE_BUTTONS)

    return args


def load_auth_profile(path: str | None) -> dict:
    """加载登录配置 YAML。"""
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        print(f"  警告: 登录配置文件不存在: {path}")
        return {}
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_routes(path: str | None) -> list[str]:
    """加载路由/文件清单（每行一个 path 或文件名，忽略空行和注释）。"""
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


def setup_browser(args) -> tuple:
    """初始化浏览器和上下文（含登录态注入）。
    返回 (pw_context_manager, browser, context)。
    """
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=not args.headed)

    auth = load_auth_profile(args.auth_profile)
    storage_state = args.storage_state or auth.get("storage_state")

    context_args = {
        "viewport": {"width": int(args.viewport.split("x")[0]), "height": int(args.viewport.split("x")[1])},
    }
    if storage_state and Path(storage_state).is_file():
        context_args["storage_state"] = storage_state
        print(f"  注入登录态: {storage_state}")

    context = browser.new_context(**context_args)
    return pw, browser, context


def do_form_login(context: BrowserContext, base_url: str, auth: dict) -> None:
    """表单登录（storage_state 不存在时）。"""
    login_path = auth.get("login_path", "/login")
    username_field = auth.get("username_field", "username")
    password_field = auth.get("password_field", "password")
    username = auth.get("username") or os.environ.get("TEST_USERNAME", "")
    password = auth.get("password") or os.environ.get("TEST_PASSWORD", "")

    if not username or not password:
        print("  警告: 未提供登录账号，跳过表单登录")
        return

    page = context.new_page()
    url = urljoin(base_url, login_path)
    print(f"  表单登录: {url}")
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_timeout(1000)

    # 查找用户名/密码输入框
    if username_field:
        try:
            page.get_by_label(username_field).fill(username)
        except Exception:
            try:
                page.get_by_placeholder(username_field).fill(username)
            except Exception:
                page.locator(f'input[name="{username_field}"]').fill(username)

    if password_field:
        try:
            page.get_by_label(password_field).fill(password)
        except Exception:
            try:
                page.get_by_placeholder(password_field).fill(password)
            except Exception:
                page.locator(f'input[name="{password_field}"]').fill(password)

    # 点击登录按钮（6 种降级策略）
    login_attempts = [
        lambda: page.get_by_role("button", name="login"),
        lambda: page.get_by_role("button", name="登录"),
        lambda: page.locator('button[type="submit"]').first,
        lambda: page.locator("button.bg-primary").first,
        lambda: page.get_by_role("button", name=re.compile(r"^登\s*录$")),
        lambda: page.get_by_role("button", name=re.compile(r"^Login$")),
    ]
    for la in login_attempts:
        try:
            la().click(timeout=5000)
            break
        except Exception:
            continue
    else:
        print("  警告: 未找到登录按钮")

    page.wait_for_timeout(2000)
    page.wait_for_load_state("domcontentloaded")

    # 保存 storage_state
    state_path = Path("output/.auth/login_state.json")
    state_path.parent.mkdir(parents=True, exist_ok=True)
    context.storage_state(path=str(state_path))
    print(f"  登录态已保存: {state_path}")
    page.close()


def crawl_sidebar_links(page: Page, start_menu: str | None = None) -> list[str]:
    """从侧栏菜单爬取链接。"""
    links = page.evaluate("""(startMenu) => {
        const results = [];
        const selectors = [
            'aside a[href]', 'nav a[href]', '.sidebar a[href]',
            '.menu a[href]', '[role="navigation"] a[href]',
            '.ant-layout-sider a[href]', '.el-menu a[href]'
        ];
        for (const sel of selectors) {
            const els = document.querySelectorAll(sel);
            for (const el of els) {
                const href = el.getAttribute('href') || el.getAttribute('data-path') || '';
                const text = el.textContent?.trim() || '';
                if (href && href.startsWith('/')) {
                    if (!startMenu || text.includes(startMenu)) {
                        results.push({path: href, text: text});
                    }
                }
            }
        }
        return results;
    }""", start_menu)
    return [l["path"] for l in links]


def crawl_bfs_links(page: Page, base_url: str, max_depth: int = 2) -> list[str]:
    """站内 BFS 爬取链接。"""
    visited = set()
    queue = [(base_url, 0)]
    all_links = set()

    while queue:
        url, depth = queue.pop(0)
        if depth > max_depth or url in visited:
            continue
        visited.add(url)

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=10000)
            page.wait_for_timeout(500)
            links = page.evaluate("""(baseUrl) => {
                const results = [];
                const aEls = document.querySelectorAll('a[href]');
                for (const a of aEls) {
                    const href = a.getAttribute('href');
                    if (href && href.startsWith('/') && !href.includes('#')) {
                        const full = new URL(href, baseUrl).pathname;
                        if (full.startsWith(baseUrl.pathname)) {
                            results.push(full);
                        }
                    }
                }
                return results;
            }""", {"pathname": urlparse(base_url).path.rstrip("/")})
            for link in links:
                if link not in visited:
                    all_links.add(link)
                    queue.append((urljoin(base_url, link), depth + 1))
        except Exception:
            continue

    return list(all_links)


def capture_dialogs(page: Page, out_dir: Path, page_name: str, buttons: list[str], wait_ms: int = 800) -> list[dict]:
    """截取按钮触发的弹窗/抽屉区域。

    对每个按钮：点击 → 等待弹窗出现 → 截图 → 关闭弹窗。
    """
    dialogs = []
    for btn_text in buttons:
        try:
            btn = page.get_by_role("button", name=re.compile(re.escape(btn_text), re.IGNORECASE)).first
            if not btn.is_visible():
                continue
            btn.click()
            page.wait_for_timeout(wait_ms)
            page.wait_for_load_state("domcontentloaded")

            # 截取 dialog 区域
            dlg_selectors = [
                '[role="dialog"]', '.ant-modal-content', '.el-dialog__wrapper',
                '.el-dialog', '.modal-content', '[class*="Drawer"]',
                '[class*="modal"]', '.v-dialog', '[class*="dialog"]',
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
                # 如果没找到 dialog 选择器，截取整页
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


def screenshot_page(page: Page, url: str, out_path: Path, args) -> dict:
    """截取单个页面。"""
    result = {"url": url, "status": None, "screenshot": None, "error": None}
    try:
        resp = page.goto(url, wait_until="domcontentloaded", timeout=30000)
        result["status"] = resp.status if resp else None

        if args.ready_selector:
            page.wait_for_selector(args.ready_selector, timeout=10000)
        else:
            page.wait_for_timeout(args.wait_ms)

        if args.full_page:
            page.screenshot(path=str(out_path), full_page=True)
        else:
            page.screenshot(path=str(out_path))

        result["screenshot"] = str(out_path.relative_to(out_path.parent.parent))
        result["title"] = page.title()
        body_len = len((page.locator("body").inner_text() or "").strip())
        if body_len < 10 or (result["title"] or "").startswith("- "):
            result["warning"] = "blank_or_unmatched_route"
            result["body_text_len"] = body_len
    except Exception as e:
        result["error"] = str(e)[:200]
    return result


def build_index(manifest: list[dict], out_dir: Path) -> None:
    """生成 INDEX.md 浏览索引。"""
    index_path = out_dir / "INDEX.md"
    lines = ["# 全站截图索引", f"\n生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ""]

    ok_pages = [m for m in manifest if m.get("screenshot")]
    fail_pages = [m for m in manifest if m.get("error")]

    lines.append(f"总计: {len(manifest)} 页 | 成功: {len(ok_pages)} | 失败: {len(fail_pages)}")
    lines.append("")

    if ok_pages:
        lines.append("## 成功页面")
        lines.append("")
        lines.append("| 页面 | 截图 | 状态 |")
        lines.append("|------|------|------|")
        for m in ok_pages:
            name = Path(m["screenshot"]).stem
            lines.append(f"| {name} | ![{name}]({m['screenshot']}) | {m.get('status', '-')} |")
        lines.append("")

    if fail_pages:
        lines.append("## 失败页面")
        lines.append("")
        lines.append("| 页面 | 错误 |")
        lines.append("|-----|------|")
        for m in fail_pages:
            lines.append(f"| {m['url']} | {m.get('error', '-')} |")
        lines.append("")

    index_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  INDEX.md: {index_path}")


def main():
    args = resolve_args(parse_args())

    # 判断运行模式
    is_local = bool(args.local_dir)
    mode_label = f"本地 HTML: {args.local_dir}" if is_local else f"URL: {args.base_url}"

    out_dir = Path(args.out_dir)
    pages_dir = out_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)

    print(f"全站截图: {mode_label}")
    print(f"输出目录: {out_dir}")
    print(f"按钮截图: {'开启' if args.capture_dialogs else '关闭'}")
    if args.capture_dialogs:
        print(f"  截取按钮: {', '.join(args.capture_buttons)}")

    # 加载路由/文件清单
    routes = load_routes(args.routes_file)
    if is_local:
        if routes:
            print(f"文件清单: {len(routes)} 个")
        else:
            # 本地模式无清单时自动扫描
            routes = scan_local_html(args.local_dir)
            print(f"自动扫描 HTML: {len(routes)} 个")
    else:
        print(f"路由清单: {len(routes)} 条")

    # 初始化浏览器
    pw, browser, context = setup_browser(args)

    # URL 模式：表单登录
    if not is_local:
        auth = load_auth_profile(args.auth_profile)
        if not args.storage_state and not auth.get("storage_state"):
            do_form_login(context, args.base_url, auth)

    page = context.new_page()

    # 构建待截图列表
    all_items = []  # list of (display_name, actual_url)

    if is_local:
        # 本地 HTML 模式
        local_dir = Path(args.local_dir).resolve()
        for route in routes:
            # 支持带路径的文件名，取 basename 防止路径泄露
            fname = Path(route).name
            file_path = local_dir / fname
            if file_path.exists():
                file_url = f"file://{file_path}"
                all_items.append((fname, file_url))
            else:
                print(f"  警告: 文件不存在: {file_path}")
                all_items.append((fname, None))  # 标记为失败
    else:
        # URL 模式
        if routes:
            for r in routes:
                if r.startswith("http"):
                    all_items.append((r, r))
                else:
                    url = urljoin(args.base_url, r)
                    display = r
                    all_items.append((display, url))

        if args.crawl_menu:
            try:
                page.goto(args.base_url, wait_until="domcontentloaded", timeout=15000)
                page.wait_for_timeout(2000)
                sidebar_links = crawl_sidebar_links(page, args.start_menu)
                for link in sidebar_links:
                    url = urljoin(args.base_url, link)
                    if url not in [item[1] for item in all_items]:
                        all_items.append((link, url))
                print(f"侧栏爬取: {len(sidebar_links)} 条")
            except Exception as e:
                print(f"  侧栏爬取失败: {e}")

        if args.crawl_bfs:
            try:
                bfs_links = crawl_bfs_links(page, args.base_url, args.max_depth)
                for link in bfs_links:
                    url = urljoin(args.base_url, link)
                    if url not in [item[1] for item in all_items]:
                        all_items.append((link, url))
                print(f"BFS 爬取: {len(bfs_links)} 条")
            except Exception as e:
                print(f"  BFS 爬取失败: {e}")

    # 去重（保序）+ 限制
    seen = set()
    deduped = []
    for display, url in all_items:
        key = url or display
        if key not in seen:
            seen.add(key)
            deduped.append((display, url))
    all_items = deduped[:args.max_pages]
    print(f"待截图: {len(all_items)} 页")

    # 执行截图
    manifest = []
    for i, (display_name, url) in enumerate(all_items):
        # 生成安全的文件名（用 display_name，不含本地路径）
        safe_name = re.sub(r"[^a-zA-Z0-9_\u4e00-\u9fff.-]", "_", display_name)[:80].rstrip("_")
        out_path = pages_dir / f"{safe_name}.png"

        print(f"  [{i+1}/{len(all_items)}] {display_name}")

        if url is None:
            # 文件不存在
            manifest.append({
                "url": display_name,
                "error": "file_not_found",
                "screenshot": None,
            })
            print(f"    失败: 文件不存在")
            continue

        result = screenshot_page(page, url, out_path, args)
        # 脱敏：manifest 中只存 display_name，不存 file:// 本地路径
        result["url"] = display_name
        manifest.append(result)

        if result.get("error"):
            print(f"    失败: {result['error'][:80]}")
        elif result.get("warning") == "blank_or_unmatched_route":
            print(
                f"    空白页: {result.get('screenshot', 'unknown')} "
                f"(title={result.get('title', '')!r}, body_len={result.get('body_text_len', 0)})"
            )
        else:
            status_str = f"HTTP {result.get('status', '?')}" if not is_local else "local"
            print(f"    OK: {result.get('screenshot', 'unknown')} ({status_str})")

        # 按钮弹窗截图（URL 和本地 HTML 都支持）
        if args.capture_dialogs and not result.get("error"):
            dialogs = capture_dialogs(page, pages_dir, safe_name, args.capture_buttons)
            if dialogs:
                print(f"    弹窗/按钮截图: {len(dialogs)} 个")
                # 追加弹窗截图到 manifest
                if "dialog_screenshots" not in result:
                    result["dialog_screenshots"] = []
                result["dialog_screenshots"] = dialogs

    # 保存 manifest
    manifest_path = out_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"\nmanifest.json: {manifest_path}")

    # 生成索引
    build_index(manifest, out_dir)

    # 统计
    ok = sum(1 for m in manifest if m.get("screenshot"))
    fail = sum(1 for m in manifest if m.get("error"))
    dlg_count = sum(len(m.get("dialog_screenshots", [])) for m in manifest)
    print(f"\n完成: 成功 {ok} 页, 失败 {fail} 页, 弹窗截图 {dlg_count} 个")

    page.close()
    context.close()
    browser.close()
    pw.stop()


if __name__ == "__main__":
    main()
