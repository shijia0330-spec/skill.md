"""
从 PRD/需求文本构造 RAG 检索词 — 领域词由 rag_domain_keywords.json 配置。
"""
from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

_RAG_ENGINE_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = _RAG_ENGINE_ROOT / "config" / "rag_domain_keywords.json"

_BUILTIN_DEFAULT: dict[str, Any] = {
    "domain": "进销存",
    "business_keywords": [
        "登录", "注册", "支付", "订单", "库存", "鉴权", "Token", "权限",
        "秒杀", "财务", "采购", "销售", "入库", "出库", "盘点", "供应商",
        "客户", "退货", "对账", "应收", "应付", "商品", "仓库",
    ],
    "test_dimension_suffix": "测试用例 业务规则 验收标准 边界",
    "max_keywords_from_prd": 6,
    "max_query_length": 240,
    "api_path_pattern": r"接口[:：]\s*([/\w\-{}]+)",
}


def _resolve_config_path(config_path: Path | str | None = None) -> Path:
    if config_path:
        return Path(config_path).expanduser().resolve()
    env_path = os.environ.get("RAG_DOMAIN_CONFIG", "").strip()
    if env_path:
        return Path(env_path).expanduser().resolve()
    return DEFAULT_CONFIG_PATH


@lru_cache(maxsize=8)
def _load_config_cached(resolved_path: str) -> dict[str, Any]:
    path = Path(resolved_path)
    if not path.is_file():
        return dict(_BUILTIN_DEFAULT)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return dict(_BUILTIN_DEFAULT)
    if not isinstance(data, dict):
        return dict(_BUILTIN_DEFAULT)
    merged = dict(_BUILTIN_DEFAULT)
    merged.update(data)
    return merged


def load_domain_config(config_path: Path | str | None = None) -> dict[str, Any]:
    """加载领域词配置；缺失或损坏时回退到内置进销存默认值。"""
    return _load_config_cached(str(_resolve_config_path(config_path)))


def _business_keyword_pattern(config: dict[str, Any]) -> str:
    keywords = config.get("business_keywords") or _BUILTIN_DEFAULT["business_keywords"]
    cleaned = [str(k).strip() for k in keywords if str(k).strip()]
    if not cleaned:
        cleaned = list(_BUILTIN_DEFAULT["business_keywords"])
    return "(" + "|".join(re.escape(k) for k in cleaned) + ")"


def _first_heading(text: str) -> str:
    for line in text.splitlines():
        m = re.match(r"^#\s+(.+)", line.strip())
        if m:
            return m.group(1).strip()
    return ""


def extract_module_name(text: str) -> str:
    patterns = [
        r"模块[名称名]?[:：]\s*(.+)",
        r"功能[名称名]?[:：]\s*(.+)",
        r"测试范围[:：]\s*(.+)",
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            return m.group(1).strip().split("\n")[0][:80]
    title = _first_heading(text)
    if title:
        return re.sub(r"(测试用例|需求文档|PRD|说明书)$", "", title).strip() or title
    return ""


def build_query_from_prd(
    text: str,
    extra: str = "",
    *,
    config_path: Path | str | None = None,
) -> str:
    """从 PRD 抠检索词：模块名 + 配置化业务关键词 + 固定测试维度词。"""
    config = load_domain_config(config_path)
    module = extract_module_name(text)
    api_pat = config.get("api_path_pattern") or _BUILTIN_DEFAULT["api_path_pattern"]
    biz_pat = _business_keyword_pattern(config)
    max_kw = int(config.get("max_keywords_from_prd") or 6)
    suffix = str(config.get("test_dimension_suffix") or _BUILTIN_DEFAULT["test_dimension_suffix"])
    max_len = int(config.get("max_query_length") or 240)

    keywords: list[str] = []
    for pat in (api_pat, biz_pat):
        keywords.extend(re.findall(pat, text, flags=re.I))

    seen: set[str] = set()
    uniq: list[str] = []
    for k in keywords:
        k = k.strip()
        if k and k.lower() not in seen:
            seen.add(k.lower())
            uniq.append(k)

    parts = [p for p in (module, " ".join(uniq[:max_kw]), extra, suffix) if p]
    query = " ".join(parts)
    return re.sub(r"\s+", " ", query).strip()[:max_len]


def format_output(query: str, context: str, hit_count: int) -> str:
    lines = [
        "## 知识库检索摘要（RAG · 生成前必做）",
        "",
        f"- **检索词**：{query}",
        f"- **命中条数**：{hit_count}",
        "- **使用规则**：以下片段仅作补充；与 PRD 冲突时以 PRD 为准，并在待澄清清单记录。",
        "",
    ]
    if context.strip():
        lines.extend(["【RAG 检索结果】", context.strip(), ""])
    else:
        lines.extend([
            "（知识库无命中 — 已降级为纯 PRD + 覆盖矩阵生成，请在文档信息中标注 `RAG: 无命中`）",
            "",
        ])
    return "\n".join(lines)
