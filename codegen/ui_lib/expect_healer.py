"""UI expect 断言轻量自愈 — 失败时尝试放宽匹配。"""
from __future__ import annotations

import copy
import os
import re
from typing import Any

from playwright.sync_api import Page, expect

from .context import UIContext
from .locator_resolver import resolve_string

HEALABLE_TYPES = frozenset(
    {
        "visible_text",
        "url_regex",
        "title_contains",
        "role_visible",
        "columnheader_visible",
        "alert_visible",
        "locator_visible",
        "visible",
    }
)


def _expect_heal_enabled() -> bool:
    return os.environ.get("UI_EXPECT_HEAL", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def is_healable_expect(ex: dict[str, Any]) -> bool:
    t = str(ex.get("type") or "").strip().lower()
    return t in HEALABLE_TYPES


def _heal_alternatives(ex: dict[str, Any]) -> list[dict[str, Any]]:
    t = str(ex.get("type") or "").strip().lower()
    alts: list[dict[str, Any]] = []

    if t == "visible_text":
        text = str(ex.get("text") or "")
        if ex.get("exact"):
            loose = copy.deepcopy(ex)
            loose["exact"] = False
            alts.append(loose)
        frag = text.strip()[: min(12, len(text.strip()))]
        if len(frag) >= 2 and frag != text.strip():
            partial = copy.deepcopy(ex)
            partial["text"] = frag
            partial["exact"] = False
            alts.append(partial)

    elif t == "url_regex":
        pat = str(ex.get("pattern") or "")
        if pat and not pat.startswith(".*"):
            broader = copy.deepcopy(ex)
            broader["pattern"] = f".*{re.escape(pat)}.*"
            alts.append(broader)

    elif t == "title_contains":
        pat = str(ex.get("pattern") or "")
        if len(pat) > 4:
            shorter = copy.deepcopy(ex)
            shorter["pattern"] = pat[: max(4, len(pat) // 2)]
            alts.append(shorter)

    elif t in ("role_visible", "columnheader_visible", "locator_visible", "visible", "alert_visible"):
        name = ex.get("l1_name")
        if isinstance(name, str) and len(name) > 2:
            partial = copy.deepcopy(ex)
            partial["l1_name_regex"] = re.escape(name[: max(4, len(name) // 2)])
            partial.pop("l1_name", None)
            alts.append(partial)

    return alts


def _run_single_expect(page: Page, ex: dict[str, Any], ctx: UIContext) -> None:
    t = str(ex.get("type") or "").strip().lower()
    if t == "url_regex":
        pat = resolve_string(ex.get("pattern", ".*"), ctx)
        expect(page).to_have_url(re.compile(pat))
    elif t == "title_contains":
        pat = resolve_string(ex.get("pattern", ".*"), ctx)
        expect(page).to_have_title(re.compile(pat))
    elif t in (
        "visible_text",
        "role_visible",
        "columnheader_visible",
        "alert_visible",
        "locator_visible",
        "visible",
    ):
        from .runner import _expect_locator

        expect(_expect_locator(page, ex, ctx)).to_be_visible(
            timeout=int(ex.get("timeout_ms") or 5000)
        )
    else:
        raise RuntimeError(f"expect_healer 不处理 type={t!r}")


def run_expect_with_healing(page: Page, ex: dict[str, Any], ctx: UIContext) -> str | None:
    """执行 expect；严格匹配成功返回 None，自愈成功返回策略名。"""
    candidates = [ex]
    if _expect_heal_enabled():
        candidates.extend(_heal_alternatives(ex))

    last_err: Exception | None = None
    for i, candidate in enumerate(candidates):
        try:
            _run_single_expect(page, candidate, ctx)
            return None if i == 0 else f"expect_heal_{i}"
        except Exception as exc:  # noqa: BLE001
            last_err = exc

    assert last_err is not None
    raise last_err
