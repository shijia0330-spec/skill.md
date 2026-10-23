"""缺陷同步 Adapter 基类"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from canonical import CanonicalDefect  # noqa: E402


@dataclass
class PushResult:
    success: bool
    remote_id: str = ""
    remote_url: str = ""
    message: str = ""
    dry_run: bool = False
    payload: dict[str, Any] | None = None


class BaseAdapter(ABC):
    platform: str = "base"

    def __init__(self, config: dict[str, Any]):
        self.config = config

    @abstractmethod
    def validate_config(self) -> list[str]:
        """返回缺失的配置项列表，空列表表示配置完整"""

    @abstractmethod
    def map_defect(self, defect: CanonicalDefect) -> dict[str, Any]:
        """Canonical → 平台 payload"""

    @abstractmethod
    def push(self, defect: CanonicalDefect, *, dry_run: bool = False) -> PushResult:
        """推送到远端平台"""

    def _map_severity(self, severity: str, mapping: dict[str, Any]) -> Any:
        return mapping.get(severity, mapping.get("default", severity))

    def _map_priority(self, priority: str, mapping: dict[str, Any]) -> Any:
        return mapping.get(priority, mapping.get("default", priority))
