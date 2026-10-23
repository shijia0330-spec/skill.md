"""自愈知识库：持久化修复模式供复用。"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class HealKB:
    def __init__(self, cache_dir: str | Path | None = None) -> None:
        root = Path(__file__).resolve().parents[2]
        self.cache_dir = Path(cache_dir or root / ".heal_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self.cache_dir / "index.json"
        self._index: dict[str, Any] = self._load_index()

    def _load_index(self) -> dict[str, Any]:
        if self._index_path.is_file():
            try:
                return json.loads(self._index_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"patterns": []}

    def _save_index(self) -> None:
        self._index_path.write_text(
            json.dumps(self._index, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def record(self, pattern_type: str, url: str, meta: dict[str, Any] | None = None) -> None:
        entry = {
            "type": pattern_type,
            "url": url,
            "meta": meta or {},
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        patterns: list = self._index.setdefault("patterns", [])
        patterns.append(entry)
        if len(patterns) > 500:
            self._index["patterns"] = patterns[-500:]
        self._save_index()

        safe = url.replace("/", "_").replace(":", "_")[:80]
        detail_path = self.cache_dir / f"{pattern_type}_{safe}.json"
        detail_path.write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8")

    def get_patterns(self, pattern_type: str | None = None) -> list[dict[str, Any]]:
        patterns = self._index.get("patterns") or []
        if pattern_type:
            return [p for p in patterns if p.get("type") == pattern_type]
        return list(patterns)
