#!/usr/bin/env python3
"""
缺陷同步入口脚本

用法：
    python defect_sync.py push output/bugs/ --platform zentao --dry-run
    python defect_sync.py push output/bugs/BUG-20260627-001_xxx.md --platform custom --confirm
    python defect_sync.py status output/bugs/
    python defect_sync.py preview output/bugs/ --platform yunxiao
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from canonical import load_defects_from_path  # noqa: E402
from sync_service import format_report, push_defects  # noqa: E402
from sync_state import SyncState  # noqa: E402
from adapters import create_adapter, ADAPTERS  # noqa: E402


def cmd_push(args: argparse.Namespace) -> int:
    severity = [s.strip() for s in args.severity.split(",") if s.strip()] if args.severity else None
    state_path = Path(args.state) if args.state else None
    report = push_defects(
        Path(args.target),
        args.platform,
        dry_run=args.dry_run,
        confirm=args.confirm,
        skip_env=not args.include_env,
        severity_filter=severity,
        state_path=state_path,
        notify=args.notify,
    )
    print(format_report(report))
    if args.json:
        print(json.dumps(report.details, ensure_ascii=False, indent=2))
    return 1 if report.failed else 0


def cmd_preview(args: argparse.Namespace) -> int:
    adapter = create_adapter(args.platform)
    missing = adapter.validate_config()
    if missing:
        print(f"⚠ 配置缺失（dry-run 仍可预览映射）: {', '.join(missing)}")
    defects = load_defects_from_path(Path(args.target))
    for d in defects:
        payload = adapter.map_defect(d)
        print(f"\n--- {d.bug_id}: {d.title} ---")
        print(f"  fingerprint: {d.fingerprint}")
        print(f"  triage: {d.triage} | status: {d.status}")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    state_path = Path(args.state) if args.state else None
    state = SyncState(state_path)
    records = state._data.get("records", {})
    if not records:
        print("暂无同步记录")
        return 0
    print(f"同步记录 ({len(records)} 条):")
    for fp, rec in records.items():
        print(
            f"  {rec.get('bug_id')} → {rec.get('platform')} #{rec.get('remote_id')} "
            f"({rec.get('synced_at', '')})"
        )
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    adapter = create_adapter(args.platform)
    missing = adapter.validate_config()
    if missing:
        print(f"[FAIL] 平台 {args.platform} 配置不完整，缺少: {', '.join(missing)}")
        return 1
    print(f"[OK] 平台 {args.platform} 配置完整")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="缺陷同步引擎 — 推送草稿到禅道/云效/自研平台")
    sub = parser.add_subparsers(dest="command", required=True)

    p_push = sub.add_parser("push", help="推送缺陷到远端平台")
    p_push.add_argument("target", help="缺陷 Markdown 文件或 bugs/ 目录")
    p_push.add_argument("--platform", "-p", required=True, choices=sorted(ADAPTERS.keys()))
    p_push.add_argument("--dry-run", action="store_true", help="仅预览，不实际推送")
    p_push.add_argument("--confirm", action="store_true", help="确认推送 Draft 状态草稿")
    p_push.add_argument("--include-env", action="store_true", help="包含「环境」分流缺陷")
    p_push.add_argument("--severity", default="", help="仅推送指定严重级别，逗号分隔，如 High,Critical")
    p_push.add_argument("--state", default="", help="sync_state.json 路径")
    p_push.add_argument("--notify", action="store_true", help="推送成功后发飞书通知")
    p_push.add_argument("--json", action="store_true", help="额外输出 JSON 详情")
    p_push.set_defaults(func=cmd_push)

    p_preview = sub.add_parser("preview", help="预览字段映射结果")
    p_preview.add_argument("target", help="缺陷 Markdown 文件或 bugs/ 目录")
    p_preview.add_argument("--platform", "-p", required=True, choices=sorted(ADAPTERS.keys()))
    p_preview.set_defaults(func=cmd_preview)

    p_status = sub.add_parser("status", help="查看同步状态")
    p_status.add_argument("target", nargs="?", default="", help="（可选）bugs 目录")
    p_status.add_argument("--state", default="", help="sync_state.json 路径")
    p_status.set_defaults(func=cmd_status)

    p_check = sub.add_parser("check", help="检查平台配置是否完整")
    p_check.add_argument("--platform", "-p", required=True, choices=sorted(ADAPTERS.keys()))
    p_check.set_defaults(func=cmd_check)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
