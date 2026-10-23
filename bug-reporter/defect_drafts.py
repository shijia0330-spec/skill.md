"""
pytest 会话结束后，为失败用例自动生成缺陷 Markdown 草稿（对齐 bug-reporter/SKILL.md）。

环境变量：
  DEFECT_DRAFTS=1|0     默认 1，设为 0 关闭
  DEFECT_DRAFT_DIR      默认 <引擎根>/output/bugs
  DEFECT_DISCOVERER     发现人，默认 自动化测试
"""

from __future__ import annotations

import os
import re
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

ENGINE_ROOT = Path(__file__).resolve().parent.parent


def _drafts_enabled() -> bool:
    return os.environ.get("DEFECT_DRAFTS", "1").strip().lower() not in ("0", "false", "no", "off")


def resolve_draft_dir() -> Path:
    raw = os.environ.get("DEFECT_DRAFT_DIR", "").strip()
    if raw:
        p = Path(raw)
        return p if p.is_absolute() else (ENGINE_ROOT / p)
    return ENGINE_ROOT / "output" / "bugs"


def _is_ui_failure(nodeid: str, longrepr: str) -> bool:
    blob = f"{nodeid}\n{longrepr}".lower()
    ui_markers = (
        "playwright",
        "page.",
        "locator",
        "get_by_role",
        "get_by_label",
        "timeout",
        "screenshot",
        "chromium",
    )
    return any(m in blob for m in ui_markers)


def classify_failure(nodeid: str, longrepr: str) -> dict[str, str]:
    """粗分类：环境 / 脚本待修 / 产品缺陷待确认。"""
    text = longrepr.lower()
    is_ui = _is_ui_failure(nodeid, longrepr)

    env_markers = (
        "connection refused",
        "connectionerror",
        "failed to establish",
        "name or service not known",
        "nodename nor servname",
        "errno 111",
        "errno 61",
        "max retries exceeded",
        "network is unreachable",
    )
    if any(m in text for m in env_markers):
        return {
            "triage": "环境",
            "defect_type": "环境",
            "severity": "Medium",
            "priority": "P2",
            "title_hint": "测试环境不可达或服务未启动",
            "next_skill": "检查 BASE_URL / 服务进程；勿直接当产品缺陷提交",
        }

    heal_markers = (
        "404",
        "not found",
        "assertionerror",
        "jsondecodeerror",
        "keyerror",
        "401",
        "403",
        "422",
    )
    if any(m in text for m in heal_markers) and not is_ui:
        return {
            "triage": "脚本或契约漂移（待确认）",
            "defect_type": "功能",
            "severity": "High",
            "priority": "P1",
            "title_hint": "接口断言/状态与预期不符",
            "next_skill": "先 @api-skills/自我修复；复现稳定且确认为产品行为后再 @bug-reporter 定稿",
        }

    if is_ui and ("locator" in text or "timeout" in text):
        return {
            "triage": "UI 定位或超时（待确认）",
            "defect_type": "界面",
            "severity": "High",
            "priority": "P1",
            "title_hint": "页面元素定位失败或操作超时",
            "next_skill": "先 @UI-skills/自我修复；确认为产品问题后再定稿",
        }

    return {
        "triage": "产品缺陷（待人工确认）",
        "defect_type": "界面" if is_ui else "功能",
        "severity": "High",
        "priority": "P1",
        "title_hint": "自动化用例失败，需人工判定是否为缺陷",
        "next_skill": "复核后 @bug-reporter 补充证据并指派",
    }


def _next_bug_id(draft_dir: Path) -> str:
    today = datetime.now().strftime("%Y%m%d")
    prefix = f"BUG-{today}-"
    max_n = 0
    if draft_dir.is_dir():
        for f in draft_dir.glob(f"{prefix}*.md"):
            m = re.search(rf"{re.escape(prefix)}(\d+)", f.name)
            if m:
                max_n = max(max_n, int(m.group(1)))
    return f"{prefix}{max_n + 1:03d}"


