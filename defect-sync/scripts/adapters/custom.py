"""自研平台 / 通用 Webhook Adapter"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from canonical import CanonicalDefect, format_analysis_appendix  # noqa: E402

from .base import BaseAdapter, PushResult  # noqa: E402
from .http_util import http_request  # noqa: E402


class CustomAdapter(BaseAdapter):
    platform = "custom"

    def validate_config(self) -> list[str]:
        if not os.environ.get("DEFECT_WEBHOOK_URL") and not self.config.get("webhook_url"):
            return ["DEFECT_WEBHOOK_URL"]
        return []

    def _webhook_url(self) -> str:
        return os.environ.get("DEFECT_WEBHOOK_URL") or str(self.config.get("webhook_url", ""))

    def _auth_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        token = os.environ.get("DEFECT_WEBHOOK_TOKEN") or self.config.get("auth_token", "")
        auth_type = self.config.get("auth_type", "bearer")
        if token:
            if auth_type == "bearer":
                headers["Authorization"] = f"Bearer {token}"
            elif auth_type == "header":
                header_name = self.config.get("auth_header", "X-API-Key")
                headers[header_name] = token
        extra = self.config.get("extra_headers", {})
        headers.update(extra)
        return headers

    def map_defect(self, defect: CanonicalDefect) -> dict[str, Any]:
        field_map = self.config.get("field_map", {})
        defaults = self.config.get("defaults", {})

        canonical = defect.to_dict()
        payload: dict[str, Any] = dict(defaults)
        for target, source in field_map.items():
            if source in canonical:
                payload[target] = canonical[source]
            elif source.startswith("$"):
                payload[target] = source[1:]
        if "title" not in payload:
            payload["title"] = defect.title
        appendix = format_analysis_appendix(defect)
        if "description" not in payload:
            payload["description"] = (defect.steps or defect.raw_markdown[:4000]) + appendix
        elif appendix and appendix not in str(payload.get("description", "")):
            payload["description"] = str(payload["description"]) + appendix
        analysis = defect.analysis_block()
        if analysis:
            payload["analysis"] = analysis
            payload["failure_category"] = analysis.get("category", "")
            payload["failure_confidence"] = analysis.get("confidence")
        if "severity" not in payload:
            payload["severity"] = defect.severity
        if "fingerprint" not in payload:
            payload["fingerprint"] = defect.fingerprint
        if "source" not in payload:
            payload["source"] = {
                "bug_id": defect.bug_id,
                "nodeid": defect.nodeid,
                "file": defect.source_file,
            }
        return payload

    def push(self, defect: CanonicalDefect, *, dry_run: bool = False) -> PushResult:
        payload = self.map_defect(defect)
        if dry_run:
            return PushResult(success=True, dry_run=True, payload=payload, message="dry-run")

        url = self._webhook_url()
        headers = self._auth_headers()
        headers.setdefault("Content-Type", "application/json")
        status, body = http_request("POST", url, headers=headers, json_body=payload)

        if status >= 400:
            return PushResult(success=False, message=f"Webhook 推送失败 ({status}): {body}", payload=payload)

        remote_id = ""
        remote_url = ""
        if isinstance(body, dict):
            id_field = self.config.get("response_id_field", "id")
            url_field = self.config.get("response_url_field", "url")
            remote_id = str(body.get(id_field) or body.get("data", {}).get(id_field, ""))
            remote_url = str(body.get(url_field) or body.get("data", {}).get(url_field, ""))

        return PushResult(
            success=True,
            remote_id=remote_id or defect.bug_id,
            remote_url=remote_url,
            message=f"Webhook 推送成功 ({status})",
            payload=payload,
        )
