"""JSON 点分路径取值。"""
from __future__ import annotations

from typing import Any


def extract_by_path(obj: Any, dotted: str) -> Any:
    cur = obj
    for part in dotted.split("."):
        if not part:
            continue
        if isinstance(cur, list) and part.isdigit():
            idx = int(part)
            cur = cur[idx] if idx < len(cur) else None
        elif isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur
