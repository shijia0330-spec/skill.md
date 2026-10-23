"""LLM 断言客户端（OpenAI 兼容 API）。"""
from __future__ import annotations

import json
import os
from typing import Any

import requests


def llm_judge(
    *,
    system: str,
    user: str,
    response_payload: str,
) -> tuple[bool, str]:
    """
    调用 LLM 做语义/业务判断。
    环境变量：LLM_API_KEY / OPENAI_API_KEY、LLM_BASE_URL、LLM_MODEL
    返回 (passed, reason)
    """
    api_key = os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("LLM 断言需要 LLM_API_KEY 或 OPENAI_API_KEY")

    base = (os.environ.get("LLM_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
    model = os.environ.get("LLM_MODEL", "gpt-4o-mini")
    url = f"{base}/chat/completions"

    messages = [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": f"{user}\n\n--- API 响应 ---\n{response_payload[:8000]}",
        },
    ]
    resp = requests.post(
        url,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": model, "messages": messages, "temperature": 0},
        timeout=int(os.environ.get("LLM_TIMEOUT", "60")),
    )
    resp.raise_for_status()
    data = resp.json()
    content = data["choices"][0]["message"]["content"].strip()

    try:
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            passed = bool(parsed.get("pass") or parsed.get("passed"))
            reason = str(parsed.get("reason") or parsed.get("message") or content)
            return passed, reason
    except json.JSONDecodeError:
        pass

    lowered = content.lower()
    if "pass" in lowered and "fail" not in lowered:
        return True, content
    if content.startswith("通过") or content.startswith("PASS"):
        return True, content
    return False, content
