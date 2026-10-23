#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本地单文件 HTML 原型截图：侧栏页 + Tab + Drawer + 操作按钮弹窗。"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

BUTTON_PATTERN = re.compile(
    r"^(新增|添加|创建|编辑|修改|查看|查看全部|详情|导出|导入|设置|配置|发送|测试|预览|"
    r"提交|终止|取消|恢复|配额|处理|保存|"
    r"➕\s*.+|🔗\s*.+|⚙️\s*.+|📥\s*.+|💾\s*.+|"
    r"新增\w+|创建\w+|添加\w+|查看\w+)$"
)

# 表格行内按钮：同一文案多行各拍一张
ROW_ACTION_LABELS = frozenset({
    "详情", "编辑", "终止", "取消", "恢复", "配额", "处理",
})

SKIP_BUTTONS = frozenset({
    "刷新", "搜索", "重置", "查询", "批量删除", "删除",
})

SKIP_SUBSTR = ("刷新",)

DIALOG_SELECTORS = (
    "[role='dialog'], [role='alertdialog'], .el-dialog, .drawer.open, "
    "#proto-mock-modal[style*='flex']"
)

INJECT_JS = """
() => {
  if (window.showProtoMock) return;
  window.ensureProtoMock = function() {
    if (document.getElementById('proto-mock-modal')) return;
    const overlay = document.createElement('div');
    overlay.id = 'proto-mock-modal';
    overlay.style.cssText = 'position:fixed;inset:0;background:rgba(15,23,42,0.35);backdrop-filter:blur(4px);z-index:999;display:none;align-items:center;justify-content:center;';
    overlay.innerHTML = `
      <div class="card" style="width:520px;max-width:90vw;">
        <div class="card-header"><div class="card-title" id="proto-mock-title">操作</div></div>
        <div class="card-body" id="proto-mock-body"></div>
        <div style="padding:12px 20px;border-top:1px solid #e2e8f0;display:flex;gap:8px;justify-content:flex-end;">
          <button type="button" class="btn btn-secondary btn-sm" id="proto-mock-cancel">取消</button>
          <button type="button" class="btn btn-primary btn-sm" id="proto-mock-ok">确定</button>
        </div>
      </div>`;
    document.body.appendChild(overlay);
    document.getElementById('proto-mock-cancel').onclick = () => window.closeProtoMock();
    document.getElementById('proto-mock-ok').onclick = () => window.closeProtoMock();
  };
  window.showProtoMock = function(title) {
    window.ensureProtoMock();
    document.getElementById('proto-mock-title').textContent = title;
    document.getElementById('proto-mock-body').innerHTML =
      '<p style="color:#64748b;font-size:12px;margin-bottom:12px;">原型交互占位 · 表单字段以 PRD 为准</p>' +
      '<div class="form-group"><label class="form-label">名称 *</label><input class="form-input" placeholder="请输入..." /></div>' +
      '<div class="form-group"><label class="form-label">描述</label><input class="form-input" placeholder="可选" /></div>';
    const m = document.getElementById('proto-mock-modal');
    m.style.display = 'flex';
  };
  window.closeProtoMock = function() {
    const m = document.getElementById('proto-mock-modal');
    if (m) m.style.display = 'none';
    if (typeof closeDrawer === 'function') closeDrawer();
  };
}
"""


def slugify(text: str, max_len: int = 96) -> str:
    text = (text or "page").strip()
    text = re.sub(r"[\\/:*?\"<>|]", "-", text)
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"[^\w\-\u4e00-\u9fff.]", "-", text, flags=re.UNICODE)
    text = re.sub(r"-+", "-", text).strip("-")
    return (text or "page")[:max_len]


def file_url(path: Path) -> str:
    return path.resolve().as_uri()


def normalize_btn_label(raw: str) -> str:
    return re.sub(r"\s+", " ", (raw or "").strip())


