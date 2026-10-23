"""
Markdown 缺陷草稿 → Canonical Defect JSON
对齐 bug-reporter/SKILL.md 字段 + defect-analysis 指纹算法
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

ENGINE_ROOT = Path(__file__).resolve().parent.parent.parent


@dataclass
class CanonicalDefect:
    bug_id: str
    title: str
    severity: str = "Medium"
    defect_type: str = "功能"
    module: str = ""
    status: str = "Draft"
    priority: str = "P2"
    triage: str = ""
    steps: str = ""
    nodeid: str = ""
    discoverer: str = "自动化测试"
    discovered_at: str = ""
    discovered_via: str = "自动化测试（pytest）"
    environment: dict[str, str] = field(default_factory=dict)
    fingerprint: str = ""
    source_file: str = ""
    raw_markdown: str = ""
    failure_category: str = ""
    failure_category_label: str = ""
    failure_confidence: float | None = None
    failure_root_cause: str = ""
    failure_suggestion: str = ""
    analysis_matched_by: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def analysis_block(self) -> dict[str, Any]:
        if not self.failure_category:
            return {}
        block: dict[str, Any] = {
            "category": self.failure_category,
            "category_label": self.failure_category_label or self.failure_category,
            "confidence": self.failure_confidence,
            "root_cause": self.failure_root_cause,
            "suggestion": self.failure_suggestion,
        }
        return {k: v for k, v in block.items() if v not in (None, "")}


def _table_value(text: str, key: str) -> str:
    pattern = rf"\|\s*{re.escape(key)}\s*\|\s*([^|\n]+?)\s*\|"
    m = re.search(pattern, text)
    return m.group(1).strip() if m else ""


def _extract_list_item(text: str, prefix: str) -> str:
    for line in text.splitlines():
        line = line.strip()
        cn_key = f"- {prefix}："
        en_key = f"- {prefix}:"
        if line.startswith(cn_key):
            return line[len(cn_key):].strip().strip("`")
        if line.startswith(en_key):
            return line[len(en_key):].strip().strip("`")
        if line.startswith(prefix + "：") or line.startswith(prefix + ":"):
            sep = "：" if "：" in line else ":"
            return line.split(sep, 1)[-1].strip().strip("`")
    return ""


def compute_fingerprint(nodeid: str, body: str) -> str:
    """与 defect-analysis 一致：nodeid + 错误摘要前 50 字符 → MD5"""
    status_code = ""
    for code in ("500", "401", "403", "404", "422", "502", "503"):
        if code in body:
            status_code = code
            break
    error_snippet = re.sub(r"\s+", " ", body)[:50]
    raw = f"{nodeid}|{status_code}|{error_snippet}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def parse_markdown_draft(path: Path) -> CanonicalDefect:
    text = path.read_text(encoding="utf-8")
    bug_id = _table_value(text, "缺陷编号") or path.stem.split("_")[0]

    title_m = re.search(r"\|\s*标题\s*\|\s*([^|\n]+?)\s*\|", text)
    title = title_m.group(1).strip() if title_m else path.stem

    nodeid = _extract_list_item(text, "pytest nodeid").strip("`")
    if not nodeid:
        nodeid_m = re.search(r"关联 nodeid[：:]\s*`?([^`\n]+)`?", text)
        nodeid = nodeid_m.group(1).strip() if nodeid_m else ""

    steps_m = re.search(r"## 问题描述\s*\n+([\s\S]*?)(?=\n## |\Z)", text)
    steps = steps_m.group(1).strip() if steps_m else ""

    env: dict[str, str] = {}
    env_block = re.search(r"## 环境信息\s*\n+([\s\S]*?)(?=\n## |\Z)", text)
    if env_block:
        for row in re.finditer(r"\|\s*([^|]+?)\s*\|\s*([^|\n]+?)\s*\|", env_block.group(1)):
            k, v = row.group(1).strip(), row.group(2).strip()
            if k and k not in ("字段", "------"):
                env[k] = v

    defect = CanonicalDefect(
        bug_id=bug_id,
        title=title,
        severity=_table_value(text, "严重程度") or "Medium",
        defect_type=_table_value(text, "缺陷类型") or "功能",
        status=_table_value(text, "当前状态") or "Draft",
        priority=_table_value(text, "优先级") or "P2",
        triage=_table_value(text, "分流") or "",
        steps=steps,
        nodeid=nodeid,
        discoverer=_extract_list_item(text, "发现人") or "自动化测试",
        discovered_at=_extract_list_item(text, "发现时间") or datetime.now().strftime("%Y-%m-%d %H:%M"),
        discovered_via=_extract_list_item(text, "发现方式") or "自动化测试（pytest）",
        environment=env,
        source_file=str(path),
        raw_markdown=text,
    )
    defect.fingerprint = compute_fingerprint(defect.nodeid or defect.bug_id, defect.steps or text)
    return defect


def load_defects_from_path(target: Path) -> list[CanonicalDefect]:
    if target.is_file() and target.suffix == ".md":
        defects = [parse_markdown_draft(target)]
    elif target.is_dir():
        files = sorted(target.glob("BUG-*.md"))
        if not files:
            files = sorted(target.glob("*.md"))
        defects = [parse_markdown_draft(f) for f in files if f.name != "bug_list.md"]
    else:
        return []

    if _analysis_enrich_enabled() and defects:
        index = load_failure_analysis_index()
        if index.get("by_fingerprint") or index.get("by_nodeid"):
            for defect in defects:
                enrich_defect_from_analysis(defect, index)
    return defects


def defect_to_payload(defect: CanonicalDefect) -> dict[str, Any]:
    return defect.to_dict()


def resolve_failure_analysis_path() -> Path:
    raw = os.environ.get("FAILURE_ANALYSIS_PATH", "").strip()
    if raw:
        p = Path(raw)
        return p if p.is_absolute() else (ENGINE_ROOT / p)
    raw_dir = os.environ.get("FAILURE_ANALYSIS_DIR", "").strip()
    if raw_dir:
        base = Path(raw_dir) if Path(raw_dir).is_absolute() else (ENGINE_ROOT / raw_dir)
        return base / "failure_analysis.json"
    return ENGINE_ROOT / "output" / "reports" / "failure_analysis.json"


def _analysis_enrich_enabled() -> bool:
    return os.environ.get("DEFECT_SYNC_ENRICH_ANALYSIS", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def load_failure_analysis_index(path: Path | None = None) -> dict[str, dict[str, Any]]:
    """按 fingerprint / nodeid 索引 failure_analysis.json。"""
    path = path or resolve_failure_analysis_path()
    if not path.is_file():
        return {"by_fingerprint": {}, "by_nodeid": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"by_fingerprint": {}, "by_nodeid": {}}

    by_fp: dict[str, dict[str, Any]] = {}
    by_node: dict[str, dict[str, Any]] = {}
    for item in data.get("failures") or []:
        if not isinstance(item, dict):
            continue
        fp = str(item.get("fingerprint") or "")
        nodeid = str(item.get("nodeid") or "")
        if fp:
            by_fp[fp] = item
        if nodeid:
            by_node[nodeid] = item
    return {"by_fingerprint": by_fp, "by_nodeid": by_node}


def enrich_defect_from_analysis(
    defect: CanonicalDefect,
    index: dict[str, dict[str, Any]] | None = None,
) -> CanonicalDefect:
    if index is None:
        index = load_failure_analysis_index()
    by_fp = index.get("by_fingerprint") or {}
    by_node = index.get("by_nodeid") or {}

    hit: dict[str, Any] | None = by_fp.get(defect.fingerprint)
    matched_by = "fingerprint"
    if hit is None and defect.nodeid:
        hit = by_node.get(defect.nodeid)
        matched_by = "nodeid"
    if not hit:
        return defect

    defect.failure_category = str(hit.get("category") or "")
    defect.failure_category_label = str(hit.get("category_label") or "")
    conf = hit.get("confidence")
    defect.failure_confidence = float(conf) if conf is not None else None
    defect.failure_root_cause = str(hit.get("root_cause") or "")
    defect.failure_suggestion = str(hit.get("suggestion") or "")
    defect.analysis_matched_by = matched_by
    return defect


def format_analysis_appendix(defect: CanonicalDefect) -> str:
    block = defect.analysis_block()
    if not block:
        return ""
    lines = [
        "",
        "---",
        "【失败分析 defect-analysis】",
        f"类别: {block.get('category_label', block.get('category', ''))}"
        + (f"（置信度 {block['confidence']:.0%}）" if block.get("confidence") is not None else ""),
    ]
    if block.get("root_cause"):
        lines.append(f"根因: {block['root_cause']}")
    if block.get("suggestion"):
        lines.append(f"建议: {block['suggestion']}")
    return "\n".join(lines)
