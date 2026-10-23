"""造数 refs 登记与精确 teardown（按 ID 删除，避免全表 DELETE）。"""
from __future__ import annotations

from typing import Any

from .executor import run_step
from .resolver import fill_body
from .variable_pool import VariablePool


class RefsRegistry:
    """单条 pytest 用例生命周期内的资源引用表。"""

    def __init__(self) -> None:
        self._refs: list[dict[str, Any]] = []

    def register(
        self,
        *,
        ref_type: str,
        ref_id: Any,
        delete_step: dict[str, Any],
        source: str = "",
    ) -> None:
        if ref_id is None or ref_id == "":
            return
        self._refs.append(
            {
                "ref_type": ref_type,
                "ref_id": ref_id,
                "delete_step": dict(delete_step),
                "source": source,
            }
        )

    def register_from_response(
        self,
        track_cfg: dict[str, Any],
        response_json: Any,
        *,
        source: str = "",
    ) -> None:
        """从响应 JSON 提取 ID 并登记删除步骤。track_cfg 示例见 spec track_ref。"""
        if not isinstance(track_cfg, dict):
            return
        from .json_path import extract_by_path

        ref_type = str(track_cfg.get("type") or track_cfg.get("ref_type") or "resource")
        path = track_cfg.get("json_path") or track_cfg.get("path") or "data.id"
        ref_id = extract_by_path(response_json, str(path)) if isinstance(response_json, dict) else None
        delete_step = track_cfg.get("delete") or track_cfg.get("delete_step")
        if not isinstance(delete_step, dict):
            return
        var_name = track_cfg.get("var") or f"{ref_type}_id"
        delete_copy = dict(delete_step)
        pool_snapshot = {var_name: ref_id, "id": ref_id, f"{ref_type}_id": ref_id}
        method = delete_copy.get("method") or "DELETE"
        path_tmpl = delete_copy.get("path") or ""
        delete_copy["method"] = method
        delete_copy["path"] = fill_body(path_tmpl, pool_snapshot)
        delete_copy.setdefault("expect_status", 200)
        delete_copy.pop("track_ref", None)
        self.register(ref_type=ref_type, ref_id=ref_id, delete_step=delete_copy, source=source)

    def cleanup_all(
        self,
        session: Any,
        pool: VariablePool,
        base_url: str,
        *,
        timeout_default: int = 30,
        ignore_errors: bool = True,
    ) -> list[dict[str, Any]]:
        """按登记逆序执行删除；默认忽略单条失败以便清完其余资源。"""
        results: list[dict[str, Any]] = []
        for ref in reversed(self._refs):
            step = dict(ref["delete_step"])
            step.setdefault("id", f"teardown-{ref['ref_type']}-{ref['ref_id']}")
            pool.set(f"{ref['ref_type']}_id", ref["ref_id"])
            pool.set("id", ref["ref_id"])
            try:
                resp = run_step(
                    session,
                    pool,
                    step,
                    base_url,
                    timeout_default=timeout_default,
                )
                results.append(
                    {
                        "ref_type": ref["ref_type"],
                        "ref_id": ref["ref_id"],
                        "status": resp.status_code,
                        "ok": True,
                    }
                )
            except Exception as exc:
                results.append(
                    {
                        "ref_type": ref["ref_type"],
                        "ref_id": ref["ref_id"],
                        "ok": False,
                        "error": str(exc),
                    }
                )
                if not ignore_errors:
                    raise
        self._refs.clear()
        return results

    def __len__(self) -> int:
        return len(self._refs)