def button_matches(label: str) -> bool:
    if not label or label in SKIP_BUTTONS:
        return False
    if any(s in label for s in SKIP_SUBSTR):
        return False
    if BUTTON_PATTERN.match(label):
        return True
    # 带 emoji 前缀的按钮
    for prefix in ("➕", "🔗", "⚙️", "📥", "💾", "✅", "🔒", "📝", "🔄"):
        if label.startswith(prefix):
            return True
    return label in ("编辑", "详情", "终止", "取消", "恢复", "配额", "处理", "查看全部")


def row_context(row_locator) -> str:
    """取表格行标识（优先 td-name / td-mono）。"""
    for sel in (".td-name", ".td-mono", "td"):
        cell = row_locator.locator(sel).first
        try:
            if cell.count() and cell.is_visible():
                txt = normalize_btn_label(cell.inner_text(timeout=500))
                if txt and txt not in ("—", "-"):
                    return txt[:48]
        except Exception:
            continue
    return "row"


def click_and_snap_button(
    page,
    btn,
    page_label: str,
    snap,
    *,
    suffix: str = "",
    trigger: str = "",
) -> None:
    """点击单个按钮并截图弹窗/抽屉/mock。"""
    label = normalize_btn_label(btn.inner_text(timeout=800))
    trig = trigger or label
    base = f"{page_label}-按钮-{label}{suffix}"
    shot_label = base
    shot_id = slugify(shot_label)

    try:
        close_overlays(page)
        btn.scroll_into_view_if_needed(timeout=3000)
        btn.click(timeout=5000)
        page.wait_for_timeout(600)

        if page.locator(".drawer.open").count() > 0:
            snap(page, shot_id, shot_label, kind="drawer", trigger=trig)
        elif page.evaluate(
            "() => { const m=document.getElementById('proto-mock-modal'); return !!(m && m.style.display==='flex'); }"
        ):
            snap(page, shot_id, shot_label, kind="dialog", trigger=trig)
        else:
            dlg = page.locator(".drawer.open, [role='dialog']").first
            if dlg.count() and dlg.is_visible():
                snap(page, shot_id, shot_label, kind="dialog", trigger=trig)
            else:
                page.evaluate(f"showProtoMock({json.dumps(label + (suffix or ''))})")
                page.wait_for_timeout(400)
                snap(page, shot_id, shot_label, kind="dialog", trigger=f"{trig}(mock)")
    except Exception as e:
        snap(
            page,
            slugify(f"{page_label}-btn-fail-{label}{suffix}"),
            f"{page_label}-按钮失败-{label}{suffix}",
            kind="dialog",
            trigger=trig,
            status="failed",
            error=str(e)[:200],
        )
    finally:
        close_overlays(page)


def capture_table_row_buttons(
    page,
    scope: str,
    page_label: str,
    snap,
    *,
    max_rows: int = 20,
) -> None:
    """表格每一行的 详情/编辑/终止 等分别截图（不去重合并）。"""
    rows = page.locator(f"{scope} tbody tr")
    n = min(rows.count(), max_rows)
    seen: set[str] = set()

    for ri in range(n):
        row = rows.nth(ri)
        try:
            if not row.is_visible():
                continue
            ctx = row_context(row)
        except Exception:
            ctx = f"row{ri+1}"

        btns = row.locator("button.btn:visible")
        for bi in range(btns.count()):
            btn = btns.nth(bi)
            try:
                label = normalize_btn_label(btn.inner_text(timeout=500))
            except Exception:
                continue
            if label not in ROW_ACTION_LABELS:
                continue
            dedupe = f"{page_label}::{ctx}::{label}"
            if dedupe in seen:
                continue
            seen.add(dedupe)
            suffix = f"-行-{ctx}"
            click_and_snap_button(page, btn, page_label, snap, suffix=suffix, trigger=f"{ctx}/{label}")


