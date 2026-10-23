"""禅道 REST API v1 Adapter"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from canonical import CanonicalDefect, format_analysis_appendix  # noqa: E402

from .base import BaseAdapter, PushResult  # noqa: E402
from .http_util import http_request  # noqa: E402


class ZenTaoAdapter(BaseAdapter):
    platform = "zentao"

    def validate_config(self) -> list[str]:
        missing = []
        for key in ("base_url", "account", "password", "product_id"):
            env_key = f"ZENTAO_{key.upper()}"
            if not os.environ.get(env_key) and not self.config.get(key):
                missing.append(env_key)
        return missing

    def _cfg(self, key: str, default: str = "") -> str:
        env_key = f"ZENTAO_{key.upper()}"
        return os.environ.get(env_key) or str(self.config.get(key, default))

    def _get_token(self) -> str:
        cached = getattr(self, "_token", None)
        if cached:
            return cached
        base = self._cfg("base_url").rstrip("/")
        account = self._cfg("account")
        password = self._cfg("password")
        url = f"{base}/api.php/v1/tokens"
        status, body = http_request("POST", url, json_body={"account": account, "password": password})
        if status >= 400:
            raise RuntimeError(f"禅道登录失败 ({status}): {body}")
        if isinstance(body, dict):
            token = body.get("token") or body.get("data", {}).get("token", "")
        else:
            token = ""
        if not token:
            raise RuntimeError(f"禅道登录未返回 token: {body}")
        self._token = token
        return token

    def map_defect(self, defect: CanonicalDefect) -> dict[str, Any]:
        sev_map = self.config.get("severity_map", {})
        pri_map = self.config.get("priority_map", {})
        type_map = self.config.get("type_map", {})
        defaults = self.config.get("defaults", {})

        steps = (
            f"【发现方式】{defect.discovered_via}\n"
            f"【发现时间】{defect.discovered_at}\n"
            f"【关联用例】{defect.nodeid}\n"
            f"【分流】{defect.triage}\n\n"
            f"{defect.steps}"
            f"{format_analysis_appendix(defect)}"
        )

        return {
            "title": defect.title,
            "severity": self._map_severity(defect.severity, sev_map),
            "pri": self._map_priority(defect.priority, pri_map),
            "type": type_map.get(defect.defect_type, defaults.get("type", "codeerror")),
            "steps": steps,
            "openedBuild": defaults.get("opened_build", ""),
            "assignedTo": defaults.get("assigned_to", ""),
            "module": defect.module or defaults.get("module", 0),
            "keywords": defect.bug_id,
        }

    def push(self, defect: CanonicalDefect, *, dry_run: bool = False) -> PushResult:
        payload = self.map_defect(defect)
        if dry_run:
            return PushResult(success=True, dry_run=True, payload=payload, message="dry-run")

        base = self._cfg("base_url").rstrip("/")
        product_id = self._cfg("product_id")
        token = self._get_token()
        url = f"{base}/api.php/v1/products/{product_id}/bugs"
        headers = {"Token": token, "Content-Type": "application/json"}
        status, body = http_request("POST", url, headers=headers, json_body=payload)

        if status >= 400:
            return PushResult(success=False, message=f"禅道建单失败 ({status}): {body}", payload=payload)

        remote_id = ""
        if isinstance(body, dict):
            remote_id = str(body.get("id") or body.get("data", {}).get("id", ""))
        remote_url = f"{base}/bug-view-{remote_id}.html" if remote_id else ""
        return PushResult(
            success=True,
            remote_id=remote_id,
            remote_url=remote_url,
            message=f"禅道缺陷 #{remote_id} 已创建",
            payload=payload,
        )
