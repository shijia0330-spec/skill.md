"""
pytest 会话结束后，对失败用例做 5 大类根因分析 + 置信度 + 指纹去重。

环境变量：
  FAILURE_ANALYSIS=1|0       默认 1，设为 0 关闭
  FAILURE_ANALYSIS_DIR       默认 <引擎根>/output/reports
  FAILURE_ANALYSIS_FORMATS   默认 json,markdown（逗号分隔）
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

ENGINE_ROOT = Path(__file__).resolve().parent.parent

CATEGORIES = ("env", "data", "code", "test_design", "unknown")

CATEGORY_LABELS = {
    "env": "环境",
    "data": "数据",
    "code": "代码",
    "test_design": "测试设计",
    "unknown": "未知",
}


def _analysis_enabled() -> bool:
    return os.environ.get("FAILURE_ANALYSIS", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def resolve_analysis_dir() -> Path:
    raw = os.environ.get("FAILURE_ANALYSIS_DIR", "").strip()
    if raw:
        p = Path(raw)
        return p if p.is_absolute() else (ENGINE_ROOT / p)
    return ENGINE_ROOT / "output" / "reports"


def _parse_formats() -> set[str]:
    raw = os.environ.get("FAILURE_ANALYSIS_FORMATS", "json,markdown").strip()
    return {x.strip().lower() for x in raw.split(",") if x.strip()}


def compute_fingerprint(nodeid: str, body: str) -> str:
    """与 defect-sync/canonical.py 一致。"""
    status_code = ""
    for code in ("500", "401", "403", "404", "422", "502", "503"):
        if code in body:
            status_code = code
            break
    error_snippet = re.sub(r"\s+", " ", body)[:50]
    raw = f"{nodeid}|{status_code}|{error_snippet}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _is_ui_failure(nodeid: str, longrepr: str) -> bool:
    blob = f"{nodeid}\n{longrepr}".lower()
    ui_markers = (
        "playwright",
        "page.",
        "locator",
        "get_by_role",
        "get_by_label",
        "fill_with_heal",
        "click_with_heal",
        "chromium",
        "screenshot",
    )
    return any(m in blob for m in ui_markers)


@dataclass
class FailureAnalysis:
    nodeid: str
    category: str
    confidence: float
    root_cause: str
    suggestion: str
    fingerprint: str
    severity: str = "Medium"
    duplicate_of: str | None = None
    pending_confirm: bool = False
    auto_bug: bool = False
    duration_s: float | None = None
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodeid": self.nodeid,
            "category": self.category,
            "category_label": CATEGORY_LABELS.get(self.category, self.category),
            "confidence": round(self.confidence, 2),
            "root_cause": self.root_cause,
            "suggestion": self.suggestion,
            "fingerprint": self.fingerprint,
            "severity": self.severity,
            "duplicate_of": self.duplicate_of,
            "pending_confirm": self.pending_confirm,
            "auto_bug": self.auto_bug,
            "duration_seconds": self.duration_s,
            "evidence": self.evidence,
        }


def _match_rules(text: str, nodeid: str) -> tuple[str, float, str, str, list[str], str]:
    """返回 category, confidence, root_cause, suggestion, evidence, severity。"""
    lower = text.lower()
    is_ui = _is_ui_failure(nodeid, text)
    evidence: list[str] = []

    if is_ui and (
        "locator" in lower
        or "定位失败" in lower
        or "fill_with_heal" in lower
        or "click_with_heal" in lower
        or "runtimeerror" in lower
    ):
        return (
            "test_design",
            0.72,
            "UI 定位或操作失败",
            "先 @UI-skills/自我修复；确认 TEST_BASE_URL 是否指向 Web 前端（非纯 API 端口）",
            ["ui", "locator"],
            "High",
        )

    env_rules: list[tuple[tuple[str, ...], float, str, str, str]] = [
        (
            ("connection refused", "connectionerror", "errno 111", "errno 61"),
            0.92,
            "测试环境不可达或服务未启动",
            "检查 TEST_BASE_URL、后端进程与网络",
            "Medium",
        ),
        (
            ("max retries exceeded", "network is unreachable", "name or service not known"),
            0.88,
            "网络或服务发现失败",
            "确认 DNS、代理与防火墙",
            "Medium",
        ),
        (
            ("401", "unauthorized", "token expired", "invalid token"),
            0.82,
            "认证失效或 Token 过期",
            "重新登录或刷新 Token；检查 TEST_USERNAME/TEST_PASSWORD",
            "Medium",
        ),
        (
            ("429", "too many requests", "rate limit"),
            0.8,
            "触发限流",
            "降低并发或等待后重试",
            "Medium",
        ),
        (
            ("timeout", "timed out", "timeout exceeded"),
            0.72,
            "请求或页面操作超时",
            "检查服务响应、UI_HEAL_TIMEOUT_MS 或网络延迟",
            "Medium",
        ),
    ]
    for markers, conf, cause, suggestion, severity in env_rules:
        hit = [m for m in markers if m in lower]
        if hit:
            evidence.extend(hit[:3])
            return "env", conf, cause, suggestion, evidence, severity

    data_rules: list[tuple[tuple[str, ...], float, str, str, str]] = [
        (
            ("404", "not found"),
            0.78,
            "资源不存在或路径/ID 错误",
            "核对接口路径、路由与测试数据是否存在",
            "Medium",
        ),
        (
            ("jsondecodeerror", "expecting value", "invalid json"),
            0.74,
            "响应体非 JSON 或为空",
            "检查接口是否返回 HTML/空体；确认 Content-Type",
            "Medium",
        ),
    ]
    for markers, conf, cause, suggestion, severity in data_rules:
        hit = [m for m in markers if m in lower]
        if hit:
            evidence.extend(hit[:3])
            return "data", conf, cause, suggestion, evidence, severity

    code_rules: list[tuple[tuple[str, ...], float, str, str, str]] = [
        (
            ("500", "internal server error", "502", "503", "bad gateway"),
            0.76,
            "服务端内部错误或网关异常",
            "查看服务端日志，定位堆栈与依赖",
            "High",
        ),
        (
            ("403", "forbidden", "permission denied"),
            0.7,
            "权限不足或角色不匹配",
            "核对账号角色与接口鉴权策略",
            "High",
        ),
    ]
    for markers, conf, cause, suggestion, severity in code_rules:
        hit = [m for m in markers if m in lower]
        if hit:
            evidence.extend(hit[:3])
            return "code", conf, cause, suggestion, evidence, severity

    test_rules: list[tuple[tuple[str, ...], float, str, str, str]] = [
        (
            ("assertionerror", "assert ", "expected", "got"),
            0.68,
            "断言与预期不符（可能是用例或产品行为）",
            "对比预期/实际；稳定复现后再定是否为产品缺陷",
            "High",
        ),
        (
            ("422", "validation error", "unprocessable"),
            0.65,
            "请求参数校验失败",
            "核对 spec 请求体与接口契约",
            "Medium",
        ),
        (
            ("keyerror", "missing key", "indexerror"),
            0.62,
            "响应结构变化或脚本解析字段缺失",
            "先 @api-skills/自我修复；确认契约是否变更",
            "Medium",
        ),
    ]
    for markers, conf, cause, suggestion, severity in test_rules:
        hit = [m for m in markers if m in lower]
        if hit:
            evidence.extend(hit[:3])
            cat = "test_design"
            if is_ui and ("locator" in lower or "定位失败" in lower):
                cause = "UI 元素定位失败或页面结构变化"
                suggestion = "先 @UI-skills/自我修复；确认页面是否改版"
            return cat, conf, cause, suggestion, evidence, severity

    return (
        "unknown",
        0.35,
        "无法从日志自动判定根因",
        "人工查看堆栈；可 @defect-analysis/SKILL.md 让 AI 补充分析",
        [],
        "High",
    )


def analyze_failure(
    nodeid: str,
    longrepr: str,
    duration_s: float | None = None,
) -> FailureAnalysis:
    text = longrepr or ""
    category, confidence, root_cause, suggestion, evidence, severity = _match_rules(
        text, nodeid
    )
    fp = compute_fingerprint(nodeid, text)

    pending_confirm = 0.5 <= confidence < 0.8
    auto_bug = confidence >= 0.8 and category in ("code", "data")
    if category == "env":
        auto_bug = False
    if category == "unknown":
        auto_bug = False
        pending_confirm = True

    first_line = text.strip().splitlines()[0][:120] if text.strip() else nodeid
    if first_line and first_line not in evidence:
        evidence = [first_line] + evidence

    return FailureAnalysis(
        nodeid=nodeid,
        category=category,
        confidence=confidence,
        root_cause=root_cause,
        suggestion=suggestion,
        fingerprint=fp,
        severity=severity,
        pending_confirm=pending_confirm,
        auto_bug=auto_bug,
        duration_s=duration_s,
        evidence=evidence[:5],
    )


def _dedupe_analyses(analyses: list[FailureAnalysis]) -> None:
    seen: dict[str, str] = {}
    for item in analyses:
        if item.fingerprint in seen:
            item.duplicate_of = seen[item.fingerprint]
            item.auto_bug = False
        else:
            seen[item.fingerprint] = item.nodeid


def _infer_module(nodeid: str, text: str) -> str:
    blob = f"{nodeid}\n{text}".lower()
    if any(x in blob for x in ("/register", "register", "注册")):
        return "注册"
    if any(x in blob for x in ("/login", "login", "登录", "/api/auth/login")):
        return "登录"
    if any(x in blob for x in ("/products", "product", "商品")):
        return "商品"
    if any(x in blob for x in ("/profile", "401", "403", "token", "鉴权")):
        return "鉴权"
    return "其他"


def infer_coverage_gaps(analyses: list[FailureAnalysis]) -> list[dict[str, str]]:
    """从失败集合反推用例盲区（规则版，供 JSON/Markdown 报告）。"""
    if not analyses:
        return []

    gaps: list[dict[str, str]] = []
    by_module: dict[str, int] = {}
    cat_counts: dict[str, int] = {}
    ui_locator = 0
    auth_fail = 0
    validation = 0

    for a in analyses:
        text = f"{a.nodeid} {a.root_cause} {' '.join(a.evidence)}".lower()
        mod = _infer_module(a.nodeid, text)
        by_module[mod] = by_module.get(mod, 0) + 1
        cat_counts[a.category] = cat_counts.get(a.category, 0) + 1
        if "locator" in text or "定位" in text:
            ui_locator += 1
        if any(x in text for x in ("401", "403", "unauthorized", "forbidden")):
            auth_fail += 1
        if any(x in text for x in ("422", "validation", "校验")):
            validation += 1

    for mod, n in sorted(by_module.items(), key=lambda x: -x[1]):
        if mod != "其他" and n >= 1:
            gaps.append(
                {
                    "area": f"{mod}模块",
                    "signal": f"{n} 次失败集中在 {mod}",
                    "suggestion": f"复核 {mod} 相关 L-/V-/P- 用例是否覆盖主路径与关键异常",
                }
            )

    if ui_locator >= 1:
        gaps.append(
            {
                "area": "UI 自动化",
                "signal": f"{ui_locator} 次定位/Playwright 失败",
                "suggestion": "补 UI-SECKILL 步骤或 @UI-skills/自我修复；对照 step_vocabulary.md",
            }
        )
    if auth_fail >= 2:
        gaps.append(
            {
                "area": "鉴权边界",
                "signal": f"{auth_fail} 次 401/403",
                "suggestion": "补 P-xx：未登录访问、错误 Token、越权访问 /api/auth/profile",
            }
        )
    if validation >= 1:
        gaps.append(
            {
                "area": "边界校验",
                "signal": f"{validation} 次 422/校验相关失败",
                "suggestion": "补 V-xx 边界 trio（见 boundary_value_testing.md）",
            }
        )
    if cat_counts.get("test_design", 0) >= 2:
        gaps.append(
            {
                "area": "测试设计",
                "signal": "多条 test_design 分类",
                "suggestion": "优先修脚本/断言；确认非契约漂移后再报产品 Bug",
            }
        )

    return gaps[:8]


def _build_stats(analyses: list[FailureAnalysis]) -> dict[str, Any]:
    by_cat: dict[str, int] = {c: 0 for c in CATEGORIES}
    conf_sum = 0.0
    for a in analyses:
        by_cat[a.category] = by_cat.get(a.category, 0) + 1
        conf_sum += a.confidence
    avg_conf = round(conf_sum / len(analyses), 2) if analyses else 0.0
    return {
        "by_category": by_cat,
        "avg_confidence": avg_conf,
        "duplicate_count": sum(1 for a in analyses if a.duplicate_of),
        "auto_bug_candidates": sum(1 for a in analyses if a.auto_bug),
    }


def write_json_report(analyses: list[FailureAnalysis], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    gaps = infer_coverage_gaps(analyses)
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "failed_count": len(analyses),
        "failures": [a.to_dict() for a in analyses],
        "stats": _build_stats(analyses),
        "coverage_gaps": gaps,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_markdown_report(analyses: list[FailureAnalysis], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    stats = _build_stats(analyses)
    lines = [
        "# 失败分析报告",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 统计",
        "",
        "| 类别 | 数量 |",
        "|------|------|",
    ]
    for cat in CATEGORIES:
        lines.append(f"| {CATEGORY_LABELS[cat]} ({cat}) | {stats['by_category'].get(cat, 0)} |")
    lines.extend(
        [
            "",
            f"- 平均置信度：**{stats['avg_confidence']}**",
            f"- 指纹重复：**{stats['duplicate_count']}**",
            f"- 建议自动报 Bug：**{stats['auto_bug_candidates']}**",
            "",
            "## 明细",
            "",
        ]
    )
    for a in analyses:
        dup = f"（重复于 `{a.duplicate_of}`）" if a.duplicate_of else ""
        lines.append(f"### `{a.nodeid}` {dup}")
        lines.append(f"- **类别**：{CATEGORY_LABELS[a.category]} · 置信度 {a.confidence:.2f}")
        lines.append(f"- **根因**：{a.root_cause}")
        lines.append(f"- **建议**：{a.suggestion}")
        lines.append(f"- **指纹**：`{a.fingerprint}`")
        lines.append("")

    gaps = infer_coverage_gaps(analyses)
    if gaps:
        lines.extend(["## 覆盖率盲区", ""])
        for i, g in enumerate(gaps, 1):
            lines.append(f"{i}. **{g['area']}**：{g['signal']}")
            lines.append(f"   → {g['suggestion']}")
            lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def process_session_failures(failed_reports: list[dict[str, Any]]) -> dict[str, Path]:
    """
    failed_reports: [{nodeid, longrepr, duration}]
    返回写入的文件路径 dict（json / markdown）。
    """
    if not _analysis_enabled() or not failed_reports:
        return {}

    analyses: list[FailureAnalysis] = []
    for item in failed_reports:
        analyses.append(
            analyze_failure(
                item["nodeid"],
                item.get("longrepr") or "",
                item.get("duration"),
            )
        )
    _dedupe_analyses(analyses)

    out_dir = resolve_analysis_dir()
    formats = _parse_formats()
    written: dict[str, Path] = {}

    if "json" in formats:
        written["json"] = write_json_report(analyses, out_dir / "failure_analysis.json")
    if "markdown" in formats:
        written["markdown"] = write_markdown_report(analyses, out_dir / "failure_stats.md")

    return written


def format_terminal_summary(analyses: list[FailureAnalysis]) -> str:
    if not analyses:
        return ""
    stats = _build_stats(analyses)
    top = sorted(analyses, key=lambda x: -x.confidence)[:3]
    lines = [
        "========================================",
        "失败分析（defect-analysis）",
        "========================================",
        f"失败: {len(analyses)}  |  平均置信度: {stats['avg_confidence']}",
    ]
    for cat in CATEGORIES:
        n = stats["by_category"].get(cat, 0)
        if n:
            lines.append(f"  {CATEGORY_LABELS[cat]}: {n}")
    lines.append("")
    lines.append("Top 失败:")
    for a in top:
        short = a.nodeid.split("::")[-1]
        lines.append(
            f"  {short} → {CATEGORY_LABELS[a.category]} ({a.confidence:.0%})"
        )
    lines.append("========================================")
    return "\n".join(lines)


if __name__ == "__main__":
    demo_failed = [
        {
            "nodeid": "output/api_smoke.py::test_health",
            "longrepr": "ConnectionError: Connection refused errno 111",
            "duration": 0.5,
        },
        {
            "nodeid": "output/api_smoke.py::test_orders",
            "longrepr": "AssertionError: expected 200, got 500 Internal Server Error",
            "duration": 1.2,
        },
    ]
    out = process_session_failures(demo_failed)
    analyses = [analyze_failure(x["nodeid"], x["longrepr"], x["duration"]) for x in demo_failed]
    _dedupe_analyses(analyses)
    print(format_terminal_summary(analyses))
    for k, p in out.items():
        print(f"[failure-analysis] {k}: {p}")