def capture_action_buttons(
    page,
    scope: str,
    page_label: str,
    snap,
    *,
    max_buttons: int = 40,
    per_row_detail: bool = True,
    max_rows: int = 20,
) -> None:
    """页头/卡片区按钮 + 可选表格逐行操作按钮。"""
    if per_row_detail:
        capture_table_row_buttons(page, scope, page_label, snap, max_rows=max_rows)

    # 非表格行内的按钮（页头新增、卡片头创建规则、查看全部…）
    loc = page.locator(f"{scope} button.btn:visible")
    seen: set[str] = set()

    for i in range(min(loc.count(), 80)):
        if len(seen) >= max_buttons:
            break
        btn = loc.nth(i)
        try:
            if not btn.is_visible():
                continue
            # 跳过 tbody 内（已在 capture_table_row_buttons 处理）
            in_row = btn.evaluate("el => !!el.closest('tbody tr')")
            if in_row:
                continue
            label = normalize_btn_label(btn.inner_text(timeout=800))
        except Exception:
            continue
        if not button_matches(label):
            continue
        dedupe_key = f"{page_label}::{label}"
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        click_and_snap_button(page, btn, page_label, snap)


@dataclass
class ShotRecord:
    id: str
    label: str
    file: str
    kind: str = "page"  # page | dialog | drawer | tab
    trigger: str = ""
    status: str = "ok"
    error: str = ""


def write_index(out_dir: Path, records: list[ShotRecord]) -> None:
    lines = [
        "# 原型截图索引",
        "",
        f"输出目录：`{out_dir}`",
        "",
        "| 文件 | 类型 | 说明 | 触发 | 状态 |",
        "|------|------|------|------|------|",
    ]
    for r in records:
        trig = r.trigger or "—"
        lines.append(f"| [{r.file}](pages/{r.file}) | {r.kind} | {r.label} | {trig} | {r.status} |")
    (out_dir / "INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def safe_print(msg: str) -> None:
    import sys
    out = (msg + "\n").encode("utf-8", errors="replace")
    sys.stdout.buffer.write(out)
    sys.stdout.buffer.flush()


def close_overlays(page) -> None:
    page.evaluate("typeof closeProtoMock==='function'&&closeProtoMock()")
    page.evaluate("typeof closeDrawer==='function'&&closeDrawer()")
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)


