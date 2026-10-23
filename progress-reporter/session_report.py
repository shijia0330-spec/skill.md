"""
pytest 会话结束后汇总通过/失败/跳过与耗时，输出终端摘要与 Markdown/JSON 报告。

环境变量：
  PROGRESS_REPORT=1|0       默认 1，设为 0 关闭
  PROGRESS_REPORT_DIR       默认 <引擎根>/output/reports
  PROGRESS_REPORT_FORMATS   默认 terminal,markdown,json（逗号分隔）
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

ENGINE_ROOT = Path(__file__).resolve().parent.parent


def _report_enabled() -> bool:
    return os.environ.get("PROGRESS_REPORT", "1").strip().lower() not in ("0", "false", "no", "off")


def resolve_report_dir() -> Path:
    raw = os.environ.get("PROGRESS_REPORT_DIR", "").strip()
    if raw:
        p = Path(raw)
        return p if p.is_absolute() else (ENGINE_ROOT / p)
    return ENGINE_ROOT / "output" / "reports"


def _parse_formats() -> set[str]:
    raw = os.environ.get("PROGRESS_REPORT_FORMATS", "terminal,markdown,json").strip()
    return {x.strip().lower() for x in raw.split(",") if x.strip()}


@dataclass
class CaseResult:
    nodeid: str
    status: str  # passed | failed | skipped | error
    duration: float = 0.0
    error: str = ""


@dataclass
class SessionSummary:
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    duration: float = 0.0
    cases: list[CaseResult] = field(default_factory=list)

    @property
    def executed(self) -> int:
        return self.passed + self.failed + self.errors

    @property
    def pass_rate(self) -> float:
        if self.executed == 0:
            return 0.0
        return round(100.0 * self.passed / self.executed, 1)


class SessionProgressReporter:
    """收集用例结果并生成进度报告。"""

    def __init__(self) -> None:
        self._cases: list[CaseResult] = []

    def add_result(
        self,
        test_name: str,
        status: str,
        duration: float = 0.0,
        error: str = "",
    ) -> None:
        self._cases.append(
            CaseResult(
                nodeid=test_name,
                status=status.lower(),
                duration=float(duration or 0),
                error=(error or "").strip(),
            )
        )

    def summarize(self) -> SessionSummary:
        summary = SessionSummary(cases=list(self._cases))
        for c in self._cases:
            summary.total += 1
            summary.duration += c.duration
            if c.status == "passed":
                summary.passed += 1
            elif c.status == "failed":
                summary.failed += 1
            elif c.status == "skipped":
                summary.skipped += 1
            else:
                summary.errors += 1
        return summary

    def build_summary_from_session(self, session_items: list[Any]) -> SessionSummary:
        """从 pytest session.items（含 rep_setup / rep_call）构建汇总。"""
        self._cases.clear()
        for item in session_items:
            rep_setup = getattr(item, "rep_setup", None)
            rep_call = getattr(item, "rep_call", None)

            if rep_setup is not None and rep_setup.skipped:
                self._record_pytest_report(item.nodeid, rep_setup, "skipped")
                continue
            if rep_setup is not None and rep_setup.failed:
                self._record_pytest_report(item.nodeid, rep_setup, "failed")
                continue

            if rep_call is None:
                continue
            if rep_call.skipped:
                self._record_pytest_report(item.nodeid, rep_call, "skipped")
            elif rep_call.failed:
                self._record_pytest_report(item.nodeid, rep_call, "failed")
            elif rep_call.passed:
                self._record_pytest_report(item.nodeid, rep_call, "passed")

        return self.summarize()

    def _record_pytest_report(self, nodeid: str, rep: Any, status: str) -> None:
        duration = float(rep.duration) if getattr(rep, "duration", None) is not None else 0.0
        error = ""
        if status == "failed" and rep.longrepr is not None:
            error = str(rep.longrepr)
            if len(error) > 2000:
                error = error[:2000] + "\n…(truncated)"
        self.add_result(nodeid, status, duration, error)

    def format_terminal_report(self, summary: SessionSummary | None = None) -> str:
        s = summary or self.summarize()
        lines = [
            "========================================",
            "测试进度报告",
            "========================================",
            f"总计: {s.total}  |  通过: {s.passed}  |  失败: {s.failed}  |  跳过: {s.skipped}",
            f"通过率: {s.pass_rate}%",
            f"总耗时: {s.duration:.1f}s",
        ]
        failed_cases = [c for c in s.cases if c.status in ("failed", "error")]
        if failed_cases:
            lines.append("")
            lines.append("失败用例:")
            for c in failed_cases:
                short = c.nodeid.split("::")[-1] if "::" in c.nodeid else c.nodeid
                lines.append(f"  {short}")
                if c.error:
                    first_line = c.error.strip().splitlines()[0]
                    lines.append(f"    {first_line[:120]}")
        lines.append("========================================")
        return "\n".join(lines)

    def generate_markdown_report(self, path: Path, summary: SessionSummary | None = None) -> Path:
        s = summary or self.summarize()
        path.parent.mkdir(parents=True, exist_ok=True)
        failed = [c for c in s.cases if c.status in ("failed", "error")]
        skipped = [c for c in s.cases if c.status == "skipped"]

        body = [
            "# 测试进度报告",
            "",
            f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "| 指标 | 数值 |",
            "|------|------|",
            f"| 总用例数 | {s.total} |",
            f"| 通过 | {s.passed} |",
            f"| 失败 | {s.failed} |",
            f"| 跳过 | {s.skipped} |",
            f"| 通过率 | {s.pass_rate}% |",
            f"| 总耗时 | {s.duration:.1f}s |",
            "",
        ]

        if failed:
            body.append("## 失败用例")
            body.append("")
            for c in failed:
                title = c.nodeid.split("::")[-1] if "::" in c.nodeid else c.nodeid
                body.append(f"### {title}")
                body.append(f"- **nodeid**: `{c.nodeid}`")
                body.append(f"- **耗时**: {c.duration:.2f}s")
                if c.error:
                    body.append(f"- **错误**:")
                    body.append("")
                    body.append("```")
                    body.append(c.error)
                    body.append("```")
                body.append("")

        if skipped:
            body.append("## 跳过用例")
            body.append("")
            for c in skipped:
                body.append(f"- `{c.nodeid}` ({c.duration:.2f}s)")
            body.append("")

        path.write_text("\n".join(body), encoding="utf-8")
        return path

    def generate_json_report(self, path: Path, summary: SessionSummary | None = None) -> Path:
        s = summary or self.summarize()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "total": s.total,
            "passed": s.passed,
            "failed": s.failed,
            "skipped": s.skipped,
            "errors": s.errors,
            "pass_rate": s.pass_rate,
            "duration_seconds": round(s.duration, 3),
            "cases": [
                {
                    "nodeid": c.nodeid,
                    "status": c.status,
                    "duration": round(c.duration, 3),
                    "error": c.error,
                }
                for c in s.cases
            ],
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def write_all(
        self,
        session_items: list[Any] | None = None,
        *,
        summary: SessionSummary | None = None,
    ) -> dict[str, Path | str]:
        """生成配置要求的全部报告，返回产物路径。"""
        if summary is None:
            if session_items is not None:
                summary = self.build_summary_from_session(session_items)
            else:
                summary = self.summarize()

        formats = _parse_formats()
        out_dir = resolve_report_dir()
        written: dict[str, Path | str] = {}

        if "terminal" in formats:
            written["terminal"] = self.format_terminal_report(summary)

        if "markdown" in formats:
            md_path = out_dir / "progress.md"
            written["markdown"] = self.generate_markdown_report(md_path, summary)

        if "json" in formats:
            json_path = out_dir / "progress.json"
            written["json"] = self.generate_json_report(json_path, summary)

        return written


def _summary_from_terminal_reporter(session: Any) -> SessionSummary | None:
    """session.items 无 rep_call 时（如 rootdir 异常），回退 terminalreporter 统计。"""
    tr = session.config.pluginmanager.get_plugin("terminalreporter")
    if tr is None:
        return None
    stats = getattr(tr, "stats", None) or {}
    summary = SessionSummary()
    for key, status in (("passed", "passed"), ("failed", "failed"), ("skipped", "skipped"), ("error", "error")):
        for rep in stats.get(key, []):
            nodeid = getattr(rep, "nodeid", "") or ""
            if not nodeid:
                continue
            dur = float(getattr(rep, "duration", 0.0) or 0.0)
            err = ""
            if status in ("failed", "error") and getattr(rep, "longrepr", None):
                err = str(rep.longrepr)
                if len(err) > 2000:
                    err = err[:2000] + "\n…(truncated)"
            summary.cases.append(CaseResult(nodeid=nodeid, status=status, duration=dur, error=err))
    if not summary.cases:
        return None
    summary.total = len(summary.cases)
    summary.duration = sum(c.duration for c in summary.cases)
    for c in summary.cases:
        if c.status == "passed":
            summary.passed += 1
        elif c.status == "failed":
            summary.failed += 1
        elif c.status == "skipped":
            summary.skipped += 1
        else:
            summary.errors += 1
    return summary


def process_session(session: Any) -> dict[str, Path | str]:
    """pytest_sessionfinish 入口。"""
    if not _report_enabled():
        return {}
    reporter = SessionProgressReporter()
    summary = reporter.build_summary_from_session(list(session.items))
    if summary.total == 0:
        alt = _summary_from_terminal_reporter(session)
        if alt is not None:
            summary = alt
    return reporter.write_all(summary=summary)


if __name__ == "__main__":
    demo = SessionProgressReporter()
    demo.add_result("test_login", "passed", 1.2)
    demo.add_result("test_register", "failed", 0.8, "AssertionError: expected 200, got 400")
    demo.add_result("test_skip_demo", "skipped", 0.0)
    print(demo.format_terminal_report())
    out = resolve_report_dir()
    demo.generate_markdown_report(out / "progress_demo.md")
    demo.generate_json_report(out / "progress_demo.json")
    print(f"Demo written to {out}")
