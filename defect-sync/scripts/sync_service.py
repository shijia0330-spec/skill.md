"""缺陷同步主服务"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(__file__))

from adapters import create_adapter  # noqa: E402
from adapters.feishu import notify_feishu  # noqa: E402
from canonical import CanonicalDefect, load_defects_from_path  # noqa: E402
from sync_state import SyncState  # noqa: E402


ENGINE_ROOT = Path(__file__).resolve().parent.parent.parent
SKIP_TRIAGE = {"环境"}


@dataclass
class SyncReport:
    total: int = 0
    pushed: int = 0
    skipped: int = 0
    failed: int = 0
    dry_run: bool = False
    details: list[dict[str, Any]] = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.details is None:
            self.details = []


def _should_skip(defect: CanonicalDefect, *, skip_draft: bool, skip_env: bool) -> str | None:
    if skip_draft and defect.status.lower() == "draft":
        return "状态为 Draft，需 --confirm 确认后推送"
    if skip_env and defect.triage in SKIP_TRIAGE:
        return f"分流为「{defect.triage}」，跳过自动推送"
    return None


def _severity_allowed(severity: str, allowed: list[str] | None) -> bool:
    if not allowed:
        return True
    return severity.lower() in {s.lower() for s in allowed}


def push_defects(
    target: Path,
    platform: str,
    *,
    dry_run: bool = False,
    confirm: bool = False,
    skip_env: bool = True,
    severity_filter: list[str] | None = None,
    state_path: Path | None = None,
    notify: bool = False,
) -> SyncReport:
    adapter = create_adapter(platform)
    missing = adapter.validate_config()
    if missing and not dry_run:
        raise RuntimeError(f"平台 {platform} 配置缺失: {', '.join(missing)}")

    defects = load_defects_from_path(target)
    state = SyncState(state_path)
    report = SyncReport(total=len(defects), dry_run=dry_run)
    batch_seen: dict[str, str] = {}

    for defect in defects:
        detail: dict[str, Any] = {
            "bug_id": defect.bug_id,
            "title": defect.title,
            "fingerprint": defect.fingerprint,
        }
        if defect.analysis_block():
            detail["analysis"] = defect.analysis_block()

        skip_reason = _should_skip(defect, skip_draft=not confirm, skip_env=skip_env)
        if skip_reason:
            detail["action"] = "skipped"
            detail["reason"] = skip_reason
            report.skipped += 1
            report.details.append(detail)
            continue

        if not _severity_allowed(defect.severity, severity_filter):
            detail["action"] = "skipped"
            detail["reason"] = f"严重级别 {defect.severity} 不在过滤范围"
            report.skipped += 1
            report.details.append(detail)
            continue

        if defect.fingerprint and defect.fingerprint in batch_seen:
            detail["action"] = "skipped"
            detail["reason"] = f"本批重复指纹（同 {batch_seen[defect.fingerprint]}）"
            report.skipped += 1
            report.details.append(detail)
            continue

        if state.is_synced(defect.fingerprint, platform):
            rec = state.get(defect.fingerprint)
            detail["action"] = "skipped"
            detail["reason"] = f"已同步过 → {platform} #{rec.get('remote_id')}"
            detail["remote_url"] = rec.get("remote_url", "")
            report.skipped += 1
            report.details.append(detail)
            continue

        result = adapter.push(defect, dry_run=dry_run)
        detail["payload"] = result.payload

        if result.success:
            detail["action"] = "dry-run" if dry_run else "pushed"
            detail["message"] = result.message
            detail["remote_id"] = result.remote_id
            detail["remote_url"] = result.remote_url
            report.pushed += 1
            if defect.fingerprint:
                batch_seen[defect.fingerprint] = defect.bug_id
            if not dry_run and result.remote_id:
                state.record(
                    defect.fingerprint,
                    bug_id=defect.bug_id,
                    platform=platform,
                    remote_id=result.remote_id,
                    remote_url=result.remote_url,
                    source_file=defect.source_file,
                )
                if notify:
                    ok, msg = notify_feishu(
                        title=f"缺陷已同步 → {platform}",
                        content=(
                            f"**{defect.title}**\n"
                            f"编号: {defect.bug_id}\n"
                            f"远端: #{result.remote_id}\n"
                            f"链接: {result.remote_url or '—'}"
                        ),
                    )
                    detail["feishu"] = msg if ok else f"通知失败: {msg}"
        else:
            detail["action"] = "failed"
            detail["reason"] = result.message
            report.failed += 1

        report.details.append(detail)

    return report


def sync_after_pytest(draft_paths: list[Path]) -> SyncReport | None:
    """pytest 会话结束后可选自动同步（由 conftest 调用）"""
    if os.environ.get("DEFECT_SYNC", "").strip().lower() not in ("1", "true", "yes", "on"):
        return None
    platform = os.environ.get("DEFECT_SYNC_PLATFORM", "custom").strip()
    if not draft_paths:
        return None

    parent = draft_paths[0].parent
    confirm = os.environ.get("DEFECT_SYNC_CONFIRM", "").strip().lower() in ("1", "true", "yes")
    severity_raw = os.environ.get("DEFECT_SYNC_SEVERITY", "").strip()
    severity_filter = [s.strip() for s in severity_raw.split(",") if s.strip()] or None
    notify = os.environ.get("DEFECT_SYNC_NOTIFY", "").strip().lower() in ("1", "true", "yes")

    return push_defects(
        parent,
        platform,
        dry_run=False,
        confirm=confirm,
        skip_env=True,
        severity_filter=severity_filter,
        notify=notify,
    )


def format_report(report: SyncReport) -> str:
    lines = [
        f"{'[DRY-RUN] ' if report.dry_run else ''}缺陷同步报告",
        f"  总计: {report.total}  推送: {report.pushed}  跳过: {report.skipped}  失败: {report.failed}",
        "",
    ]
    for d in report.details:
        action = d.get("action", "?")
        bug_id = d.get("bug_id", "")
        if action == "pushed":
            lines.append(f"  [OK] {bug_id} → #{d.get('remote_id')} {d.get('remote_url', '')}")
        elif action == "dry-run":
            lines.append(f"  [SEARCH] {bug_id} [dry-run] {d.get('title', '')[:40]}")
        elif action == "skipped":
            lines.append(f"  ⏭  {bug_id} — {d.get('reason', '')}")
        else:
            lines.append(f"  [FAIL] {bug_id} — {d.get('reason', '')}")
    return "\n".join(lines)