def _safe_slug(nodeid: str, limit: int = 48) -> str:
    slug = re.sub(r"[^\w\-]+", "_", nodeid.split("::")[-1])[:limit].strip("_")
    return slug or "failed_test"


def _extract_case_id(nodeid: str, longrepr: str) -> str:
    for blob in (nodeid, longrepr):
        m = re.search(r"\b(TC[-_]?\w+|API[-_]?\d+|UI[-_]?\d+)\b", blob, re.I)
        if m:
            return m.group(1)
    return nodeid.split("::")[-1]


def render_draft_markdown(
    bug_id: str,
    nodeid: str,
    longrepr: str,
    duration_s: float | None,
    classification: dict[str, str],
    rag_hits: list[dict] | None = None,
) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    case_id = _extract_case_id(nodeid, longrepr)
    discoverer = os.environ.get("DEFECT_DISCOVERER", "自动化测试")
    is_ui = classification["defect_type"] == "界面"
    duration_line = f"{duration_s:.2f}s" if duration_s is not None else "—"

    title = f"{classification['title_hint']}（{case_id}）"

    if is_ui:
        problem_block = f"""**界面类缺陷（草稿）**

```
操作路径：（根据用例补充）
关联 nodeid：{nodeid}

页面现象：
（根据失败日志 / trace 补充）

失败摘要：
{longrepr[:2500]}
```"""
    else:
        problem_block = f"""**接口类缺陷（草稿）**

```
关联 nodeid：{nodeid}
执行耗时：{duration_line}

失败摘要：
{longrepr[:2500]}

（请补充：请求方法、URL、请求体、预期/实际状态码与响应体）
```"""

    # RAG 历史相似缺陷
    if rag_hits:
        rag_lines = [f"- **{h['title']}** (相似度: {h['relevance']:.3f})" for h in rag_hits]
        rag_section = "\n- ".join(["知识库命中以下历史缺陷："] + rag_lines)
    else:
        rag_section = "知识库无命中（首次出现此类失败，已自动收录）"

    return f"""# 缺陷报告草稿 — {bug_id}

> 由 pytest 自动生成，**状态：草稿**。请人工确认 triage 后再提交工单。

## 基本信息

| 字段 | 值 |
|------|-----|
| 缺陷编号 | {bug_id} |
| 标题 | {title} |
| 严重程度 | {classification['severity']} |
| 缺陷类型 | {classification['defect_type']} |
| 当前状态 | Draft |
| 优先级 | {classification['priority']} |
| 分流 | {classification['triage']} |

## 发现信息

- 发现时间：{now}
- 发现人：{discoverer}
- 发现方式：自动化测试（pytest）
- 关联用例：{case_id}
- pytest nodeid：`{nodeid}`

## 问题描述

{problem_block}

## 环境信息

| 字段 | 值 |
|------|-----|
| TEST_BASE_URL | {os.environ.get('TEST_BASE_URL', '（未设置）')} |
| 工作目录 | {os.getcwd()} |

## 建议下一步

- {classification['next_skill']}
- 完整规范见：`bug-reporter/SKILL.md`

## RAG 历史相似缺陷

- {rag_section}

## 附件（请补充）

- [ ] 请求/响应摘录（接口）
- [ ] 截图或 trace.zip 路径（UI）
- [ ] Allure / pytest 报告链接
"""


def _failure_fingerprint(nodeid: str, longrepr: str) -> str:
    norm = re.sub(r"\s+", " ", (longrepr or "")[:800])
    raw = f"{nodeid}|{norm}"
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:20]


def _load_fingerprint_index(draft_dir: Path) -> dict[str, str]:
    p = draft_dir / "fingerprints.json"
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_fingerprint_index(draft_dir: Path, index: dict[str, str]) -> None:
    p = draft_dir / "fingerprints.json"
    p.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")


