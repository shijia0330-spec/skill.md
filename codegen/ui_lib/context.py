"""UI 步骤上下文变量池。"""
from __future__ import annotations

from typing import Any


class UIContext:
    def __init__(self, initial: dict[str, Any] | None = None) -> None:
        self._vars: dict[str, Any] = dict(initial or {})

    def set(self, key: str, value: Any) -> None:
        self._vars[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self._vars.get(key, default)

    def update(self, mapping: dict[str, Any]) -> None:
        self._vars.update(mapping)

    def as_dict(self) -> dict[str, Any]:
        return dict(self._vars)
