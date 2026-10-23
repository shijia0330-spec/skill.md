"""选择器注册表运行时 — spec registry_key → 合并 l1_* 定位字段。"""
from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

DEFAULT_REGISTRY = Path("output/selector_registry.json")


def _slug_key(key: str) -> str:
    return re.sub(r"[^0-9a-zA-Z._-]+", ".", key.strip()).strip(".")


def registry_path() -> Path:
    raw = os.environ.get("SELECTOR_REGISTRY_PATH", "").strip()
    return Path(raw) if raw else DEFAULT_REGISTRY


@lru_cache(maxsize=4)
def _load_registry_cached(path_str: str) -> dict[str, Any]:
    p = Path(path_str)
    if not p.is_file():
        return {"version": 1, "selectors": {}}
    data = json.loads(p.read_text(encoding="utf-8"))
    if "selectors" not in data:
        data["selectors"] = {}
    return data


def load_registry(path: Path | str | None = None) -> dict[str, Any]:
    p = Path(path) if path else registry_path()
    return _load_registry_cached(str(p.resolve()))


def resolve_locator_fields(key: str, registry_path_arg: Path | str | None = None) -> dict[str, Any]:
    reg = load_registry(registry_path_arg)
    k = _slug_key(key)
    entry = (reg.get("selectors") or {}).get(k)
    if not entry:
        return {}
    return dict(entry.get("locator") or {})


def merge_registry_step(step: dict[str, Any], registry_path_arg: Path | str | None = None) -> dict[str, Any]:
    """若 step 含 registry_key，合并定位字段（显式 l1_* 优先）。"""
    rk = step.get("registry_key")
    if not rk:
        return step
    loc = resolve_locator_fields(str(rk), registry_path_arg)
    if not loc:
        return step
    out = dict(step)
    for k, v in loc.items():
        if k not in out or not out[k]:
            out[k] = v
    return out
