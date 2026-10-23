"""用户可见路径：避免软链接 resolve 后显示真实路径。"""

from __future__ import annotations

import os
from pathlib import Path

_PREFER_HOME = os.environ.get("SKILLS_PREFER_HOME", str(Path.home()))


def display_path(path: Path | str) -> str:
    """返回更适合终端展示的路径（优先 SKILLS_PREFER_HOME，默认用户主目录）。"""
    p = Path(path)
    try:
        resolved = p.resolve()
    except OSError:
        return str(p)
    text = str(resolved)

    prefer = Path(_PREFER_HOME)
    try:
        if prefer.is_symlink():
            real_home = prefer.resolve()
            real_prefix = str(real_home)
            if text == real_prefix or text.startswith(real_prefix + "/"):
                return str(prefer) + text[len(real_prefix) :]
    except OSError:
        pass

    raw = str(p)
    prefer_s = str(prefer)
    if raw.startswith(prefer_s + "/") or raw == prefer_s:
        return raw

    return text
