"""移动端选择器注册表 — registry_key → 定位字段；自愈成功后回写 L0 缓存。"""
from __future__ import annotations

import json
import os
import re
import threading
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

DEFAULT_REGISTRY = Path("output/mobile_selector_registry.json")
_WRITE_LOCK = threading.Lock()


def _slug_key(key: str) -> str:
    return re.sub(r"[^0-9a-zA-Z._-]+", ".", key.strip()).strip(".")


def registry_path() -> Path:
    raw = os.environ.get("MOBILE_SELECTOR_REGISTRY_PATH", "").strip()
    return Path(raw) if raw else DEFAULT_REGISTRY


def _registry_write_enabled() -> bool:
    return os.environ.get("MOBILE_REGISTRY_WRITE", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


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


def _invalidate_cache() -> None:
    _load_registry_cached.cache_clear()


def resolve_locator_fields(key: str, registry_path_arg: Path | str | None = None) -> dict[str, Any]:
    """返回 spec 级定位字段：by / value / healed_by / healed_value。"""
    reg = load_registry(registry_path_arg)
    k = _slug_key(key)
    entry = (reg.get("selectors") or {}).get(k)
    if not entry:
        return {}
    loc = dict(entry.get("locator") or {})
    healed = entry.get("healed") or {}
    if healed.get("by") and healed.get("value"):
        loc.setdefault("healed_by", healed["by"])
        loc.setdefault("healed_value", healed["value"])
        loc.setdefault("healed_strategy", healed.get("strategy", ""))
        loc.setdefault("healed_level", healed.get("level", "L0"))
    return loc


def merge_registry_step(step: dict[str, Any], registry_path_arg: Path | str | None = None) -> dict[str, Any]:
    """若 step 含 registry_key，合并 by/value（显式字段优先）。"""
    rk = step.get("registry_key")
    if not rk:
        return step
    loc = resolve_locator_fields(str(rk), registry_path_arg)
    if not loc:
        return step
    out = dict(step)
    healed_by = (loc.get("healed_by") or "").strip()
    healed_value = (loc.get("healed_value") or "").strip()
    if healed_by and healed_value:
        out.setdefault("by", healed_by)
        out.setdefault("value", healed_value)
    else:
        if loc.get("by") and not out.get("by"):
            out["by"] = loc["by"]
        if loc.get("value") and not out.get("value"):
            out["value"] = loc["value"]
    return out


def resolve_l0_attempt(key: str, registry_path_arg: Path | str | None = None) -> tuple[str, str] | None:
    """L0：返回上次自愈成功的 (by, locator)。"""
    loc = resolve_locator_fields(key, registry_path_arg)
    by = (loc.get("healed_by") or loc.get("by") or "").strip()
    value = (loc.get("healed_value") or loc.get("value") or "").strip()
    if by and value:
        return by, value
    return None


def record_healed_locator(
    key: str,
    *,
    by: str,
    locator: str,
    strategy: str,
    level: str,
    primary_by: str = "",
    primary_locator: str = "",
    registry_path_arg: Path | str | None = None,
) -> None:
    """自愈成功后写入注册表，供下次 L0 直读。"""
    if not _registry_write_enabled():
        return
    k = _slug_key(key)
    if not k:
        return
    p = Path(registry_path_arg) if registry_path_arg else registry_path()
    now = datetime.now(timezone.utc).isoformat()
    with _WRITE_LOCK:
        reg = load_registry(p)
        selectors = reg.setdefault("selectors", {})
        entry = selectors.setdefault(k, {"locator": {}, "healed": {}})
        if primary_by and primary_locator:
            entry["locator"] = {"by": primary_by, "value": primary_locator}
        entry["healed"] = {
            "by": by,
            "value": locator,
            "strategy": strategy,
            "level": level,
            "updated_at": now,
        }
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(reg, ensure_ascii=False, indent=2), encoding="utf-8")
        _invalidate_cache()
