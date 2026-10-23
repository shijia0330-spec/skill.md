"""失败时保存截图与 HTML。"""
from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path

from playwright.sync_api import Page


def artifacts_dir() -> Path:
    root = Path(__file__).resolve().parents[2]
    raw = os.environ.get("UI_ARTIFACTS_DIR", "output/ui_artifacts")
    p = Path(raw)
    if not p.is_absolute():
        p = root / p
    p.mkdir(parents=True, exist_ok=True)
    return p


def safe_stem(name: str, limit: int = 80) -> str:
    s = re.sub(r"[^0-9a-zA-Z._-]+", "_", name)[:limit].strip("_")
    return s or "ui_failure"


def save_failure_artifacts(page: Page, stem: str) -> tuple[Path, Path]:
    art = artifacts_dir()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = safe_stem(stem)
    png = art / f"{slug}_{ts}.png"
    html = art / f"{slug}_{ts}.html"
    page.screenshot(path=str(png), full_page=True)
    html.write_text(page.content(), encoding="utf-8")
    return png, html
