#!/usr/bin/env python3
"""
页面 DOM 扫描 — 提取所有可交互元素的结构化信息。

用途：
  给 LLM 提供真实 DOM 数据，避免看图猜选择器。
  输出 JSON 供 testcase-skills 生成和 UI-skills 执行使用。

用法:
  # URL 模式
  python scan_page_dom.py --url http://your-server:8080/login --out output/dom_login.json

  # 本地 HTML 模式
  python scan_page_dom.py --file /path/to/page.html --out output/dom_page.json

  # 指定输出目录（自动命名）
  python scan_page_dom.py --url http://your-server:8080 --out-dir output/dom-scan/

  # 只扫描可见元素（跳过 hidden/disabled）
  python scan_page_dom.py --url http://your-server:8080 --visible-only

  # 自定义视口
  python scan_page_dom.py --url http://your-server:8080 --viewport 1920x1080

依赖:
  pip install playwright
  playwright install chromium
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright, Page
except ImportError:
    print("请安装: pip install playwright && playwright install chromium")
    sys.exit(1)


def parse_args():
    p = argparse.ArgumentParser(
        description="页面 DOM 扫描 — 提取可交互元素",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--url", default=None, help="目标 URL")
    p.add_argument("--file", default=None, help="本地 HTML 文件路径")
    p.add_argument("--out", default=None, help="输出 JSON 文件路径")
    p.add_argument("--out-dir", default="output/dom-scan", help="输出目录（无 --out 时自动命名）")
    p.add_argument("--viewport", default="1440x900", help="视口尺寸 (宽x高)")
    p.add_argument("--wait-ms", type=int, default=1500, help="等待渲染毫秒数")
    p.add_argument("--headed", action="store_true", help="有头模式（调试用）")
    p.add_argument("--visible-only", action="store_true", help="仅扫描可见元素")
    p.add_argument("--storage-state", default=None, help="登录态 JSON 路径")
    p.add_argument("--max-elements", type=int, default=500, help="最大元素数")
    p.add_argument("--cache-dir", default=None, help="DOM 快照缓存目录（默认 output/dom-cache/）")
    p.add_argument("--no-cache", action="store_true", help="跳过缓存，强制重新扫描")
    p.add_argument("--cache-ttl", type=int, default=3600, help="缓存有效期（秒，默认 1 小时）")
    return p.parse_args()


def resolve_args(args):
    """校验参数。"""
    if not args.url and not args.file:
        print("错误: 必须指定 --url 或 --file")
        sys.exit(1)

    if args.url and args.file:
        print("错误: --url 和 --file 不能同时使用")
        sys.exit(1)

    # 确定输出路径
    if args.out:
        args.out_path = Path(args.out)
    else:
        out_dir = Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        if args.file:
            name = Path(args.file).stem
        else:
            from urllib.parse import urlparse
            name = urlparse(args.url).netloc.replace(":", "_") or "page"
        args.out_path = out_dir / f"dom_{name}.json"

    return args


def scan_interactive_elements(page: Page, visible_only: bool = False, max_elements: int = 500) -> list[dict]:
    """从页面提取所有可交互元素的结构化信息。"""
    elements = page.evaluate("""(params) => {
        const visibleOnly = params.visibleOnly;
        const maxElements = params.maxElements;
        const results = [];
        const selectors = [
            // 按钮类
            'button', 'input[type="button"]', 'input[type="submit"]', 'input[type="reset"]',
            // 输入类
            'input:not([type="hidden"])', 'textarea', 'select',
            // 链接
            'a[href]',
            // 可交互元素（role + tabindex）
            '[role="button"]', '[role="link"]', '[role="textbox"]', '[role="combobox"]',
            '[role="listbox"]', '[role="menuitem"]', '[role="menuitemcheckbox"]',
            '[role="menuitemradio"]', '[role="option"]', '[role="radio"]',
            '[role="checkbox"]', '[role="switch"]', '[role="slider"]',
            '[role="searchbox"]', '[role="spinbutton"]',
            // 可聚焦元素
            '[tabindex]:not([tabindex="-1"])',
            // 详情/摘要
            'details > summary',
            // 可编辑元素
            '[contenteditable="true"]', '[contenteditable=""]',
        ];

        const allEls = new Set();
        for (const sel of selectors) {
            try {
                document.querySelectorAll(sel).forEach(el => allEls.add(el));
            } catch (e) {}
        }

        for (const el of allEls) {
            // 跳过不可见元素
            if (visibleOnly) {
                const style = window.getComputedStyle(el);
                if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') {
                    continue;
                }
                const rect = el.getBoundingClientRect();
                if (rect.width === 0 && rect.height === 0) {
                    continue;
                }
            }

            // 跳过被 disabled 的元素（但保留，标记状态）
            const isDisabled = el.disabled || el.getAttribute('aria-disabled') === 'true';

            // 提取定位线索
            const hints = {
                tag: el.tagName.toLowerCase(),
                text: (el.textContent || '').trim().substring(0, 100),
                type: el.getAttribute('type') || null,
                name: el.getAttribute('name') || null,
                id: el.getAttribute('id') || null,
                class: el.className ? (typeof el.className === 'string' ? el.className : (el.className.baseVal || '')).substring(0, 200) : null,
                role: el.getAttribute('role') || el.tagName.toLowerCase(),
                'data-testid': el.getAttribute('data-testid') || el.getAttribute('data-test') || el.getAttribute('data-cy') || null,
                'aria-label': el.getAttribute('aria-label') || null,
                'aria-labelledby': el.getAttribute('aria-labelledby') || null,
                placeholder: el.getAttribute('placeholder') || null,
                title: el.getAttribute('title') || null,
                href: el.getAttribute('href') || null,
                value: el.value || null,
                checked: el.checked !== undefined ? el.checked : null,
                selected: el.selected !== undefined ? el.selected : null,
                disabled: isDisabled,
                readonly: el.readOnly || el.getAttribute('readonly') !== null,
                visible: !visibleOnly,  // 如果 visibleOnly=false，这里都是 true
            };

            // 提取 CSS 选择器（精简版，优先稳定属性）
            const cssParts = [];
            if (hints.id) {
                cssParts.push(`#${hints.id}`);
            } else {
                cssParts.push(hints.tag);
                if (hints.class) {
                    const classes = hints.class.split(/\\s+/).filter(c => c && !c.startsWith('css-') && !c.startsWith('_'));
                    if (classes.length > 0) {
                        cssParts.push('.' + classes.slice(0, 2).join('.'));
                    }
                }
            }
            hints.css = cssParts.join('');

            // 提取父级锚点（用于 L2 推断）
            const parent = el.parentElement;
            if (parent) {
                const parentRole = parent.getAttribute('role') || parent.tagName.toLowerCase();
                const parentId = parent.getAttribute('id') || '';
                const parentClass = parent.className ? (typeof parent.className === 'string' ? parent.className : '').substring(0, 100) : '';
                hints.parent = {
                    tag: parent.tagName.toLowerCase(),
                    role: parentRole,
                    id: parentId || null,
                    class: parentClass || null,
                    text: (parent.textContent || '').trim().substring(0, 80),
                };
            }

            // 提取 label（针对输入元素）
            if (hints.tag === 'input' || hints.tag === 'textarea' || hints.tag === 'select') {
                const labelEl = el.closest('label') ||
                    document.querySelector(`label[for="${el.id}"]`) ||
                    document.querySelector(`label[for="${el.name}"]`);
                if (labelEl) {
                    hints.label = (labelEl.textContent || '').trim().substring(0, 100);
                }
            }

            results.push(hints);

            if (results.length >= maxElements) break;
        }

        return results;
    }""", {"visibleOnly": visible_only, "maxElements": max_elements})

    return elements


def scan_page_structure(page: Page) -> dict:
    """提取页面整体结构信息。"""
    return page.evaluate("""() => {
        const result = {
            title: document.title,
            url: window.location.href,
            meta: {},
        };

        // 提取 meta 标签
        document.querySelectorAll('meta[name], meta[property]').forEach(el => {
            const name = el.getAttribute('name') || el.getAttribute('property');
            const content = el.getAttribute('content');
            if (name && content) {
                result.meta[name] = content.substring(0, 200);
            }
        });

        // 提取页面区域
        result.regions = [];
        const regionSelectors = ['main', 'nav', 'aside', 'header', 'footer', '[role="main"]', '[role="navigation"]'];
        for (const sel of regionSelectors) {
            const els = document.querySelectorAll(sel);
            els.forEach(el => {
                result.regions.push({
                    tag: el.tagName.toLowerCase(),
                    role: el.getAttribute('role') || null,
                    id: el.getAttribute('id') || null,
                    text_length: (el.textContent || '').trim().length,
                });
            });
        }

        return result;
    }""")


def scan_dialogs(page: Page) -> list[dict]:
    """扫描页面上的弹窗/抽屉/模态框。"""
    return page.evaluate("""() => {
        const results = [];
        const selectors = [
            '[role="dialog"]', '[role="alertdialog"]',
            '.ant-modal', '.ant-drawer', '.el-dialog', '.el-drawer',
            '.modal', '.v-dialog', '[class*="Dialog"]', '[class*="Modal"]',
            '[class*="Drawer"]', '[class*="dialog"]', '[class*="modal"]',
        ];

        for (const sel of selectors) {
            try {
                document.querySelectorAll(sel).forEach(el => {
                    const style = window.getComputedStyle(el);
                    const isVisible = style.display !== 'none' &&
                                     style.visibility !== 'hidden' &&
                                     style.opacity !== '0';
                    const rect = el.getBoundingClientRect();
                    const hasContent = rect.width > 0 && rect.height > 0;

                    results.push({
                        selector: sel,
                        tag: el.tagName.toLowerCase(),
                        id: el.getAttribute('id') || null,
                        title: (el.querySelector('h1, h2, h3, h4, [class*="title"], [class*="Title"]')?.textContent || '').trim().substring(0, 100),
                        visible: isVisible,
                        has_content: hasContent,
                        button_count: el.querySelectorAll('button, [role="button"]').length,
                        input_count: el.querySelectorAll('input, textarea, select').length,
                    });
                });
            } catch (e) {}
        }

        return results;
    }""")


def scan_routes(page: Page) -> list[str]:
    """扫描页面中的路由链接（SPA 路由发现）。"""
    return page.evaluate("""() => {
        const routes = [];
        const aEls = document.querySelectorAll('a[href]');
        for (const a of aEls) {
            const href = a.getAttribute('href') || '';
            if (href.startsWith('/') && !href.includes('#') && !href.includes('javascript')) {
                routes.push({
                    path: href,
                    text: (a.textContent || '').trim().substring(0, 80),
                    visible: a.offsetParent !== null,
                });
            }
        }
        return routes;
    }""")


def build_summary(page_info: dict, elements: list[dict], dialogs: list[dict], routes: list[str]) -> dict:
    """构建扫描结果的摘要。"""
    # 按类型统计
    type_counts = {}
    for el in elements:
        t = el.get("role", el.get("tag", "unknown"))
        type_counts[t] = type_counts.get(t, 0) + 1

    # 统计定位线索覆盖
    has_testid = sum(1 for e in elements if e.get("data-testid"))
    has_role = sum(1 for e in elements if e.get("role"))
    has_label = sum(1 for e in elements if e.get("label"))
    has_aria = sum(1 for e in elements if e.get("aria-label"))
    has_id = sum(1 for e in elements if e.get("id"))
    has_name = sum(1 for e in elements if e.get("name"))
    total = len(elements)

    # 统计 disabled 元素
    disabled_count = sum(1 for e in elements if e.get("disabled"))

    return {
        "scan_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "page": {
            "title": page_info.get("title", ""),
            "url": page_info.get("url", ""),
        },
        "summary": {
            "total_elements": total,
            "by_type": type_counts,
            "locator_coverage": {
                "data-testid": f"{has_testid}/{total} ({has_testid*100//total}%)",
                "role": f"{has_role}/{total} ({has_role*100//total}%)",
                "label": f"{has_label}/{total} ({has_label*100//total}%)",
                "aria-label": f"{has_aria}/{total} ({has_aria*100//total}%)",
                "id": f"{has_id}/{total} ({has_id*100//total}%)",
                "name": f"{has_name}/{total} ({has_name*100//total}%)",
            },
            "disabled_elements": disabled_count,
            "dialogs_found": len(dialogs),
            "routes_found": len(routes),
        },
    }


def main():
    args = resolve_args(parse_args())

    # ── 缓存支持 ──
    cache_dir = Path(args.cache_dir) if args.cache_dir else Path("output/dom-cache")
    cache_dir.mkdir(parents=True, exist_ok=True)

    # 生成缓存 key
    source = args.url or str(Path(args.file).resolve())
    cache_key = hashlib.md5(source.encode()).hexdigest()[:12]
    cache_file = cache_dir / f"dom_{cache_key}.json"

    # 尝试加载缓存
    if not args.no_cache and cache_file.is_file():
        cache_age = time.time() - cache_file.stat().st_mtime
        if cache_age <= args.cache_ttl:
            print(f" 使用缓存: {cache_file} (年龄 {cache_age:.0f}s)")
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            # 仍然输出到指定路径
            args.out_path.parent.mkdir(parents=True, exist_ok=True)
            args.out_path.write_text(json.dumps(cached, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"\\n扫描完成（缓存）: {args.out_path}")
            summary = cached.get("summary", {})
            print(f"  元素总数: {summary.get('summary', {}).get('total_elements', 'N/A')}")
            return
        else:
            print(f" 缓存已过期 (年龄 {cache_age:.0f}s > TTL {args.cache_ttl}s)")

    print(f"页面 DOM 扫描")
    if args.url:
        print(f"目标: {args.url}")
    else:
        print(f"文件: {args.file}")
    print(f"输出: {args.out_path}")
    print(f"视口: {args.viewport}")
    print(f"仅可见: {args.visible_only}")

    # 启动浏览器
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=not args.headed)

    context_args = {
        "viewport": {"width": int(args.viewport.split("x")[0]), "height": int(args.viewport.split("x")[1])},
    }
    if args.storage_state and Path(args.storage_state).is_file():
        context_args["storage_state"] = args.storage_state
        print(f"注入登录态: {args.storage_state}")

    context = browser.new_context(**context_args)
    page = context.new_page()

    # 打开页面
    if args.url:
        print(f"打开 URL: {args.url}")
        page.goto(args.url, wait_until="domcontentloaded", timeout=30000)
    else:
        file_path = Path(args.file).resolve()
        file_url = f"file://{file_path}"
        print(f"打开文件: {file_url}")
        page.goto(file_url, wait_until="domcontentloaded", timeout=30000)

    page.wait_for_timeout(args.wait_ms)
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass  # SPA 可能不会 networkidle

    print("扫描中...")

    # 提取页面结构
    page_info = scan_page_structure(page)
    print(f"  页面: {page_info.get('title', 'N/A')}")

    # 提取可交互元素
    elements = scan_interactive_elements(page, args.visible_only, args.max_elements)
    print(f"  可交互元素: {len(elements)} 个")

    # 扫描弹窗
    dialogs = scan_dialogs(page)
    if dialogs:
        print(f"  弹窗/抽屉: {len(dialogs)} 个")

    # 扫描路由
    routes = scan_routes(page)
    if routes:
        visible_routes = [r for r in routes if r.get("visible")]
        print(f"  路由链接: {len(visible_routes)} 个可见 / {len(routes)} 个总计")

    # 构建结果
    summary = build_summary(page_info, elements, dialogs, routes)

    result = {
        "scan_info": {
            "source": args.url or f"file://{Path(args.file).resolve()}",
            "viewport": args.viewport,
            "visible_only": args.visible_only,
            "max_elements": args.max_elements,
        },
        "summary": summary,
        "page": page_info,
        "elements": elements,
        "dialogs": dialogs,
        "routes": routes,
    }

    # 保存
    args.out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # 保存到缓存
    if not args.no_cache:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f" 缓存已保存: {cache_file}")

    print(f"\n扫描完成: {args.out_path}")
    print(f"  元素总数: {summary['summary']['total_elements']}")
    print(f"  定位覆盖: testid={summary['summary']['locator_coverage']['data-testid']}")

    # 打印元素类型分布
    print(f"\n元素类型分布:")
    for t, c in sorted(summary["summary"]["by_type"].items(), key=lambda x: -x[1])[:15]:
        print(f"  {t}: {c}")

    page.close()
    context.close()
    browser.close()
    pw.stop()


if __name__ == "__main__":
    main()