def main() -> None:
    ap = argparse.ArgumentParser(description="本地 HTML 原型批量截图（含操作按钮）")
    ap.add_argument("--html", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--viewport", default="1440x900")
    ap.add_argument("--wait-ms", type=int, default=800)
    ap.add_argument("--capture-module-tabs", action="store_true", default=True,
                    help="权限/设置等多 Tab 模块分别截图")
    ap.add_argument("--capture-drawers", action="store_true", default=True)
    ap.add_argument("--capture-action-buttons", action="store_true", default=True)
    ap.add_argument("--per-row-detail", action="store_true", default=True,
                    help="表格每行 详情/编辑/终止 等分别截图")
    ap.add_argument("--max-buttons-per-page", type=int, default=40)
    ap.add_argument("--max-rows-per-table", type=int, default=20)
    args = ap.parse_args()

    html_path = Path(args.html)
    if not html_path.is_file():
        raise SystemExit(f"HTML 不存在: {html_path}")

    out_dir = Path(args.out_dir)
    pages_dir = out_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)

    vw, vh = (int(x) for x in args.viewport.lower().split("x", 1))
    url = file_url(html_path)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise SystemExit("需要 playwright: pip install playwright && playwright install chromium")

    records: list[ShotRecord] = []

    def snap(page, shot_id: str, label: str, *, kind: str = "page", trigger: str = "",
             status: str = "ok", error: str = "") -> None:
        fname = f"{shot_id}.png"
        fpath = pages_dir / fname
        try:
            page.wait_for_timeout(args.wait_ms)
            page.screenshot(path=str(fpath), full_page=False)
            records.append(ShotRecord(id=shot_id, label=label, file=fname, kind=kind,
                                    trigger=trigger, status=status, error=error))
            safe_print(f"OK  [{kind}] {fname}  {label}")
        except Exception as e:
            records.append(ShotRecord(id=shot_id, label=label, file=fname, kind=kind,
                                    trigger=trigger, status="failed", error=str(e)))
            safe_print(f"FAIL [{kind}] {fname}  {label}  {e}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": vw, "height": vh})
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=120_000)
        page.wait_for_timeout(args.wait_ms)
        page.evaluate(INJECT_JS)

        nav_pages = page.evaluate(
            """() => Array.from(document.querySelectorAll('.nav-item[data-page]')).map(el => ({
                page: el.dataset.page,
                label: document.getElementById('page-' + el.dataset.page)?.dataset.label
                    || el.innerText.trim().replace(/\\s+/g, ' ')
            }))"""
        )

        for item in nav_pages:
            pid = item["page"]
            label = item.get("label") or pid
            page.evaluate(f"switchModule({json.dumps(pid)})")
            page.wait_for_timeout(400)
            scope = f"#page-{pid}"

            snap(page, slugify(f"{pid}-{label}"), label, kind="page")

            if args.capture_action_buttons:
                capture_action_buttons(
                    page, scope, label, snap,
                    max_buttons=args.max_buttons_per_page,
                    per_row_detail=args.per_row_detail,
                    max_rows=args.max_rows_per_table,
                )

            if pid in ("auth", "settings") and args.capture_module_tabs:
                module_tabs = [
                    ("users", "权限-用户管理"),
                    ("roles", "权限-角色定义"),
                    ("permissions", "权限-访问控制"),
                    ("audit", "权限-操作审计"),
                ]
                for tab_id, tab_label in module_tabs:
                    page.evaluate(
                        f"""(() => {{
                            const root = document.querySelector('#page-{pid}') || document.querySelector('#page-auth');
                            if (!root) return;
                            const tabs = root.querySelectorAll('.tabs .tab, [role="tab"]');
                            const idx = {{users:0, roles:1, permissions:2, audit:3}}[{json.dumps(tab_id)}];
                            const el = tabs[idx];
                            if (el) {{
                                if (typeof switchAuthTab === 'function') switchAuthTab(el, {json.dumps(tab_id)});
                                else el.click();
                            }}
                        }})()"""
                    )
                    page.wait_for_timeout(400)
                    snap(page, slugify(tab_label), tab_label, kind="tab")
                    if args.capture_action_buttons:
                        capture_action_buttons(
                            page, f"#{pid}-{tab_id}, #auth-{tab_id}", tab_label, snap,
                            max_buttons=args.max_buttons_per_page,
                            per_row_detail=args.per_row_detail,
                            max_rows=args.max_rows_per_table,
                        )

            if pid in ("inventory", "products") and args.capture_drawers:
                for item_id, item_label in [
                    ("sku-001", "库存-商品详情-在售"),
                    ("sku-002", "库存-商品详情-低库存"),
                    ("sku-003", "库存-商品详情-缺货"),
                ]:
                    page.evaluate(f"switchModule({json.dumps(pid)})")
                    page.evaluate(
                        f"""(() => {{
                            if (typeof openItemDrawer === 'function') openItemDrawer({json.dumps(item_id)});
                            else if (typeof openNodeDrawer === 'function') openNodeDrawer({json.dumps(item_id)});
                        }})()"""
                    )
                    snap(page, slugify(item_label), item_label, kind="drawer", trigger="openItemDrawer")
                    page.evaluate("typeof closeDrawer==='function'&&closeDrawer()")

        browser.close()

    manifest = {
        "source_html": str(html_path),
        "source_url": url,
        "viewport": args.viewport,
        "total": len(records),
        "failed": sum(1 for r in records if r.status != "ok"),
        "by_kind": {},
        "pages": [asdict(r) for r in records],
    }
    for r in records:
        manifest["by_kind"][r.kind] = manifest["by_kind"].get(r.kind, 0) + 1

    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_index(out_dir, records)
    safe_print(f"\n完成: {len(records)} 张 → {out_dir}")
    safe_print(f"分类: {manifest['by_kind']}")
    if manifest["failed"]:
        raise SystemExit(f"有 {manifest['failed']} 张截图失败")


if __name__ == "__main__":
    main()
