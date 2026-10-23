#!/usr/bin/env python3
"""UI automation 步骤 → Appium 声明式 steps（规则映射，非 1:1 像素级）。"""
from __future__ import annotations

import re
from typing import Any

LABEL_TO_ACCESSIBILITY: dict[str, str] = {
    "用户名": "username_input",
    "密码": "password_input",
    "邮箱": "email_input",
    "确认密码": "confirm_password_input",
    "登录": "login_button",
    "注册": "register_button",
    "搜索": "search_button",
    "提交": "submit_button",
}


def _slug(text: str, *, suffix: str = "") -> str:
    s = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "_", (text or "").strip()).strip("_").lower()
    if not s:
        s = "element"
    return f"{s}{suffix}" if suffix else s


def _resolve_env_value(raw: str) -> str:
    v = str(raw or "")
    for token, env_key in (
        ("${TEST_USERNAME}", "TEST_USERNAME"),
        ("admin", "TEST_USERNAME"),
        ("${TEST_PASSWORD}", "TEST_PASSWORD"),
        ("admin123", "TEST_PASSWORD"),
    ):
        if v == token and env_key:
            return f"${{{env_key}}}"
    return v


def ui_step_to_appium_steps(step: dict[str, Any]) -> list[dict[str, Any]]:
    action = str(step.get("action") or "").strip()
    if action == "wait_timeout_ms":
        return [{"action": "wait_timeout_ms", "ms": int(step.get("ms") or 800)}]
    if action in ("goto", "ensure_logged_in"):
        path = str(step.get("path") or "/")
        url = path if path.startswith("http") else f"${{TEST_BASE_URL}}{path}"
        out: list[dict[str, Any]] = [
            {"action": "switch_context", "name": "WEBVIEW"},
            {"action": "open_url", "url": url},
            {"action": "wait_timeout_ms", "ms": 1500},
        ]
        if action == "ensure_logged_in":
            out.insert(0, {"action": "permission_allow"})
        return out
    if action == "fill":
        label = str(step.get("l1_label") or step.get("l1_placeholder") or "")
        val = _resolve_env_value(str(step.get("value") or ""))
        aid = LABEL_TO_ACCESSIBILITY.get(label) or _slug(label, suffix="_input")
        return [{"action": "fill", "by": "accessibility_id", "value": aid, "input": val}]
    if action == "click":
        name = str(step.get("l1_name") or step.get("l1_name_regex") or "")
        if "登" in name and "录" in name:
            aid = "login_button"
        elif "注" in name and "册" in name:
            aid = "register_button"
        else:
            aid = LABEL_TO_ACCESSIBILITY.get(name) or _slug(name, suffix="_button")
        return [{"action": "click", "by": "accessibility_id", "value": aid, "wait_sec": 15}]
    if action == "click_radio":
        val = str(step.get("value") or "")
        return [{"action": "click", "by": "accessibility_id", "value": _slug(val, suffix="_option")}]
    return []


def ui_expect_to_appium(exp: dict[str, Any]) -> dict[str, Any] | None:
    et = str(exp.get("type") or "").strip()
    if et == "visible_text":
        text = str(exp.get("text") or "")
        if not text:
            return None
        return {"type": "text_in_page_source", "text": text}
    if et == "url_contains":
        return {"type": "text_in_page_source", "text": str(exp.get("pattern") or exp.get("text") or "")}
    return None


def convert_ui_flow(flow: dict[str, Any]) -> dict[str, Any]:
    steps_in = flow.get("steps") if isinstance(flow.get("steps"), list) else []
    appium_steps: list[dict[str, Any]] = []
    for st in steps_in:
        if isinstance(st, dict):
            appium_steps.extend(ui_step_to_appium_steps(st))
    expects_in = flow.get("expect") if isinstance(flow.get("expect"), list) else []
    appium_expects: list[dict[str, Any]] = []
    for ex in expects_in:
        if isinstance(ex, dict):
            converted = ui_expect_to_appium(ex)
            if converted:
                appium_expects.append(converted)
    out: dict[str, Any] = {
        "name": flow.get("name") or "flow",
        "steps": appium_steps,
    }
    if appium_expects:
        out["expect"] = appium_expects
    for key in ("layer", "priority", "parametrize"):
        if key in flow:
            out[key] = flow[key]
    return out