def _find_existing_by_fingerprint(draft_dir: Path, fp: str) -> str | None:
    index = _load_fingerprint_index(draft_dir)
    return index.get(fp)


def write_draft(
    nodeid: str,
    longrepr: str,
    duration_s: float | None = None,
) -> Path | None:
    if not _drafts_enabled():
        return None

    draft_dir = resolve_draft_dir()
    draft_dir.mkdir(parents=True, exist_ok=True)

    fp = _failure_fingerprint(nodeid, longrepr)
    existing_bug = _find_existing_by_fingerprint(draft_dir, fp)
    if existing_bug:
        return None

    bug_id = _next_bug_id(draft_dir)
    clf = classify_failure(nodeid, longrepr)
    rag_hits = _search_rag_for_similar(nodeid, longrepr)
    body = render_draft_markdown(bug_id, nodeid, longrepr, duration_s, clf, rag_hits=rag_hits)
    slug = _safe_slug(nodeid)
    out = draft_dir / f"{bug_id}_{slug}.md"
    out.write_text(body, encoding="utf-8")
    _append_bug_list(draft_dir, bug_id, nodeid, clf, out)
    index = _load_fingerprint_index(draft_dir)
    index[fp] = bug_id
    _save_fingerprint_index(draft_dir, index)
    return out


def _search_rag_for_similar(nodeid: str, longrepr: str) -> list[dict]:
    """从 RAG 知识库检索历史相似缺陷。"""
    rag_scripts = ENGINE_ROOT / "rag-engine" / "scripts"
    service_file = rag_scripts / "service.py"
    if not service_file.is_file():
        return []
    try:
        import importlib.util
        import sys
        sys.path.insert(0, str(rag_scripts))
        spec = importlib.util.spec_from_file_location("rag_service_similar", service_file)
        if spec is None or spec.loader is None:
            return []
        mod = importlib.util.module_from_spec(spec)
        sys.modules["rag_service_similar"] = mod
        spec.loader.exec_module(mod)
        rag = mod.create_rag_service()

        # 构造检索词：从 nodeid 和错误信息提取关键词
        module = nodeid.split("::")[0] if "::" in nodeid else nodeid
        error_snippet = longrepr[:200].replace("\n", " ").strip()
        query = f"{module} 测试失败 {error_snippet[:80]}"

        results = rag.search(query, top_k=3)
        return [
            {"title": r.get("metadata", {}).get("title", ""), "relevance": r.get("relevance", 0)}
            for r in results
        ]
    except Exception:
        return []


def _append_bug_list(
    draft_dir: Path,
    bug_id: str,
    nodeid: str,
    classification: dict[str, str],
    path: Path,
) -> None:
    list_path = draft_dir / "bug_list.md"
    row = (
        f"| {bug_id} | {classification['triage']} | "
        f"{classification['severity']} | `{nodeid}` | [{path.name}]({path.name}) | Draft |\n"
    )
    header = (
        "# 缺陷汇总（自动生成）\n\n"
        "| 编号 | 分流 | 严重度 | nodeid | 文件 | 状态 |\n"
        "|------|------|--------|--------|------|------|\n"
    )
    if list_path.is_file():
        content = list_path.read_text(encoding="utf-8")
        if bug_id in content:
            return
        if "| 编号 |" not in content:
            list_path.write_text(header + row, encoding="utf-8")
        else:
            with list_path.open("a", encoding="utf-8") as f:
                f.write(row)
    else:
        list_path.write_text(header + row, encoding="utf-8")


def process_session_failures(failed_reports: list[dict[str, Any]]) -> list[Path]:
    """failed_reports: [{nodeid, longrepr, duration}]"""
    written: list[Path] = []
    for item in failed_reports:
        p = write_draft(
            item["nodeid"],
            item.get("longrepr") or "",
            item.get("duration"),
        )
        if p:
            written.append(p)
    return written
