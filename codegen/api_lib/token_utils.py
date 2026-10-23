"""从登录/业务响应中提取 token（支持 auth profile 的 token_json_paths）。"""
from __future__ import annotations

from typing import Any

from .json_path import extract_by_path

DEFAULT_TOKEN_PATHS = (
    "access_token",
    "token",
    "data.access_token",
    "data.token",
)


def extract_token(data: Any, paths: list[str] | None = None) -> Any:
    if not isinstance(data, dict):
        return None
    for raw in paths or list(DEFAULT_TOKEN_PATHS):
        p = str(raw).strip()
        if not p:
            continue
        if "." in p:
            val = extract_by_path(data, p)
        else:
            val = data.get(p)
        if val not in (None, ""):
            return val
    return None
