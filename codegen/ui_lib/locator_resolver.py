"""Playwright 定位器：CACHE → L1（八种）→ L2(contains) → L4(坐标) 降级。

V3.1：L1 顺序对齐 locator_healer；失败输出候选节点 JSON。
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
import warnings
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from playwright.sync_api import Locator, Page

from api_lib.resolver import fill_body, resolve_env

from .artifacts import artifacts_dir
from .context import UIContext
from .heal_kb import UIHealKB
from .selector_registry import merge_registry_step

logger = logging.getLogger(__name__)

_LOCATOR_TIMEOUT_MS = int(os.environ.get("UI_LOCATOR_TIMEOUT_MS", "15000"))
_L4_MAX_PER_STEP = int(os.environ.get("UI_L4_MAX_PER_STEP", "1"))
_L4_MAX_PER_CASE = int(os.environ.get("UI_L4_MAX_PER_CASE", "3"))
_CACHE_MAX = int(os.environ.get("UI_LOCATOR_CACHE_MAX", "500"))
_L2_MAX_CANDIDATES = int(os.environ.get("UI_L2_MAX_CANDIDATES", "24"))

STRATEGY_CONFIDENCE: dict[str, float] = {
    "L1_testid": 0.98,
    "L1_role": 0.95,
    "L1_label": 0.93,
    "L1_id": 0.92,
    "L1_name_attr": 0.92,
    "L1_aria_label": 0.90,
    "L1_text": 0.75,
    "L1_placeholder": 0.85,
    "L1_css": 0.70,
    "L1_target": 0.95,
    "L2": 0.65,
    "L2_context": 0.70,
    "L4": 0.40,
}


@dataclass
class ResolveMeta:
    strategy: str = ""
    level: str = "L1"
    confidence: float = 0.0
    healed: bool = False
    attempts: list[dict[str, Any]] = field(default_factory=list)
    candidates: list[dict[str, Any]] = field(default_factory=list)
    warning: str = ""


class LocatorResolutionError(RuntimeError):
    def __init__(self, message: str, *, meta: ResolveMeta, step: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.meta = meta
        self.step = step or {}


class _LocatorLRUCache:
    """键: url:action:target → 策略名。"""

    def __init__(self, maxsize: int = 500) -> None:
        self._max = maxsize
        self._data: OrderedDict[str, str] = OrderedDict()

    def get(self, key: str) -> str | None:
        if key not in self._data:
            return None
        self._data.move_to_end(key)
        return self._data[key]

    def set(self, key: str, strategy: str) -> None:
        self._data[key] = strategy
        self._data.move_to_end(key)
        while len(self._data) > self._max:
            self._data.popitem(last=False)


_LOCATOR_CACHE = _LocatorLRUCache(_CACHE_MAX)
_l4_case_count = 0
_l4_step_used = False


def reset_l4_counters() -> None:
    global _l4_case_count, _l4_step_used  # noqa: PLW0603
    _l4_case_count = 0
    _l4_step_used = False


def _step_root(page: Page, step: dict[str, Any], ctx: UIContext) -> Page | Locator:
    from .scopes import resolve_scope

    return resolve_scope(page, step, ctx)


def _cache_key(page: Page, step: dict[str, Any], action: str = "locate") -> str:
    url = getattr(page, "url", "").split("?")[0]
    parts = [
        step.get("registry_key"),
        step.get("scope"),
        step.get("dialog_title"),
        step.get("l1_name"),
        step.get("l1_name_regex"),
        step.get("l1_label"),
        step.get("l1_placeholder"),
        step.get("l1_test_id"),
        step.get("l1_aria_label"),
        step.get("l2_css"),
        step.get("value"),
    ]
    target = "|".join(str(p) for p in parts if p)
    return f"{url}:{action}:{target}"


def resolve_string(val: Any, ctx: UIContext) -> str:
    if not isinstance(val, str):
        return str(val)
    if val.startswith("__ENV__:"):
        return resolve_env(val)
    return fill_body(val, ctx.as_dict())


def _confidence(name: str, *, ambiguous: bool = False) -> float:
    if name in STRATEGY_CONFIDENCE:
        base = STRATEGY_CONFIDENCE[name]
    elif name.startswith("L2_context"):
        base = 0.70
    elif name.startswith("L2"):
        base = 0.65
    elif name.startswith("L1_text"):
        base = 0.75
    else:
        base = 0.50
    if ambiguous:
        base = min(base, 0.80)
    return round(base, 2)


def _build_l1_strategies(
    root: Page | Locator,
    step: dict[str, Any],
    ctx: UIContext,
) -> list[tuple[str, float, Callable[[], Locator]]]:
    """L1：testid → role → label → id/name → aria-label → text → placeholder → css。"""
    strategies: list[tuple[str, float, Callable[[], Locator]]] = []

    raw = step.get("target")
    if isinstance(raw, str) and raw.strip():
        r = resolve_string(raw, ctx)
        if r.startswith(("xpath=", "text=", "role=", "css=")):
            sel = r.split("=", 1)[1] if r.startswith("css=") else r
            strategies.append(("L1_target", 0.95, lambda s=sel: root.locator(s)))

    if step.get("l1_test_id"):
        tid = resolve_string(step["l1_test_id"], ctx)
        strategies.append(("L1_testid", 0.98, lambda t=tid: root.get_by_test_id(t)))

    role = step.get("l1_role")
    if role and step.get("l1_name_regex"):
        pat = re.compile(resolve_string(step["l1_name_regex"], ctx))
        strategies.append(("L1_role", 0.95, lambda r=str(role), p=pat: root.get_by_role(r, name=p)))
    elif role and step.get("l1_name"):
        nm = resolve_string(step["l1_name"], ctx)
        strategies.append(("L1_role", 0.95, lambda r=str(role), n=nm: root.get_by_role(r, name=n)))
    elif role:
        strategies.append(("L1_role", 0.90, lambda r=str(role): root.get_by_role(r)))

    if role == "button":
        strategies.append(("L1_submit", 0.88, lambda: root.locator('button[type="submit"]').first))

    if step.get("l1_label"):
        lb = resolve_string(step["l1_label"], ctx)
        strategies.append(("L1_label", 0.93, lambda l=lb: root.get_by_label(l)))

    if step.get("l1_id"):
        eid = resolve_string(step["l1_id"], ctx).lstrip("#")
        strategies.append(("L1_id", 0.92, lambda i=eid: root.locator(f"#{i}")))

    if step.get("l1_name_attr"):
        na = resolve_string(step["l1_name_attr"], ctx)
        strategies.append(("L1_name_attr", 0.92, lambda n=na: root.locator(f'[name="{n}"]')))

    if step.get("l1_aria_label"):
        al = resolve_string(step["l1_aria_label"], ctx)
        strategies.append(("L1_aria_label", 0.90, lambda a=al: root.locator(f'[aria-label="{a}"]')))

    if step.get("l1_placeholder"):
        ph = resolve_string(step["l1_placeholder"], ctx)
        strategies.append(("L1_placeholder", 0.85, lambda p=ph: root.get_by_placeholder(p)))

    for key in ("l1_name", "l1_label"):
        raw_val = step.get(key)
        if isinstance(raw_val, str) and raw_val.strip():
            text = resolve_string(raw_val, ctx)
            strategies.append((f"L1_text_{key}", 0.75, lambda t=text: root.get_by_text(t, exact=False)))

    if step.get("l2_css"):
        sel = resolve_string(step["l2_css"], ctx)
        strategies.append(("L1_css", 0.70, lambda s=sel: root.locator(s)))

    return strategies


def _loc_l1(root: Page | Locator, step: dict[str, Any], ctx: UIContext) -> Locator | None:
    strategies = _build_l1_strategies(root, step, ctx)
    return strategies[0][2]() if strategies else None


def _tokens_from_step(step: dict[str, Any], ctx: UIContext) -> list[str]:
    out: list[str] = []
    for key in ("l1_name", "l1_label", "l1_placeholder", "l1_aria_label", "value", "l1_test_id", "l1_id", "l1_name_attr"):
        v = step.get(key)
        if isinstance(v, str) and len(v.strip()) >= 2:
            out.append(resolve_string(v, ctx))
    return out


def _loc_l2_contains(root: Page | Locator, step: dict[str, Any], ctx: UIContext) -> list[tuple[str, Locator]]:
    locs: list[tuple[str, Locator]] = []
    role = str(step.get("l1_role") or "")
    role_tag = {"button": "button", "link": "a", "textbox": "input", "combobox": "select"}.get(role, "")

    for tok in _tokens_from_step(step, ctx)[:3]:
        safe = tok.replace("'", "\\'")
        for xp in (
            f"//*[contains(@placeholder,'{safe}')]",
            f"//*[contains(@name,'{safe}')]",
            f"//*[contains(@id,'{safe}')]",
            f"//*[contains(@aria-label,'{safe}')]",
            f"//*[contains(@class,'{safe}')]",
            f"//*[contains(text(),'{safe}')]",
        ):
            locs.append(("L2_contains", root.locator(f"xpath={xp}")))
        frag = re.sub(r"[^\w\u4e00-\u9fff]+", "", tok)[:12]
        if len(frag) >= 2:
            locs.append(("L2_text", root.locator(f"text={frag}")))
        if role_tag:
            locs.append(
                ("L2_context", root.locator(f"{role_tag}[id*='{safe}'], {role_tag}[name*='{safe}'], {role_tag}[aria-label*='{safe}']"))
            )
    return locs[:_L2_MAX_CANDIDATES]


def build_locator_strategies(
    page: Page,
    step: dict[str, Any],
    ctx: UIContext,
    *,
    heal_kb: UIHealKB | None = None,
    action: str = "locate",
) -> list[tuple[str, Callable[[], Locator]]]:
    step = merge_registry_step(step)
    root = _step_root(page, step, ctx)
    strategies: list[tuple[str, Callable[[], Locator]]] = []

    if heal_kb:
        alt = heal_kb.get_alternate_step(step)
        if alt:
            strategies.append(
                ("heal_kb_history", lambda a=alt: _require_loc(page, a, ctx))
            )

    for name, _conf, factory in _build_l1_strategies(root, step, ctx):
        strategies.append((name, factory))

    if _self_heal_enabled():
        for l2_name, loc in _loc_l2_contains(root, step, ctx):
            strategies.append((l2_name, lambda loc=loc: loc))

    ck = _cache_key(page, step, action)
    cached = _LOCATOR_CACHE.get(ck)
    if cached:
        for i, (name, fn) in enumerate(strategies):
            if name == cached:
                strategies.insert(0, (f"CACHE:{cached}", fn))
                break

    return strategies


def _require_loc(page: Page, step: dict[str, Any], ctx: UIContext) -> Locator:
    root = _step_root(page, step, ctx)
    loc = _loc_l1(root, step, ctx)
    if loc is None:
        raise ValueError(f"无法构建定位器: {step}")
    return loc


def get_locator(
    page: Page,
    step: dict[str, Any],
    ctx: UIContext,
    *,
    heal_kb: UIHealKB | None = None,
) -> Locator:
    strategies = build_locator_strategies(page, step, ctx, heal_kb=heal_kb)
    if not strategies:
        raise ValueError(f"步骤缺少定位字段: {step}")
    return strategies[0][1]()


def _collect_dom_candidates(page: Page, step: dict[str, Any], ctx: UIContext, limit: int = 8) -> list[dict[str, Any]]:
    tokens = _tokens_from_step(step, ctx)
    keywords = [re.sub(r"[^\w\u4e00-\u9fff]+", "", t) for t in tokens if t]
    script = """
    (keywords) => {
      const nodes = Array.from(document.querySelectorAll(
        'button, a, input, select, textarea, [role="button"], [role="link"], [role="textbox"]'
      ));
      const scored = [];
      for (const el of nodes) {
        const r = el.getBoundingClientRect();
        if (r.width < 4 || r.height < 4) continue;
        const st = getComputedStyle(el);
        if (st.visibility === 'hidden' || st.display === 'none') continue;
        const text = (el.innerText || el.value || '').trim().slice(0, 80);
        const id = el.id || '';
        const name = el.getAttribute('name') || '';
        const aria = el.getAttribute('aria-label') || '';
        const ph = el.getAttribute('placeholder') || '';
        const tag = el.tagName.toLowerCase();
        const blob = `${text} ${id} ${name} ${aria} ${ph}`;
        let score = 0;
        for (const kw of keywords) {
          if (kw && blob.includes(kw)) score += 30;
        }
        scored.push({ tag, id, name, aria_label: aria, placeholder: ph, text, score });
      }
      scored.sort((a, b) => b.score - a.score);
      return scored.slice(0, 20);
    }
    """
    try:
        items = page.evaluate(script, keywords)
        return items[:limit]
    except Exception:  # noqa: BLE001
        return []


def _save_locator_failure_json(page: Page, step: dict[str, Any], meta: ResolveMeta, action: str) -> Path | None:
    if os.environ.get("UI_LOCATOR_DEBUG", "1").strip().lower() in ("0", "false", "no", "off"):
        return None
    art = artifacts_dir()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    rk = step.get("registry_key") or step.get("l1_label") or action
    slug = re.sub(r"[^0-9a-zA-Z._-]+", "_", str(rk))[:40]
    out = art / f"locator_fail_{slug}_{ts}.json"
    payload = {
        "action": action,
        "step": {k: v for k, v in step.items() if not str(k).startswith("_")},
        "url": page.url,
        "meta": {
            "strategy": meta.strategy,
            "level": meta.level,
            "confidence": meta.confidence,
            "healed": meta.healed,
            "attempts": meta.attempts,
            "candidates": meta.candidates,
            "warning": meta.warning,
        },
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def dismiss_page_modals(page: Page) -> None:
    """关闭可能残留的弹窗（batch 切换 flow 前调用）。"""
    for sel in (
        ".ant-modal-wrap .ant-modal-close",
        "[class*='modal'] button[aria-label='Close']",
        "button:has-text('取消')",
    ):
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=200):
                loc.click(timeout=500)
        except Exception:  # noqa: BLE001
            pass


def _dismiss_modals(page: Page) -> None:
    dismiss_page_modals(page)


def _coordinate_click_l4(page: Page, step: dict[str, Any], ctx: UIContext) -> bool:
    global _l4_case_count, _l4_step_used  # noqa: PLW0603
    if _l4_step_used or _l4_case_count >= _L4_MAX_PER_CASE:
        return False
    _dismiss_modals(page)
    tokens = _tokens_from_step(step, ctx)
    keywords = [re.sub(r"[^\w\u4e00-\u9fff]+", "", t) for t in tokens if t]
    script = """
    () => {
      const nodes = Array.from(document.querySelectorAll(
        'button, a, [role="button"], input[type="submit"], .btn'
      ));
      const scored = [];
      for (const el of nodes) {
        const r = el.getBoundingClientRect();
        if (r.width < 8 || r.height < 8) continue;
        const st = getComputedStyle(el);
        if (st.visibility === 'hidden' || st.display === 'none') continue;
        const text = (el.innerText || el.value || el.getAttribute('aria-label') || '').trim();
        const id = el.id || '';
        const cls = el.className || '';
        scored.push({ x: r.x + r.width/2, y: r.y + r.height/2, text, id, cls });
      }
      return scored;
    }
    """
    try:
        items = page.evaluate(script)
    except Exception:  # noqa: BLE001
        return False
    if not items:
        return False
    best = None
    best_score = -1
    for it in items:
        score = 0
        blob = f"{it.get('text','')} {it.get('id','')} {it.get('cls','')}"
        for kw in keywords:
            if kw and kw in blob:
                score += 30
        for tok in tokens:
            if tok and tok in blob:
                score += 100
        if score > best_score:
            best_score = score
            best = it
    if best is None or best_score < 20:
        best = items[0]
        best_score = 20
    page.mouse.click(best["x"], best["y"])
    _l4_step_used = True
    _l4_case_count += 1
    return True


def _run_with_strategies(
    page: Page,
    step: dict[str, Any],
    ctx: UIContext,
    *,
    heal_kb: UIHealKB | None = None,
    action: str,
    do_action: Callable[[Locator], None],
    timeout_ms: int,
) -> str:
    budget_ms = int(step.get("timeout_ms") or timeout_ms or _LOCATOR_TIMEOUT_MS)
    deadline = time.monotonic() + budget_ms / 1000.0
    ck = _cache_key(page, step, action)
    last_err: Exception | None = None
    meta = ResolveMeta()
    strategies = build_locator_strategies(page, step, ctx, heal_kb=heal_kb, action=action)
    first_name = strategies[0][0] if strategies else ""

    for name, get_loc in strategies:
        if time.monotonic() > deadline:
            break
        if name.startswith("CACHE:"):
            continue
        level = "L2" if name.startswith("L2") else "L1"
        t0 = time.monotonic()
        try:
            loc = get_loc()
            do_action(loc)
            elapsed = round((time.monotonic() - t0) * 1000, 1)
            conf = _confidence(name)
            meta.strategy = name
            meta.level = level
            meta.confidence = conf
            meta.healed = name != first_name
            meta.attempts.append({"strategy": name, "level": level, "ok": True, "ms": elapsed, "confidence": conf})
            _LOCATOR_CACHE.set(ck, name)
            if heal_kb and name != first_name:
                heal_kb.record_fix(step, step, {"strategy": name, "confidence": conf})
            if level == "L2":
                meta.warning = f"L2 推理命中 {name}（confidence={conf}），建议人工复核"
                warnings.warn(meta.warning, stacklevel=3)
                logger.warning(meta.warning)
            return name
        except Exception as exc:  # noqa: BLE001
            elapsed = round((time.monotonic() - t0) * 1000, 1)
            meta.attempts.append({"strategy": name, "level": level, "ok": False, "ms": elapsed, "error": str(exc)[:120]})
            last_err = exc

    if time.monotonic() <= deadline and _coordinate_click_l4(page, step, ctx):
        _LOCATOR_CACHE.set(ck, "L4")
        meta.strategy = "L4"
        meta.level = "L4"
        meta.confidence = STRATEGY_CONFIDENCE["L4"]
        meta.healed = True
        meta.warning = "L4 坐标兜底，仅调试用"
        warnings.warn(meta.warning, stacklevel=3)
        return "L4"

    meta.candidates = _collect_dom_candidates(page, step, ctx)
    _save_locator_failure_json(page, step, meta, action)
    assert last_err is not None
    raise LocatorResolutionError(
        f"定位失败 action={action}（已试 {len(meta.attempts)} 次，候选 {len(meta.candidates)} 个）: {last_err}",
        meta=meta,
        step=step,
    ) from last_err


def _self_heal_enabled() -> bool:
    return os.environ.get("UI_SELF_HEAL", "1").strip().lower() not in ("0", "false", "no", "off")


def click_with_healing(
    page: Page,
    step: dict[str, Any],
    ctx: UIContext,
    *,
    heal_kb: UIHealKB | None = None,
    timeout_ms: int = 15000,
) -> str:
    global _l4_step_used  # noqa: PLW0603
    _l4_step_used = False
    budget_ms = int(step.get("timeout_ms") or timeout_ms or _LOCATOR_TIMEOUT_MS)
    if not _self_heal_enabled():
        for _name, get_loc in build_locator_strategies(page, step, ctx, heal_kb=None, action="click"):
            if not _name.startswith("CACHE:"):
                get_loc().click(timeout=budget_ms)
                return _name
        raise RuntimeError("click 失败（UI_SELF_HEAL=0）")
    return _run_with_strategies(
        page,
        step,
        ctx,
        heal_kb=heal_kb,
        action="click",
        do_action=lambda loc: loc.click(timeout=budget_ms),
        timeout_ms=budget_ms,
    )


def fill_with_healing(
    page: Page,
    step: dict[str, Any],
    value: str,
    ctx: UIContext,
    *,
    heal_kb: UIHealKB | None = None,
    timeout_ms: int = 15000,
) -> str:
    global _l4_step_used  # noqa: PLW0603
    _l4_step_used = False
    budget_ms = int(step.get("timeout_ms") or timeout_ms or _LOCATOR_TIMEOUT_MS)
    if not _self_heal_enabled():
        for _name, get_loc in build_locator_strategies(page, step, ctx, heal_kb=None, action="fill"):
            if not _name.startswith("CACHE:"):
                get_loc().fill(value, timeout=budget_ms)
                return _name
        raise RuntimeError("fill 失败（UI_SELF_HEAL=0）")
    return _run_with_strategies(
        page,
        step,
        ctx,
        heal_kb=heal_kb,
        action="fill",
        do_action=lambda loc: loc.fill(value, timeout=budget_ms),
        timeout_ms=budget_ms,
    )
