#!/usr/bin/env python3
"""从用户话术解析 intent（读取 mapping.yaml，自上而下短路由）。"""
from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore

ROOT = Path(__file__).resolve().parent
DEFAULT_MAPPING = ROOT / "mapping.yaml"


def load_mapping(path: Path | None = None) -> dict[str, Any]:
    if yaml is None:
        raise RuntimeError("需要 PyYAML: pip install PyYAML")
    p = path or DEFAULT_MAPPING
    with p.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError("mapping.yaml 根节点须为对象")
    return data


def resolve_intent(text: str, mapping: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """返回 intent_tag / default_skill / skill_paths / matched_phrase；无匹配则 None。"""
    mapping = mapping or load_mapping()
    normalized = (text or "").strip()
    if not normalized:
        return None
    lower = normalized.lower()
    for rule in mapping.get("rules") or []:
        if not isinstance(rule, dict):
            continue
        for phrase in rule.get("phrases") or []:
            p = str(phrase).strip()
            if not p:
                continue
            if p.lower() in lower or p in normalized:
                return {
                    "intent_tag": rule.get("tag"),
                    "default_skill": rule.get("default_skill"),
                    "skill_paths": list(rule.get("skill_paths") or []),
                    "matched_phrase": p,
                }
    return None
