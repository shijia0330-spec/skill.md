"""同步状态持久化：fingerprint → 远端缺陷 ID，防止重复建单"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

ENGINE_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_STATE_FILE = ENGINE_ROOT / "output" / "bugs" / "sync_state.json"


class SyncState:
    def __init__(self, path: Path | None = None):
        self.path = path or DEFAULT_STATE_FILE
        self._data: dict[str, Any] = {"records": {}}
        self._load()

    def _load(self) -> None:
        if self.path.is_file():
            self._data = json.loads(self.path.read_text(encoding="utf-8"))
        if "records" not in self._data:
            self._data["records"] = {}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get(self, fingerprint: str) -> dict[str, Any] | None:
        return self._data["records"].get(fingerprint)

    def is_synced(self, fingerprint: str, platform: str | None = None) -> bool:
        rec = self.get(fingerprint)
        if not rec:
            return False
        if platform and rec.get("platform") != platform:
            return False
        return bool(rec.get("remote_id"))

    def record(
        self,
        fingerprint: str,
        *,
        bug_id: str,
        platform: str,
        remote_id: str,
        remote_url: str = "",
        source_file: str = "",
    ) -> None:
        self._data["records"][fingerprint] = {
            "fingerprint": fingerprint,
            "bug_id": bug_id,
            "platform": platform,
            "remote_id": remote_id,
            "remote_url": remote_url,
            "source_file": source_file,
            "synced_at": datetime.now().isoformat(timespec="seconds"),
        }
        self.save()
