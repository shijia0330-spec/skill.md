"""自然语言 → ui_lib steps[]（regex 优先，可选 LLM）。"""
from __future__ import annotations

import json
import os
import re
from typing import Any
from urllib.parse import urlparse

# 分句
_SPLIT_RE = re.compile(r"[，,。.;；、\n]+")


def _split_clauses(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []
    parts = [p.strip() for p in _SPLIT_RE.split(text) if p.strip()]
    return parts or [text]


_PATH_ALIASES = {
    "登录页": "/login",
    "登录": "/login",
    "login": "/login",
    "首页": "/",
    "主页": "/",
}


def _to_path(url_or_path: str, base_url: str | None) -> str:
    s = url_or_path.strip()
    if s in _PATH_ALIASES:
        return _PATH_ALIASES[s]
    if s.startswith("http://") or s.startswith("https://"):
        if base_url:
            base = urlparse(base_url)
            u = urlparse(s)
            if base.netloc and u.netloc == base.netloc:
                return u.path or "/"
        return s
    if not s.startswith("/"):
        s = "/" + s
    return s


def _parse_clause(clause: str, base_url: str | None) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    c = clause.strip()

    if re.match(r"打开(?:登录页|登录)$", c):
        steps.append({"action": "goto", "path": "/login"})
        return steps

    m = re.search(r"(https?://[^\s，,。]+)", c)
    if m:
        steps.append({"action": "goto", "path": _to_path(m.group(1), base_url)})
        return steps

    for pat in (
        r"打开(?:页面)?[：:\s]*(.+)",
        r"访问[：:\s]*(.+)",
        r"导航到[：:\s]*(.+)",
        r"进入[：:\s]*(.+)",
    ):
        m = re.match(pat, c)
        if m:
            target = m.group(1).strip()
            if target.startswith("http"):
                steps.append({"action": "goto", "path": _to_path(target, base_url)})
            else:
                steps.append({"action": "goto", "path": _to_path(target, base_url)})
            return steps

    m = re.match(r"(用户名|账号|密码)[输入填写填入]*[：:\s]*(\S+)", c)
    if m:
        field, val = m.group(1), m.group(2)
        if field in ("用户名", "账号"):
            steps.append({"action": "fill", "l1_placeholder": "请输入用户名", "value": val})
        else:
            steps.append({"action": "fill", "l1_placeholder": "请输入密码", "value": val})
        return steps

    m = re.match(r"输入[：:\s]*(.+?)[：:\s]+(.+)", c)
    if m:
        label, val = m.group(1).strip(), m.group(2).strip()
        step: dict[str, Any] = {"action": "fill", "value": val}
        if label in ("用户名", "账号"):
            step["l1_placeholder"] = "请输入用户名"
        elif label == "密码":
            step["l1_placeholder"] = "请输入密码"
        else:
            step["l1_label"] = label
        steps.append(step)
        return steps

    m = re.match(r"(?:填写|填入)[：:\s]*(.+?)[为是：:\s]+(.+)", c)
    if m:
        label, val = m.group(1).strip(), m.group(2).strip()
        step = {"action": "fill", "value": val}
        if label in ("用户名", "账号"):
            step["l1_placeholder"] = "请输入用户名"
        elif label == "密码":
            step["l1_placeholder"] = "请输入密码"
        else:
            step["l1_label"] = label
        steps.append(step)
        return steps

    m = re.search(r'点击[「""](.+?)[」""]', c)
    if m:
        steps.append({"action": "click", "l1_role": "button", "l1_name": m.group(1).strip()})
        return steps

    m = re.match(r"点击(.+?)(?:按钮|链接)?$", c)
    if m:
        text = m.group(1).strip()
        role = "link" if "链接" in c else "button"
        steps.append({"action": "click", "l1_role": role, "l1_name": text})
        return steps

    m = re.match(r"(?:验证|检查|断言).*(?:包含|出现|显示)[：:\s]*(.+)", c)
    if m:
        return [{"__expect__": {"type": "visible_text", "text": m.group(1).strip(), "exact": False}}]

    m = re.match(r"等待[：:\s]*(\d+)\s*秒", c)
    if m:
        steps.append({"action": "wait_timeout_ms", "ms": int(m.group(1)) * 1000})
        return steps

    return steps


def _inject_login_flow(steps: list[dict[str, Any]], base_url: str | None) -> list[dict[str, Any]]:
    labels = set()
    for s in steps:
        if s.get("action") == "fill":
            lb = s.get("l1_label") or s.get("l1_placeholder")
            if lb:
                labels.add(str(lb))
    if not {"用户名", "密码"} <= labels and not ({"账号", "密码"} <= labels):
        return steps

    out = list(steps)
    if base_url:
        has_goto_login = any(
            s.get("action") == "goto" and str(s.get("path", "")).rstrip("/").endswith("/login") for s in out
        )
        if not has_goto_login:
            out.insert(0, {"action": "goto", "path": "/login"})

    has_login_click = any(
        s.get("action") == "click" and str(s.get("l1_name", "")) in ("登录", "Login") for s in out
    )
    if not has_login_click:
        out.append({"action": "click", "l1_role": "button", "l1_name": "登录"})
    return out


def _parse_with_llm(text: str, base_url: str | None) -> list[dict[str, Any]] | None:
    api_key = os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY") or os.environ.get("DASHSCOPE_API_KEY")
    if not api_key:
        return None
    try:
        import requests
    except ImportError:
        return None

    base = (os.environ.get("LLM_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
    model = os.environ.get("LLM_MODEL", "gpt-4o-mini")
    system = (
        "将用户 UI 操作描述转为 JSON 数组。每项为 ui_lib step："
        "action 取值 goto|fill|click|wait_timeout_ms；"
        "fill 用 l1_label；click 用 l1_role+l1_name；goto 用 path（相对路径）。"
        "验证语句输出 {\"__expect__\": {\"type\":\"visible_text\",\"text\":\"...\"}}。"
        "只输出 JSON 数组，不要 markdown。"
    )
    user = f"base_url={base_url or ''}\n描述：{text}"
    resp = requests.post(
        f"{base}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}], "temperature": 0},
        timeout=int(os.environ.get("LLM_TIMEOUT", "60")),
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"].strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?|```$", "", content, flags=re.MULTILINE).strip()
    data = json.loads(content)
    if isinstance(data, list):
        return data
    return None


def parse_nl_to_flow(
    text: str,
    base_url: str | None = None,
    *,
    parser: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """返回 (steps, expects)。"""
    mode = (parser or os.environ.get("NL_PARSER", "auto")).strip().lower()
    raw_steps: list[dict[str, Any]] | None = None

    if mode in ("auto", "llm"):
        try:
            raw_steps = _parse_with_llm(text, base_url)
        except Exception:
            if mode == "llm":
                raise
            raw_steps = None

    if raw_steps is None:
        raw_steps = []
        for clause in _split_clauses(text):
            raw_steps.extend(_parse_clause(clause, base_url))

    steps: list[dict[str, Any]] = []
    expects: list[dict[str, Any]] = []
    for item in raw_steps:
        if "__expect__" in item:
            expects.append(item["__expect__"])
        else:
            steps.append(item)

    steps = _inject_login_flow(steps, base_url)
    return steps, expects


def parse_nl(text: str, base_url: str | None = None, *, parser: str | None = None) -> dict[str, Any]:
    steps, expects = parse_nl_to_flow(text, base_url, parser=parser)
    return {
        "text": text,
        "base_url": base_url,
        "steps": steps,
        "expects": expects,
        "count": len(steps),
    }
