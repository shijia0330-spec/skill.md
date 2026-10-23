"""全局变量池：跨用例 / 跨步骤传递 token、id、session_id 等。"""
from __future__ import annotations

from typing import Any


class VariablePool:
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

    def extract_auto(self, response_json: Any) -> None:
        """识别 token / id / session_id 并写入变量池。"""
        if not isinstance(response_json, dict):
            return
        data = response_json.get("data")
        if isinstance(data, dict):
            for key in ("token", "access_token", "id", "session_id"):
                if key in data and data[key] is not None:
                    self.set(key, data[key])
        for key in ("token", "access_token", "id", "session_id"):
            if key in response_json and response_json[key] is not None:
                self.set(key, response_json[key])
