"""阿里云效 DevOps Adapter（工作项创建）"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from canonical import CanonicalDefect, format_analysis_appendix  # noqa: E402

from .base import BaseAdapter, PushResult  # noqa: E402
from .http_util import http_request  # noqa: E402


class YunXiaoAdapter(BaseAdapter):
    platform = "yunxiao"

    def validate_config(self) -> list[str]:
        missing = []
        for key in ("org_id", "project_id", "pat"):
            env_key = f"YUNXIAO_{key.upper()}"
            if not os.environ.get(env_key) and not self.config.get(key):
                missing.append(env_key)
        return missing

    def _cfg(self, key: str, default: str = "") -> str:
        env_key = f"YUNXIAO_{key.upper()}"
        return os.environ.get(env_key) or str(self.config.get(key, default))

    def map_defect(self, defect: CanonicalDefect) -> dict[str, Any]:
        sev_map = self.config.get("severity_map", {})
        defaults = self.config.get("defaults", {})
        description = (
            f"**缺陷编号**: {defect.bug_id}\n\n"
            f"**严重级别**: {defect.severity} | **优先级**: {defect.priority}\n\n"
            f"**分流**: {defect.triage}\n\n"
            f"**关联用例**: `{defect.nodeid}`\n\n"
            f"---\n\n{defect.steps}"
            f"{format_analysis_appendix(defect)}"
        )
        return {
            "subject": defect.title,
            "description": description,
            "assignedTo": defaults.get("assigned_to", ""),
            "workitemType": defaults.get("workitem_type", "Bug"),
            "priority": self._map_priority(defect.priority, self.config.get("priority_map", {})),
            "severity": self._map_severity(defect.severity, sev_map),
            "labels": [defect.bug_id, defect.defect_type],
        }

    def push(self, defect: CanonicalDefect, *, dry_run: bool = False) -> PushResult:
        payload = self.map_defect(defect)
        if dry_run:
            return PushResult(success=True, dry_run=True, payload=payload, message="dry-run")

        org_id = self._cfg("org_id")
        project_id = self._cfg("project_id")
        pat = self._cfg("pat")
        api_base = self._cfg("api_base", "https://devops.aliyun.com").rstrip("/")

        # 云效开放 API（工作项创建，具体路径因版本而异，可通过 config 覆盖）
        path = self.config.get(
            "create_path",
            f"/organization/{org_id}/projects/{project_id}/workitems",
        )
        url = f"{api_base}{path}"
        headers = {
            "Content-Type": "application/json",
            "x-yunxiao-token": pat,
            "Authorization": f"Bearer {pat}",
        }
        status, body = http_request("POST", url, headers=headers, json_body=payload)

        if status >= 400:
            return PushResult(success=False, message=f"云效建单失败 ({status}): {body}", payload=payload)

        remote_id = ""
        remote_url = ""
        if isinstance(body, dict):
            remote_id = str(
                body.get("id")
                or body.get("workitemId")
                or body.get("data", {}).get("id", "")
            )
            remote_url = str(body.get("url") or body.get("data", {}).get("url", ""))
        return PushResult(
            success=True,
            remote_id=remote_id,
            remote_url=remote_url,
            message=f"云效工作项 #{remote_id} 已创建",
            payload=payload,
        )
