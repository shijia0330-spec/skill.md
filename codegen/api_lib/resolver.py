"""变量与占位符解析：${var}、{{var}}、__ENV__:VAR、{ctx}、${prev.response...}。"""
from __future__ import annotations

import os
import re
import time
import uuid
from typing import Any

_ENV_PREFIX = "__ENV__:"
_PREV_PATTERN = re.compile(r"\$\{prev\.response(?:\.([a-zA-Z0-9_.\[\]]+))?\}")
_VAR_PATTERN = re.compile(r"\$\{([a-zA-Z_][a-zA-Z0-9_]*)\}")
_DBL_PATTERN = re.compile(r"\{\{([a-zA-Z_][a-zA-Z0-9_]*)\}\}")


def resolve_env(value: str) -> str:
    if value.startswith(_ENV_PREFIX):
        rest = value[len(_ENV_PREFIX) :]
        if "|" in rest:
            key, suffix = rest.split("|", 1)
            return os.environ.get(key, "") + suffix
        return os.environ.get(rest, "")
    return value


def _json_get_by_path(obj: Any, dotted: str) -> Any:
    cur = obj
    for part in dotted.replace("[", ".").replace("]", "").split("."):
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


def resolve_string(
    text: str,
    pool: dict[str, Any],
    *,
    prev_response: Any = None,
) -> str:
    if text.startswith(_ENV_PREFIX):
        return os.environ.get(text[len(_ENV_PREFIX) :], "")

    out = text

    def _prev_repl(m: re.Match[str]) -> str:
        path = m.group(1)
        if prev_response is None:
            return ""
        if not path:
            try:
                import json

                return json.dumps(prev_response, ensure_ascii=False)
            except Exception:
                return str(prev_response)
        val = _json_get_by_path(prev_response, path)
        return "" if val is None else str(val)

    out = _PREV_PATTERN.sub(_prev_repl, out)

    def _var_repl(m: re.Match[str]) -> str:
        key = m.group(1)
        if key == "timestamp":
            return str(int(time.time()))
        if key == "uuid":
            return str(uuid.uuid4())[:8]
        val = pool.get(key)
        return "" if val is None else str(val)

    out = _VAR_PATTERN.sub(_var_repl, out)

    def _dbl_repl(m: re.Match[str]) -> str:
        key = m.group(1)
        if key == "timestamp":
            return str(int(time.time()))
        if key == "uuid":
            return str(uuid.uuid4())[:8]
        val = pool.get(key)
        return "" if val is None else str(val)

    out = _DBL_PATTERN.sub(_dbl_repl, out)

    # 兼容旧 spec：{var_name} 上下文替换
    for k, v in pool.items():
        out = out.replace("{" + k + "}", "" if v is None else str(v))

    return out


def fill_body(obj: Any, pool: dict[str, Any], *, prev_response: Any = None) -> Any:
    if isinstance(obj, str):
        if obj.startswith(_ENV_PREFIX):
            return os.environ.get(obj[len(_ENV_PREFIX) :], "")
        return resolve_string(obj, pool, prev_response=prev_response)
    if isinstance(obj, dict):
        return {k: fill_body(v, pool, prev_response=prev_response) for k, v in obj.items()}
    if isinstance(obj, list):
        return [fill_body(x, pool, prev_response=prev_response) for x in obj]
    return obj
