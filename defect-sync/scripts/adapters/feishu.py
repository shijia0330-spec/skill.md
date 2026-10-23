"""飞书 Bot 通知（推送成功后可选通知）"""

from __future__ import annotations

import os
from typing import Any

from .http_util import http_request


def notify_feishu(
    *,
    title: str,
    content: str,
    webhook_url: str | None = None,
) -> tuple[bool, str]:
    url = webhook_url or os.environ.get("FEISHU_WEBHOOK_URL", "")
    if not url:
        return False, "未配置 FEISHU_WEBHOOK_URL"

    payload: dict[str, Any] = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": title},
                "template": "red" if "失败" in title else "green",
            },
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": content}},
            ],
        },
    }
    status, body = http_request("POST", url, json_body=payload)
    if status >= 400:
        return False, f"飞书通知失败 ({status}): {body}"
    return True, "飞书通知已发送"
