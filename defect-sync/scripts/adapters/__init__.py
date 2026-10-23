"""Adapter 工厂"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .base import BaseAdapter
from .custom import CustomAdapter
from .yunxiao import YunXiaoAdapter
from .zentao import ZenTaoAdapter

CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config" / "platforms"

ADAPTERS: dict[str, type[BaseAdapter]] = {
    "zentao": ZenTaoAdapter,
    "yunxiao": YunXiaoAdapter,
    "custom": CustomAdapter,
}


def load_platform_config(platform: str) -> dict[str, Any]:
    yaml_path = CONFIG_DIR / f"{platform}.yaml"
    json_path = CONFIG_DIR / f"{platform}.json"
    if yaml_path.is_file():
        try:
            import yaml  # type: ignore

            return yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
        except ImportError:
            pass
    if json_path.is_file():
        return json.loads(json_path.read_text(encoding="utf-8"))
    return {}


def create_adapter(platform: str, config_override: dict[str, Any] | None = None) -> BaseAdapter:
    platform = platform.lower().strip()
    if platform not in ADAPTERS:
        raise ValueError(f"不支持的平台: {platform}，可选: {', '.join(ADAPTERS)}")
    config = load_platform_config(platform)
    if config_override:
        config.update(config_override)
    return ADAPTERS[platform](config)
