"""UI 自愈知识库。"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class UIHealKB:
    def __init__(self, cache_dir: str | Path | None = None) -> None:
        root = Path(__file__).resolve().parents[2]
        self.cache_dir = Path(cache_dir or root / ".heal_cache" / "ui")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self.cache_dir / "index.json"
        self._index: dict[str, Any] = self._load()

    def _load(self) -> dict[str, Any]:
        if self._index_path.is_file():
            try:
                return json.loads(self._index_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"fixes": []}

    def _save(self) -> None:
        self._index_path.write_text(
            json.dumps(self._index, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _step_key(self, step: dict[str, Any]) -> str:
        action = step.get("action") or ""
        # scope / dialog_title 必须占位（空串也保留），避免弹窗内与页面级同 label 串键
        parts = [
            action,
            step.get("scope") if step.get("scope") is not None else "",
            step.get("dialog_title") if step.get("dialog_title") is not None else "",
            step.get("l1_test_id"),
            step.get("l1_label"),
            step.get("l1_placeholder"),
            step.get("l1_role"),
            step.get("l1_name"),
            step.get("l1_name_regex"),
            step.get("l2_css"),
            step.get("path"),
        ]
        return "|".join("" if p is None else str(p) for p in parts)

    def get_alternate_step(self, step: dict[str, Any]) -> dict[str, Any] | None:
        key = self._step_key(step)
        step_scope = str(step.get("scope") or "")
        step_dlg = str(step.get("dialog_title") or "")
        for item in reversed(self._index.get("fixes") or []):
            if item.get("step_key") != key:
                continue
            patched = item.get("patched_step")
            if not isinstance(patched, dict):
                continue
            # 兼容旧缓存（step_key 未含 scope）：scope 不一致则跳过
            if str(patched.get("scope") or "") != step_scope:
                continue
            if str(patched.get("dialog_title") or "") != step_dlg:
                continue
            return patched
        return None

    def record_fix(self, step: dict[str, Any], patched_step: dict[str, Any], meta: dict[str, Any] | None = None) -> None:
        entry = {
            "step_key": self._step_key(step),
            "original": step,
            "patched_step": patched_step,
            "meta": meta or {},
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        fixes: list = self._index.setdefault("fixes", [])
        fixes.append(entry)
        if len(fixes) > 300:
            self._index["fixes"] = fixes[-300:]
        self._save()
