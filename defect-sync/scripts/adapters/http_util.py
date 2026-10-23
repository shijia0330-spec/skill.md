"""轻量 HTTP 工具，优先 requests，降级 urllib"""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request
from typing import Any


def http_request(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    json_body: dict[str, Any] | None = None,
    data: bytes | None = None,
    timeout: int = 30,
) -> tuple[int, dict[str, Any] | str]:
    try:
        import requests  # type: ignore

        resp = requests.request(
            method,
            url,
            headers=headers,
            json=json_body,
            data=data,
            timeout=timeout,
        )
        try:
            body: dict[str, Any] | str = resp.json()
        except Exception:
            body = resp.text
        return resp.status_code, body
    except ImportError:
        pass

    req_headers = dict(headers or {})
    payload = data
    if json_body is not None:
        payload = json.dumps(json_body, ensure_ascii=False).encode("utf-8")
        req_headers.setdefault("Content-Type", "application/json")

    req = urllib.request.Request(url, data=payload, headers=req_headers, method=method.upper())
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            raw = resp.read().decode("utf-8")
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, raw
