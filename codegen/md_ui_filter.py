#!/usr/bin/env python3
"""
从 Markdown 功能用例中筛选 UI 自动化候选（与 UI-skills/转化 配套）。

支持三件套输入：Markdown + manifest.json + ui_cases_by_image.json（+ 可选截图目录校验）。

用法:
  python codegen/md_ui_filter.py -i examples/output_seckill_auth_testcases.md \\
      -o output/_pipeline/seckill_ui_candidates.json \\
      --manifest output/site-screenshots/seckill/manifest.json \\
      --specs-json output/_pipeline/seckill_ui_cases_by_image.json \\
      --screenshots-dir output/site-screenshots/seckill/pages \\
      --summary
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent

CASE_HEADING = re.compile(
    r"^####\s+(?P<id>\S+)\s+(?P<title>.+?)(?:\s+<!--\s*(?P<priority>P\d+)\s*-->)?\s*$"
)
SECTION_HEADING = re.compile(r"^###\s+\[图\]\s+(?P<screenshot>\S+\.png)\s+·\s+(?P<menu>.+)$")
PATH_QUOTE = re.compile(r"^>\s*路径：[`']?(?P<url>https?://[^\s`']+|`[^`]+`|[^\s`']+)[`']?\s*$")
CLICK_QUOTED = re.compile(r"[点点击][「「]([^」」]+)[」」]")

SCORE_POS = [
    (re.compile(r"点击|点「"), 15),
    (re.compile(r"输入|填写"), 15),
    (re.compile(r"搜索|重置|收起|展开"), 12),
    (re.compile(r"对话框|弹窗|抽屉"), 15),
    (re.compile(r"提交|确认|取消"), 12),
    (re.compile(r"勾选|全选"), 10),
    (re.compile(r"切换|选择"), 10),
    (re.compile(r"分页|条/页|条数"), 8),
    (re.compile(r"必填|校验|不能为空"), 12),
    (re.compile(r"删除"), 10),
]

SCORE_NEG = [
    (re.compile(r"截图对照"), 30),
    (re.compile(r"列展示-"), 25),
    (re.compile(r"样例行-"), 20),
    (re.compile(r"与截图一致|面包屑"), 15),
]

EXCLUDE_PAT = re.compile(r"无白屏|无 JS 错误|未捕获|JS 错误")
ERROR404_PAT = re.compile(r"error404|404", re.I)

TAG_PATS = [
    (re.compile(r"无权限|403|侧栏无入口"), "needs_role"),
    (re.compile(r"导出|下载"), "needs_download"),
    (re.compile(r"样例行"), "needs_data"),
]

PREFIX_BONUS = re.compile(r"-(C|V|X|U)\d")

TEMPLATE_HINTS = [
    (re.compile(r"筛选|搜索|重置"), "list_filter_search"),
    (re.compile(r"新增|修改|弹窗|对话框|抽屉"), "dialog_crud"),
    (re.compile(r"刷新|全屏|列设置|工具栏"), "toolbar_action"),
    (re.compile(r"分页|条/页"), "pagination"),
    (re.compile(r"勾选|批量"), "table_selection"),
    (re.compile(r"侧栏|导航"), "navigation"),
    (re.compile(r"URL 直达"), "page_load"),
]

KIND_TO_HINT = {
    "page": "list_filter_search",
    "list": "list_filter_search",
    "dialog": "dialog_crud",
    "modal": "dialog_crud",
    "panel": "toolbar_action",
}


def _basename(name: str) -> str:
    return Path(name.replace("\\", "/")).name


def _normalize_path(url: str) -> tuple[str, str]:
    url = url.strip().strip("`").strip("'").strip('"')
    if url.startswith("http"):
        parsed = urlparse(url)
        return parsed.path or "/", url
    if not url.startswith("/"):
        url = "/" + url
    return url, ""


def _tier_from_score(score: int) -> str:
    if score >= 60:
        return "A"
    if score >= 40:
        return "B"
    if score >= 20:
        return "C"
    return "exclude"


def _extract_click_targets(blob: str) -> list[str]:
    return [m.group(1).strip() for m in CLICK_QUOTED.finditer(blob)]


def _score_case(case_id: str, title: str, steps: list[str]) -> tuple[int, list[str], str]:
    blob = f"{case_id} {title} " + " ".join(steps)
    if EXCLUDE_PAT.search(blob):
        return 0, [], "exclude"

    score = 30
    tags: list[str] = []

    for pat, bonus in SCORE_POS:
        if pat.search(blob):
            score += bonus
    for pat, penalty in SCORE_NEG:
        if pat.search(blob):
            score -= penalty
    if PREFIX_BONUS.search(case_id):
        score += 8

    for pat, tag in TAG_PATS:
        if pat.search(blob):
            tags.append(tag)
            if tag == "needs_role":
                score -= 10

    score = max(0, min(100, score))
    tier = _tier_from_score(score)
    return score, tags, tier


def _template_hint(title: str, steps: list[str]) -> str:
    blob = title + " " + " ".join(steps)
    for pat, hint in TEMPLATE_HINTS:
        if pat.search(blob):
            return hint
    return "generic"


def load_manifest(path: Path) -> dict[str, dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data.get("items") if isinstance(data, dict) else data
    if not isinstance(items, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for it in items:
        if not isinstance(it, dict):
            continue
        fn = it.get("file") or ""
        key = _basename(fn)
        if key:
            out[key] = it
    return out


def _normalize_spec_entry(entry: dict[str, Any]) -> dict[str, Any]:
    spec = entry.get("spec") if isinstance(entry.get("spec"), dict) else {}
    page_type = (
        spec.get("page_type")
        or entry.get("page_type")
        or spec.get("kind")
        or entry.get("kind")
        or ""
    )
    return {
        "page_type": str(page_type).lower(),
        "filters": list(spec.get("filters") or entry.get("filters") or []),
        "actions": list(spec.get("actions") or entry.get("actions") or []),
        "columns": list(spec.get("columns") or entry.get("columns") or []),
        "fields_required": list(spec.get("fields_required") or entry.get("fields_required") or []),
        "row_actions": list(spec.get("row_actions") or entry.get("row_actions") or []),
        "image_path": entry.get("image_path") or spec.get("image_path") or "",
        "url": spec.get("url") or entry.get("url") or "",
        "menu": spec.get("menu") or entry.get("menu") or "",
        "trigger": spec.get("trigger") or entry.get("trigger") or "",
    }


def load_specs_json(path: Path) -> dict[str, dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for entry in data:
        if not isinstance(entry, dict):
            continue
        img = entry.get("image") or entry.get("file") or ""
        key = _basename(str(img))
        if key:
            out[key] = _normalize_spec_entry(entry)
    return out


def resolve_screenshot_path(screenshots_dir: Path | None, screenshot: str) -> tuple[str, bool]:
    if not screenshot:
        return "", False
    if not screenshots_dir:
        return "", False
    direct = screenshots_dir / screenshot
    if direct.is_file():
        return str(direct.resolve()), True
    # manifest 风格 pages/004-xxx.png
    for p in screenshots_dir.rglob(_basename(screenshot)):
        if p.is_file():
            return str(p.resolve()), True
    return str(direct), False


def enrich_case(
    case: dict[str, Any],
    *,
    manifest_by_image: dict[str, dict[str, Any]],
    specs_by_image: dict[str, dict[str, Any]],
    screenshots_dir: Path | None,
) -> dict[str, Any]:
    c = dict(case)
    score = int(c.get("score") or 0)
    tags = list(c.get("tags") or [])
    template_hint = c.get("template_hint") or "generic"
    ui_elements: dict[str, Any] = {}

    shot = c.get("screenshot") or ""
    shot_base = _basename(shot)
    blob = f"{c.get('case_id', '')} {c.get('title', '')} " + " ".join(c.get("steps") or [])

    # 截图文件
    shot_path, shot_ok = resolve_screenshot_path(screenshots_dir, shot)
    c["screenshot_path"] = shot_path
    c["screenshot_exists"] = shot_ok
    if screenshots_dir and shot and not shot_ok:
        score -= 15
        tags.append("missing_screenshot")

    # manifest
    mf = manifest_by_image.get(shot_base) or {}
    if mf:
        kind = str(mf.get("kind") or "").lower()
        status = str(mf.get("status") or "ok").lower()
        c["page_kind"] = kind
        c["capture_status"] = status
        if kind:
            template_hint = KIND_TO_HINT.get(kind, template_hint)
        if status != "ok" or ERROR404_PAT.search(kind) or ERROR404_PAT.search(str(mf.get("file") or "")):
            score = min(score, 15)
            tags.append("page_unavailable")
        if mf.get("url") and not c.get("page_url"):
            c["page_url"] = mf["url"]
            pp, _ = _normalize_path(str(mf["url"]))
            if pp:
                c["page_path"] = pp
        if mf.get("trigger"):
            ui_elements["trigger"] = mf["trigger"]

    # specs JSON
    sp = specs_by_image.get(shot_base) or {}
    if sp:
        ui_elements = {
            "page_type": sp.get("page_type"),
            "filters": sp.get("filters") or [],
            "actions": sp.get("actions") or [],
            "columns": sp.get("columns") or [],
            "fields_required": sp.get("fields_required") or [],
            "row_actions": sp.get("row_actions") or [],
        }
        if sp.get("image_path") and not c.get("screenshot_path"):
            c["screenshot_path"] = sp["image_path"]
            c["screenshot_exists"] = Path(sp["image_path"]).is_file()

        pt = sp.get("page_type") or ""
        if pt in KIND_TO_HINT:
            template_hint = KIND_TO_HINT[pt]

        filters = sp.get("filters") or []
        actions = sp.get("actions") or []
        columns = sp.get("columns") or []

        if re.search(r"筛选|搜索", blob) and filters:
            score += 8
            template_hint = "list_filter_search"
            tags.append("filter_verified")

        if re.search(r"列展示-", title := c.get("title") or ""):
            col_name = title.split("列展示-", 1)[-1].strip()
            if col_name and col_name in columns:
                score = min(score, 35)
                tags.append("column_display_merge")

        click_targets = _extract_click_targets(blob)
        for target in click_targets:
            pool = actions + (sp.get("row_actions") or [])
            if any(target in a or a in target for a in pool):
                score += 8
                tags.append("action_verified")
            elif pool:
                score -= 12
                tags.append("stale_action")

        if re.search(r"新增|修改", blob) and (actions or sp.get("fields_required")):
            template_hint = "dialog_crud"

    # 去重 tags
    tags = list(dict.fromkeys(tags))
    score = max(0, min(100, score))
    tier = _tier_from_score(score)
    if "page_unavailable" in tags:
        tier = "exclude"

    c["score"] = score
    c["tier"] = tier
    c["tags"] = tags
    c["template_hint"] = template_hint
    c["ui_elements"] = ui_elements
    c["automation_ready"] = tier in ("A", "B")
    c["enriched"] = bool(mf or sp or shot_ok)
    return c


def parse_markdown(text: str) -> list[dict[str, Any]]:
    lines = text.splitlines()
    cases: list[dict[str, Any]] = []

    screenshot = ""
    menu_path = ""
    page_path = ""
    page_url = ""

    i = 0
    while i < len(lines):
        line = lines[i]

        sec = SECTION_HEADING.match(line)
        if sec:
            screenshot = sec.group("screenshot")
            menu_path = sec.group("menu").strip()
            page_path = ""
            page_url = ""
            i += 1
            continue

        pq = PATH_QUOTE.match(line)
        if pq:
            page_path, page_url = _normalize_path(pq.group("url"))
            i += 1
            continue

        m = CASE_HEADING.match(line)
        if m:
            case_id = m.group("id")
            title = m.group("title").strip()
            priority = m.group("priority") or "P2"
            steps: list[str] = []
            i += 1
            while i < len(lines):
                nxt = lines[i]
                if nxt.startswith("#### ") or nxt.startswith("### ") or nxt.startswith("## "):
                    break
                if nxt.startswith("- "):
                    steps.append(nxt[2:].strip())
                i += 1

            score, tags, tier = _score_case(case_id, title, steps)
            cases.append(
                {
                    "case_id": case_id,
                    "title": title,
                    "priority": priority,
                    "tier": tier,
                    "score": score,
                    "screenshot": screenshot,
                    "menu_path": menu_path,
                    "page_path": page_path,
                    "page_url": page_url,
                    "steps": steps,
                    "tags": tags,
                    "template_hint": _template_hint(title, steps),
                    "automation_ready": tier in ("A", "B"),
                    "screenshot_path": "",
                    "screenshot_exists": False,
                    "page_kind": "",
                    "capture_status": "",
                    "ui_elements": {},
                    "enriched": False,
                }
            )
            continue

        i += 1

    return cases


def filter_cases(
    cases: list[dict[str, Any]],
    *,
    tiers: set[str] | None,
    priorities: set[str] | None,
    modules: list[str] | None,
    limit: int | None,
    require_screenshot: bool,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for c in cases:
        if require_screenshot and not c.get("screenshot_exists"):
            continue
        if tiers and c["tier"] not in tiers:
            continue
        if priorities and c["priority"] not in priorities:
            continue
        if modules:
            hay = f"{c['case_id']} {c['menu_path']} {c['title']}"
            if not any(m in hay for m in modules):
                continue
        if c["tier"] == "exclude" and tiers and "exclude" not in tiers:
            continue
        out.append(c)
    out.sort(key=lambda x: (-x["score"], x["case_id"]))
    if limit and limit > 0:
        out = out[:limit]
    return out


def build_stats(
    all_cases: list[dict[str, Any]],
    filtered: list[dict[str, Any]],
    *,
    enrichment_used: bool,
) -> dict[str, Any]:
    tier_all = Counter(c["tier"] for c in all_cases)
    return {
        "total": len(all_cases),
        "candidates": sum(1 for c in all_cases if c["tier"] in ("A", "B", "C")),
        "tier_a": tier_all.get("A", 0),
        "tier_b": tier_all.get("B", 0),
        "tier_c": tier_all.get("C", 0),
        "excluded": tier_all.get("exclude", 0),
        "filtered_count": len(filtered),
        "enrichment_used": enrichment_used,
        "screenshot_verified": sum(1 for c in all_cases if c.get("screenshot_exists")),
        "action_verified": sum(1 for c in all_cases if "action_verified" in (c.get("tags") or [])),
        "stale_action": sum(1 for c in all_cases if "stale_action" in (c.get("tags") or [])),
        "page_unavailable": sum(1 for c in all_cases if "page_unavailable" in (c.get("tags") or [])),
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "case_id",
        "title",
        "priority",
        "tier",
        "score",
        "screenshot",
        "screenshot_exists",
        "page_kind",
        "page_path",
        "menu_path",
        "template_hint",
        "tags",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            row = {k: r.get(k, "") for k in fields}
            row["tags"] = ",".join(r.get("tags") or [])
            w.writerow(row)


def write_summary(
    path: Path,
    stats: dict[str, Any],
    filtered: list[dict[str, Any]],
    inputs: dict[str, str],
) -> None:
    by_page = Counter(
        (c["page_path"] or c["menu_path"] or "(unknown)", c["tier"])
        for c in filtered
        if c["tier"] in ("A", "B")
    )
    page_scores: dict[str, int] = {}
    for (page, tier), _ in by_page.items():
        page_scores[page] = page_scores.get(page, 0) + (2 if tier == "A" else 1)
    top_pages = sorted(page_scores.items(), key=lambda x: -x[1])[:15]

    lines = [
        "# UI 自动化候选筛选摘要",
        "",
        f"- 生成时间：{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"- 用例源：`{inputs.get('markdown', '')}`",
        f"- 三件套增强：{'是' if stats.get('enrichment_used') else '否'}",
        "",
        "## 统计",
        "",
        f"- 总用例：{stats['total']}",
        f"- 候选（A+B+C）：{stats['candidates']}",
        f"- A 档：{stats['tier_a']} · B 档：{stats['tier_b']} · C 档：{stats['tier_c']}",
        f"- 排除：{stats['excluded']}",
        f"- 本次输出：{stats['filtered_count']} 条",
        "",
    ]
    if stats.get("enrichment_used"):
        lines.extend(
            [
                "## 三件套交叉验证",
                "",
                f"- 截图文件已校验：{stats.get('screenshot_verified', 0)} 条",
                f"- 动作与页面 spec 一致（action_verified）：{stats.get('action_verified', 0)} 条",
                f"- 动作疑似过期（stale_action）：{stats.get('stale_action', 0)} 条",
                f"- 页面不可用（404/失败截图）：{stats.get('page_unavailable', 0)} 条",
                "",
            ]
        )
    if inputs.get("manifest"):
        lines.append(f"- manifest：`{inputs['manifest']}`")
    if inputs.get("specs_json"):
        lines.append(f"- specs JSON：`{inputs['specs_json']}`")
    if inputs.get("screenshots_dir"):
        lines.append(f"- 截图目录：`{inputs['screenshots_dir']}`")
    lines.extend(["", "## 建议首期页面（A/B 加权 Top）", ""])
    for page, weight in top_pages:
        lines.append(f"- `{page}`（权重 {weight}）")
    lines.extend(
        [
            "",
            "## 首期建议",
            "",
            "- 优先 `action_verified` + `dialog_crud` / `list_filter_search`",
            "- `stale_action` 先人工核对用例或截图 spec 是否过期",
            "- 每页一个 pytest 文件，5～15 个 test_*",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-i", "--input", type=Path, required=True, help="Markdown 用例文件")
    ap.add_argument("-o", "--output", type=Path, required=True, help="输出 JSON 路径")
    ap.add_argument("--manifest", type=Path, help="截图 manifest.json（screenshot-skills 产出）")
    ap.add_argument("--specs-json", type=Path, help="按图聚合的 ui_cases_by_image.json")
    ap.add_argument("--screenshots-dir", type=Path, help="PNG 目录，校验截图是否存在")
    ap.add_argument("--tier", default="", help="档位过滤，逗号分隔，如 A,B")
    ap.add_argument("--priority", default="P0,P1", help="优先级过滤，逗号分隔；空=不过滤")
    ap.add_argument("--module", default="", help="菜单/模块关键词，逗号分隔")
    ap.add_argument("--limit", type=int, default=0, help="最多输出条数，0=不限")
    ap.add_argument("--require-screenshot", action="store_true", help="仅保留截图文件存在的用例")
    ap.add_argument("--summary", action="store_true", help="额外写 _summary.md")
    ns = ap.parse_args()

    def _resolve(p: Path | None) -> Path | None:
        if not p:
            return None
        return p if p.is_absolute() else (ROOT / p).resolve()

    inp = _resolve(ns.input)
    out = _resolve(ns.output)
    manifest_path = _resolve(ns.manifest)
    specs_path = _resolve(ns.specs_json)
    shots_dir = _resolve(ns.screenshots_dir)

    if not inp or not inp.is_file():
        print(f"输入不存在: {inp}", file=sys.stderr)
        return 1

    manifest_by_image: dict[str, dict[str, Any]] = {}
    specs_by_image: dict[str, dict[str, Any]] = {}
    enrichment_used = False

    if manifest_path and manifest_path.is_file():
        manifest_by_image = load_manifest(manifest_path)
        enrichment_used = True
    if specs_path and specs_path.is_file():
        specs_by_image = load_specs_json(specs_path)
        enrichment_used = True
    if shots_dir and shots_dir.is_dir():
        enrichment_used = True

    text = inp.read_text(encoding="utf-8")
    raw_cases = parse_markdown(text)
    all_cases = [
        enrich_case(
            c,
            manifest_by_image=manifest_by_image,
            specs_by_image=specs_by_image,
            screenshots_dir=shots_dir,
        )
        for c in raw_cases
    ]

    tiers = {t.strip().upper() for t in ns.tier.split(",") if t.strip()} or None
    priorities = {p.strip().upper() for p in ns.priority.split(",") if p.strip()} if ns.priority else None
    modules = [m.strip() for m in ns.module.split(",") if m.strip()] or None
    limit = ns.limit if ns.limit > 0 else None

    filtered = filter_cases(
        all_cases,
        tiers=tiers,
        priorities=priorities,
        modules=modules,
        limit=limit,
        require_screenshot=ns.require_screenshot,
    )
    stats = build_stats(all_cases, filtered, enrichment_used=enrichment_used)

    payload = {
        "source": str(inp),
        "inputs": {
            "markdown": str(inp),
            "manifest": str(manifest_path) if manifest_path else "",
            "specs_json": str(specs_path) if specs_path else "",
            "screenshots_dir": str(shots_dir) if shots_dir else "",
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stats": stats,
        "candidates": filtered,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    csv_path = out.with_suffix(".csv")
    write_csv(csv_path, filtered)
    if ns.summary:
        write_summary(
            out.with_name(out.stem + "_summary.md"),
            stats,
            filtered,
            payload["inputs"],
        )

    extra = ""
    if enrichment_used:
        extra = (
            f"\n  三件套: 截图校验={stats['screenshot_verified']} "
            f"action_verified={stats['action_verified']} "
            f"stale={stats['stale_action']} unavailable={stats['page_unavailable']}"
        )
    print(
        f"已写入: {out} ({stats['filtered_count']} 条)\n"
        f"  CSV: {csv_path}\n"
        f"  总计 {stats['total']} | A={stats['tier_a']} B={stats['tier_b']} "
        f"C={stats['tier_c']} 排除={stats['excluded']}{extra}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
