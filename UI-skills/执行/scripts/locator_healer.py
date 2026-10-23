"""
Playwright Web 定位自愈 — 七种策略 + L2 DOM 推断 + L3 input type 兜底。

Web 端 L1/L2 定位自愈（无 Scrapling/视觉依赖时仍可用）。

策略顺序: testid → role → label → placeholder → id → text → css → l2_dom → l3_input_type

环境变量：
  UI_SELF_HEAL=1|0           默认 1
  UI_HEAL_TIMEOUT_MS=500     单次尝试超时（毫秒）
  UI_ENABLE_AI_LOCATOR=0|1   默认 0；为 1 且 NL 服务可用时可走 L3（占位）
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Literal

StrategyName = Literal[
    "testid",
    "role",
    "label",
    "placeholder",
    "id",
    "text",
    "css",
    "l2_dom",
]


def _heal_enabled() -> bool:
    return os.environ.get("UI_SELF_HEAL", "1").strip().lower() not in ("0", "false", "no", "off")


def _timeout_ms() -> int:
    raw = os.environ.get("UI_HEAL_TIMEOUT_MS", os.environ.get("UI_LOCATOR_TIMEOUT_MS", "500")).strip()
    try:
        return max(100, int(raw))
    except ValueError:
        return 500


@dataclass
class LocatorHints:
    """元素定位提示 — 七种策略的数据源。"""

    testid: str = ""
    role: str = ""
    name: str = ""
    label: str = ""
    placeholder: str = ""
    element_id: str = ""
    text: str = ""
    css: str = ""
    xpath: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "testid": self.testid,
            "role": self.role,
            "name": self.name,
            "label": self.label,
            "placeholder": self.placeholder,
            "id": self.element_id,
            "text": self.text,
            "css": self.css,
            "xpath": self.xpath,
        }


@dataclass
class HealResult:
    healed: bool = False
    strategy: str = ""
    level: str = "L1"
    attempts: list[dict[str, Any]] = field(default_factory=list)
    elapsed_ms: float = 0.0


def _try_locator(page: Any, factory: Callable[[], Any], strategy: str, timeout_ms: int) -> tuple[Any | None, dict]:
    t0 = time.perf_counter()
    try:
        loc = factory()
        loc.first.wait_for(state="attached", timeout=timeout_ms)
        ms = (time.perf_counter() - t0) * 1000
        return loc.first, {"strategy": strategy, "ok": True, "ms": round(ms, 1)}
    except Exception as exc:  # noqa: BLE001
        ms = (time.perf_counter() - t0) * 1000
        return None, {"strategy": strategy, "ok": False, "ms": round(ms, 1), "error": str(exc)[:120]}


def _build_l1_attempts(page: Any, hints: LocatorHints) -> list[tuple[str, Callable[[], Any]]]:
    attempts: list[tuple[str, Callable[[], Any]]] = []

    if hints.testid:
        tid = hints.testid
        attempts.append(("testid", lambda: page.get_by_test_id(tid)))

    if hints.role:
        if hints.name:
            nm = hints.name
            attempts.append(("role", lambda: page.get_by_role(hints.role, name=nm)))  # type: ignore[arg-type]
        attempts.append(("role", lambda: page.get_by_role(hints.role)))  # type: ignore[arg-type]

    if hints.label:
        lb = hints.label
        attempts.append(("label", lambda: page.get_by_label(lb)))

    if hints.placeholder:
        ph = hints.placeholder
        attempts.append(("placeholder", lambda: page.get_by_placeholder(ph)))

    if hints.element_id:
        eid = hints.element_id.lstrip("#")
        attempts.append(("id", lambda: page.locator(f"#{eid}")))

    if hints.text:
        tx = hints.text
        attempts.append(("text", lambda: page.get_by_text(tx, exact=False)))

    if hints.css:
        sel = hints.css
        attempts.append(("css", lambda: page.locator(sel)))

    if hints.xpath:
        xp = hints.xpath
        attempts.append(("css", lambda: page.locator(f"xpath={xp}")))

    return attempts


def _build_l3_attempts(root: Any, hints: LocatorHints, action: str = "fill") -> list[tuple[str, Callable[[], Any]]]:
    """L3 兜底 — 按 input type 扫描（当所有 hint 都不匹配时）。

    适用于：登录页字段名千奇百怪（Email/Account/Mail/User Name），
    但 HTML 结构是标准的 <input type="text"> / <input type="password">。
    """
    attempts: list[tuple[str, Callable[[], Any]]] = []
    tag = (hints.label or hints.placeholder or hints.text or "").lower()

    if action == "fill":
        # 判断是用户名还是密码字段
        is_password = any(kw in tag for kw in ("password", "pwd", "密码", "passwort"))
        is_username = any(kw in tag for kw in ("user", "name", "用户名", "email", "mail", "account", "账号"))

        if is_password or "password" in tag:
            attempts.append(("l3_input_type", lambda: root.locator("input[type='password']").first))
        elif is_username or "user" in tag:
            attempts.append(("l3_input_type", lambda: root.locator("input[type='text']").first))
        else:
            # 不确定类型，两个都试
            attempts.append(("l3_input_type", lambda: root.locator("input[type='text']").first))
            attempts.append(("l3_input_type", lambda: root.locator("input[type='password']").first))

    return attempts


def _build_l2_attempts(page: Any, hints: LocatorHints) -> list[tuple[str, Callable[[], Any]]]:
    """L2 DOM 推断 — id/name/class/placeholder 模糊匹配。"""
    attempts: list[tuple[str, Callable[[], Any]]] = []
    seen: set[str] = set()
    seeds = [hints.text, hints.name, hints.label, hints.placeholder, hints.element_id]
    for raw in seeds:
        token = (raw or "").strip().lstrip("#.")
        if not token or len(token) < 2 or token in seen:
            continue
        seen.add(token)

        def _attr_match(t: str = token) -> Any:
            return page.locator(
                f"[id*='{t}'], [name*='{t}'], [placeholder*='{t}'], [aria-label*='{t}']"
            )

        def _text_match(t: str = token) -> Any:
            return page.locator(f"button:has-text('{t}'), a:has-text('{t}')")

        attempts.append(("l2_dom", _attr_match))
        attempts.append(("l2_dom", _text_match))
    return attempts


def resolve_locator(
    root: Any,
    hints: LocatorHints,
    *,
    action: str = "click",
    primary_css: str = "",
    timeout_ms: int | None = None,
) -> tuple[Any, HealResult]:
    """
    按 L1（七种）→ L2（DOM 推断）顺序解析 Locator。

    root: 可以是 Page 或 scoped Locator（如 dialog.get_by_role('dialog').first）
    primary_css: 脚本里写死的原始选择器，作为 L1 第一条（若提供）。
    timeout_ms: 单次尝试超时，默认从环境变量读取。
    """
    _ = action
    start = time.perf_counter()
    meta = HealResult()
    timeout = timeout_ms or _timeout_ms()

    chain: list[tuple[str, Callable[[], Any], str]] = []

    if primary_css:
        sel = primary_css
        chain.append(("css", lambda: root.locator(sel), "L1"))

    for strat, factory in _build_l1_attempts(root, hints):
        chain.append((strat, factory, "L1"))

    if _heal_enabled():
        for strat, factory in _build_l2_attempts(root, hints):
            chain.append((strat, factory, "L2"))

        # L3 兜底：按 input type 扫描
        for strat, factory in _build_l3_attempts(root, hints, action=action):
            chain.append((strat, factory, "L3"))

    if not chain and not _heal_enabled():
        raise ValueError("LocatorHints 为空且未提供 primary_css")

    first_strat = chain[0][0] if chain else ""
    for strat, factory, level in chain:
        loc, att = _try_locator(root, factory, strat, timeout)
        meta.attempts.append({**att, "level": level})
        if loc is not None:
            meta.strategy = strat
            meta.level = level
            meta.healed = strat != first_strat or level != "L1"
            meta.elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
            return loc, meta

    meta.elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
    raise RuntimeError(
        f"定位失败（已试 {len(meta.attempts)} 次）: {meta.attempts[-3:] if len(meta.attempts) >= 3 else meta.attempts}"
    )


def click_with_heal(root: Any, hints: LocatorHints, *, primary_css: str = "", timeout_ms: int | None = None) -> HealResult:
    loc, meta = resolve_locator(root, hints, action="click", primary_css=primary_css, timeout_ms=timeout_ms)
    loc.click()
    return meta


def fill_with_heal(root: Any, hints: LocatorHints, value: str, *, primary_css: str = "", timeout_ms: int | None = None) -> HealResult:
    loc, meta = resolve_locator(root, hints, action="fill", primary_css=primary_css, timeout_ms=timeout_ms)
    loc.fill(value)
    return meta


def select_with_heal(
    root: Any,
    hints: LocatorHints,
    value: str,
    *,
    primary_css: str = "",
    timeout_ms: int | None = None,
) -> HealResult:
    loc, meta = resolve_locator(root, hints, action="select", primary_css=primary_css, timeout_ms=timeout_ms)
    loc.select_option(value)
    return meta


if __name__ == "__main__":
    print("locator_healer — Web 七种策略 + L2 DOM 推断 + L3 input type 兜底")
    print("策略顺序: testid → role → label → placeholder → id → text → css → l2_dom → l3_input_type")
    print("用法见 UI-skills/执行/references/locator_strategy_web.md")
