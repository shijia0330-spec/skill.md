"""
Appium 定位自愈 — 原生 + WebView（Chrome/H5）+ iOS。

策略顺序:
  L0 registry 缓存 → L1 primary/确定性降级 → L2 token 模糊 → WebView context 切换
  → 权限弹窗 dismiss → L3 page_source 重推断

环境变量:
  MOBILE_SELF_HEAL=1|0           默认 1
  MOBILE_HEAL_TIMEOUT_MS=800     单次尝试超时（毫秒）
  MOBILE_WAIT_MODE=presence      默认等待模式：presence|visible|clickable
  MOBILE_SELECTOR_REGISTRY_PATH  注册表路径（默认 output/mobile_selector_registry.json）
  MOBILE_REGISTRY_WRITE=1        自愈成功后回写注册表
"""

from __future__ import annotations

import os
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any

try:
    from appium.webdriver.common.appiumby import AppiumBy
except ImportError:  # pragma: no cover — 单元测试可 mock driver
    AppiumBy = None  # type: ignore[misc, assignment]

from .selector_registry import record_healed_locator, resolve_l0_attempt


def _heal_enabled() -> bool:
    return os.environ.get("MOBILE_SELF_HEAL", "1").strip().lower() not in ("0", "false", "no", "off")


def _timeout_ms() -> int:
    raw = os.environ.get("MOBILE_HEAL_TIMEOUT_MS", "800").strip()
    try:
        return max(200, int(raw))
    except ValueError:
        return 800


def _default_wait_mode() -> str:
    return os.environ.get("MOBILE_WAIT_MODE", "presence").strip().lower() or "presence"


def _norm_by(name: str) -> str:
    key = (name or "").strip().lower().replace(" ", "_").replace("-", "_")
    if key in ("content_desc", "contentdesc"):
        return "accessibility_id"
    if key in ("css_selector",):
        return "css"
    return key


def _norm_wait_mode(mode: str | None) -> str:
    m = (mode or _default_wait_mode()).strip().lower()
    if m in ("clickable", "click", "enabled"):
        return "clickable"
    if m in ("visible", "displayed", "visibility"):
        return "visible"
    return "presence"


@dataclass
class MobileLocatorHints:
    accessibility_id: str = ""
    resource_id: str = ""
    text: str = ""
    content_desc: str = ""
    label: str = ""
    name: str = ""
    android_uiautomator: str = ""
    ios_predicate: str = ""
    ios_class_chain: str = ""
    xpath: str = ""
    css: str = ""
    class_name: str = ""


@dataclass
class HealResult:
    healed: bool = False
    strategy: str = ""
    level: str = "L1"
    attempts: list[dict[str, Any]] = field(default_factory=list)
    elapsed_ms: float = 0.0
    context: str = ""


def hints_from_primary(by_name: str, locator: str) -> MobileLocatorHints:
    """从 spec 主定位器推断 hint 链。"""
    hints = MobileLocatorHints()
    by = _norm_by(by_name)
    loc = (locator or "").strip()
    if not loc:
        return hints

    if by == "accessibility_id":
        hints.accessibility_id = loc
        hints.content_desc = loc
        hints.label = loc
        hints.name = loc
    elif by == "id":
        hints.resource_id = loc
    elif by == "name":
        hints.name = loc
        hints.accessibility_id = loc
    elif by == "css":
        hints.css = loc
        m = re.search(r'name=["\']([^"\']+)["\']', loc)
        if m:
            hints.text = m.group(1)
        m = re.search(r'placeholder=["\']([^"\']+)["\']', loc)
        if m:
            hints.text = hints.text or m.group(1)
        m = re.search(r'#([\w-]+)', loc)
        if m:
            hints.resource_id = m.group(1)
    elif by == "xpath":
        hints.xpath = loc
        m = re.search(r"@text=['\"]([^'\"]+)['\"]", loc)
        if m:
            hints.text = m.group(1)
        m = re.search(r"@content-desc=['\"]([^'\"]+)['\"]", loc)
        if m:
            hints.content_desc = m.group(1)
        m = re.search(r"@label=['\"]([^'\"]+)['\"]", loc)
        if m:
            hints.label = m.group(1)
        m = re.search(r"@name=['\"]([^'\"]+)['\"]", loc)
        if m:
            hints.name = m.group(1)
    elif by == "android_uiautomator":
        hints.android_uiautomator = loc
        m = re.search(r'\.text(?:Contains)?\(["\']([^"\']+)["\']\)', loc)
        if m:
            hints.text = m.group(1)
    elif by == "ios_predicate":
        hints.ios_predicate = loc
        m = re.search(r'label\s*(?:CONTAINS|==)\s*["\']([^"\']+)["\']', loc, re.I)
        if m:
            hints.label = m.group(1)
            hints.text = hints.text or m.group(1)
        m = re.search(r'name\s*(?:CONTAINS|==)\s*["\']([^"\']+)["\']', loc, re.I)
        if m:
            hints.name = m.group(1)
    elif by == "ios_class_chain":
        hints.ios_class_chain = loc
        m = re.search(r'label\s*==\s*["\']([^"\']+)["\']', loc)
        if m:
            hints.label = m.group(1)
    elif by == "class_name":
        hints.class_name = loc

    return hints


def _by_map() -> dict[str, Any]:
    if AppiumBy is None:
        raise ImportError("需要 Appium-Python-Client")
    return {
        "accessibility_id": AppiumBy.ACCESSIBILITY_ID,
        "id": AppiumBy.ID,
        "xpath": AppiumBy.XPATH,
        "class_name": AppiumBy.CLASS_NAME,
        "name": AppiumBy.NAME,
        "android_uiautomator": AppiumBy.ANDROID_UIAUTOMATOR,
        "ios_predicate": AppiumBy.IOS_PREDICATE,
        "ios_class_chain": AppiumBy.IOS_CLASS_CHAIN,
        "css": AppiumBy.CSS_SELECTOR,
    }


def _ios_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')[:60]


def _build_l1_attempts(
    by_name: str,
    locator: str,
    hints: MobileLocatorHints,
) -> list[tuple[str, str, str]]:
    """返回 (strategy, by_key, locator_value)。"""
    attempts: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add(strat: str, by_key: str, loc: str) -> None:
        loc = (loc or "").strip()
        if not loc:
            return
        key = (by_key, loc)
        if key in seen:
            return
        seen.add(key)
        attempts.append((strat, by_key, loc))

    add("primary", _norm_by(by_name), locator)

    if hints.accessibility_id:
        add("accessibility_id", "accessibility_id", hints.accessibility_id)
    if hints.content_desc and hints.content_desc != hints.accessibility_id:
        add("content_desc", "accessibility_id", hints.content_desc)
    if hints.name and hints.name != hints.accessibility_id:
        add("ios_name", "name", hints.name)
    if hints.resource_id:
        add("resource_id", "id", hints.resource_id)
    if hints.text:
        safe = hints.text.replace('"', '\\"')[:60]
        add("uia_text", "android_uiautomator", f'new UiSelector().textContains("{safe}")')
        add("xpath_text", "xpath", f'//*[contains(@text, "{safe}")]')
        add("xpath_desc", "xpath", f'//*[contains(@content-desc, "{safe}")]')
        ios_safe = _ios_escape(hints.text)
        add(
            "ios_predicate_text",
            "ios_predicate",
            f'label CONTAINS "{ios_safe}" OR name CONTAINS "{ios_safe}" OR value CONTAINS "{ios_safe}"',
        )
        add("ios_class_chain_text", "ios_class_chain", f'**/*[`label == "{ios_safe}"`]')
    if hints.label and hints.label != hints.text:
        ios_label = _ios_escape(hints.label)
        add("ios_predicate_label", "ios_predicate", f'label CONTAINS "{ios_label}"')
        add("ios_class_chain_label", "ios_class_chain", f'**/*[`label == "{ios_label}"`]')
    if hints.android_uiautomator:
        add("uia_custom", "android_uiautomator", hints.android_uiautomator)
    if hints.ios_predicate and hints.ios_predicate != locator:
        add("ios_predicate_custom", "ios_predicate", hints.ios_predicate)
    if hints.ios_class_chain and hints.ios_class_chain != locator:
        add("ios_class_chain_custom", "ios_class_chain", hints.ios_class_chain)
    if hints.xpath and hints.xpath != locator:
        add("xpath", "xpath", hints.xpath)
    if hints.css and hints.css != locator:
        add("css", "css", hints.css)
    if hints.class_name:
        add("class_name", "class_name", hints.class_name)

    return attempts


def _tokens_for_l2(hints: MobileLocatorHints, primary_loc: str) -> list[str]:
    seeds = [
        hints.text,
        hints.content_desc,
        hints.accessibility_id,
        hints.label,
        hints.name,
        hints.resource_id,
        primary_loc,
    ]
    out: list[str] = []
    seen: set[str] = set()
    for raw in seeds:
        for token in re.split(r"[^\w\u4e00-\u9fff]+", raw or ""):
            t = token.strip().lower()
            if len(t) < 2 or t in seen:
                continue
            seen.add(t)
            out.append(token.strip())
    return out[:6]


def _build_l2_attempts(hints: MobileLocatorHints, primary_loc: str) -> list[tuple[str, str, str]]:
    attempts: list[tuple[str, str, str]] = []
    for token in _tokens_for_l2(hints, primary_loc):
        safe = token.replace('"', '\\"')[:40]
        ios_safe = _ios_escape(token)
        attempts.append(("l2_attr", "xpath", f'//*[contains(@name,"{safe}") or contains(@placeholder,"{safe}")]'))
        attempts.append(
            ("l2_native",
             "xpath",
             f'//*[contains(@text,"{safe}") or contains(@content-desc,"{safe}") or contains(@label,"{safe}")]',
             )
        )
        attempts.append(
            ("l2_ios_predicate",
             "ios_predicate",
             f'label CONTAINS "{ios_safe}" OR name CONTAINS "{ios_safe}" OR value CONTAINS "{ios_safe}"',
             )
        )
    return attempts


def _needs_webview(by_key: str) -> bool:
    return by_key in ("css", "xpath") and _norm_by(by_key) in ("css", "xpath")


def _current_context(driver: Any) -> str:
    try:
        return str(getattr(driver, "current_context", "") or "")
    except Exception:  # noqa: BLE001
        return ""


def _list_contexts(driver: Any) -> list[str]:
    try:
        return list(getattr(driver, "contexts", []) or [])
    except Exception:  # noqa: BLE001
        return []


def _switch_context(driver: Any, ctx: str) -> None:
    driver.switch_to.context(ctx)


def _contexts_for_heal(driver: Any, by_key: str) -> list[str]:
    contexts = _list_contexts(driver)
    if len(contexts) <= 1:
        return [contexts[0] if contexts else "NATIVE_APP"]
    current = _current_context(driver)
    ordered: list[str] = []
    if _needs_webview(by_key):
        for ctx in contexts:
            if "WEBVIEW" in ctx.upper():
                ordered.append(ctx)
        for ctx in contexts:
            if ctx not in ordered:
                ordered.append(ctx)
    else:
        if current:
            ordered.append(current)
        for ctx in contexts:
            if ctx not in ordered:
                ordered.append(ctx)
    return ordered or ["NATIVE_APP"]


def _try_dismiss_permission_popup(driver: Any) -> bool:
    """尝试点掉 Android 权限弹窗，成功返回 True。"""
    if AppiumBy is None:
        return False
    allow_ids = (
        "com.android.permissioncontroller:id/permission_allow_button",
        "com.android.packageinstaller:id/permission_allow_button",
    )
    for rid in allow_ids:
        try:
            driver.find_element(AppiumBy.ID, rid).click()
            return True
        except Exception:  # noqa: BLE001
            continue
    try:
        driver.find_element(
            AppiumBy.ANDROID_UIAUTOMATOR,
            'new UiSelector().textContains("允许")',
        ).click()
        return True
    except Exception:  # noqa: BLE001
        pass
    try:
        driver.find_element(
            AppiumBy.ANDROID_UIAUTOMATOR,
            'new UiSelector().textContains("Allow")',
        ).click()
        return True
    except Exception:  # noqa: BLE001
        pass
    return False


def _try_find(
    driver: Any,
    by_key: str,
    loc: str,
    timeout_ms: int,
    *,
    wait_mode: str = "presence",
) -> tuple[Any | None, dict[str, Any]]:
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    mapping = _by_map()
    if by_key not in mapping:
        return None, {"strategy": by_key, "ok": False, "error": f"unknown by {by_key}"}
    wm = _norm_wait_mode(wait_mode)
    if wm == "clickable":
        cond = EC.element_to_be_clickable((mapping[by_key], loc))
    elif wm == "visible":
        cond = EC.visibility_of_element_located((mapping[by_key], loc))
    else:
        cond = EC.presence_of_element_located((mapping[by_key], loc))
    t0 = time.perf_counter()
    try:
        el = WebDriverWait(driver, timeout_ms / 1000.0).until(cond)
        ms = (time.perf_counter() - t0) * 1000
        return el, {"by": by_key, "locator": loc[:80], "ok": True, "ms": round(ms, 1), "wait": wm}
    except Exception as exc:  # noqa: BLE001
        ms = (time.perf_counter() - t0) * 1000
        return None, {
            "by": by_key,
            "locator": loc[:80],
            "ok": False,
            "ms": round(ms, 1),
            "wait": wm,
            "error": str(exc)[:120],
        }


def _detect_platform(xml_text: str) -> str:
    low = (xml_text or "")[:4000].lower()
    if "xcuielement" in low or 'type="xcui' in low:
        return "ios"
    if "android.widget" in low or "resource-id" in low:
        return "android"
    return "unknown"


def suggest_from_page_source(xml_text: str, *, text_hint: str = "") -> list[tuple[str, str]]:
    """离线：从 page_source XML 推断候选 (by_key, locator)。"""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    platform = _detect_platform(xml_text)
    out: list[tuple[str, str]] = []
    hint = (text_hint or "").strip().lower()
    for el in root.iter():
        desc = (el.get("content-desc") or el.get("contentDescription") or "").strip()
        rid = (el.get("resource-id") or el.get("resourceId") or "").strip()
        text = (el.get("text") or "").strip()
        label = (el.get("label") or "").strip()
        name = (el.get("name") or "").strip()
        value = (el.get("value") or "").strip()
        blob = (desc + text + rid + label + name + value).lower()
        if hint and hint not in blob:
            continue
        if desc:
            out.append(("accessibility_id", desc))
        if rid:
            out.append(("id", rid))
        if platform == "ios":
            if label:
                out.append(("ios_predicate", f'label == "{_ios_escape(label)}"'))
                out.append(("accessibility_id", label))
            if name and name != label:
                out.append(("name", name))
                out.append(("ios_predicate", f'name == "{_ios_escape(name)}"'))
            if value:
                out.append(("ios_predicate", f'value CONTAINS "{_ios_escape(value)}"'))
        if text:
            safe = text.replace('"', '\\"')[:40]
            out.append(("android_uiautomator", f'new UiSelector().textContains("{safe}")'))
            if platform != "ios":
                out.append(("xpath", f'//*[contains(@text, "{safe}")]'))
    return out[:16]


def _maybe_record_registry(
    registry_key: str | None,
    meta: HealResult,
    primary_by: str,
    primary_locator: str,
) -> None:
    if not registry_key or not meta.healed:
        return
    success = next((a for a in reversed(meta.attempts) if a.get("ok")), None)
    if not success:
        return
    by_key = str(success.get("by") or "")
    loc = str(success.get("locator") or "")
    if not by_key or not loc:
        return
    record_healed_locator(
        registry_key,
        by=by_key,
        locator=loc,
        strategy=meta.strategy,
        level=meta.level,
        primary_by=primary_by,
        primary_locator=primary_locator,
    )


def _run_chain(
    driver: Any,
    chain: list[tuple[str, str, str, str]],
    *,
    per_try_ms: int,
    wait_mode: str,
    meta: HealResult,
    first_strat: str,
    restore_context: str,
) -> Any | None:
    for strat, by_key, loc, level in chain:
        for ctx in _contexts_for_heal(driver, by_key):
            try:
                if ctx and ctx != _current_context(driver):
                    _switch_context(driver, ctx)
                    meta.context = ctx
            except Exception as exc:  # noqa: BLE001
                meta.attempts.append({"strategy": strat, "level": level, "context": ctx, "ok": False, "error": str(exc)[:80]})
                continue
            el, att = _try_find(driver, by_key, loc, per_try_ms, wait_mode=wait_mode)
            meta.attempts.append({**att, "strategy": strat, "level": level, "context": ctx})
            if el is not None:
                meta.strategy = strat
                meta.level = level
                meta.healed = strat != first_strat or level not in ("L1", "L0")
                return el
    if restore_context:
        try:
            if restore_context != _current_context(driver):
                _switch_context(driver, restore_context)
        except Exception:  # noqa: BLE001
            pass
    return None


def find_with_heal(
    driver: Any,
    by_name: str,
    locator: str,
    *,
    hints: MobileLocatorHints | None = None,
    timeout_sec: float | None = None,
    wait_mode: str | None = None,
    registry_key: str | None = None,
) -> Any:
    """L0→L1→L2→context→permission→L3 查找元素；失败抛 RuntimeError。"""
    start = time.perf_counter()
    meta = HealResult()
    wm = _norm_wait_mode(wait_mode)
    per_try_ms = _timeout_ms()
    if timeout_sec is not None:
        per_try_ms = min(per_try_ms, max(200, int(float(timeout_sec) * 1000)))

    h = hints or hints_from_primary(by_name, locator)
    restore_context = _current_context(driver) or "NATIVE_APP"
    chain: list[tuple[str, str, str, str]] = []

    if registry_key:
        l0 = resolve_l0_attempt(registry_key)
        if l0:
            by0, loc0 = l0
            chain.append(("registry_l0", _norm_by(by0), loc0, "L0"))

    for strat, by_key, loc in _build_l1_attempts(by_name, locator, h):
        chain.append((strat, by_key, loc, "L1"))
    if _heal_enabled():
        for strat, by_key, loc in _build_l2_attempts(h, locator):
            chain.append((strat, by_key, loc, "L2"))

    first_strat = chain[0][0] if chain else ""
    el = _run_chain(driver, chain, per_try_ms=per_try_ms, wait_mode=wm, meta=meta, first_strat=first_strat, restore_context="")
    if el is not None:
        meta.elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
        _maybe_record_registry(registry_key, meta, by_name, locator)
        return el

    if _heal_enabled() and _try_dismiss_permission_popup(driver):
        meta.attempts.append({"strategy": "permission_dismiss", "ok": True, "level": "L2.5"})
        el = _run_chain(
            driver,
            chain,
            per_try_ms=per_try_ms,
            wait_mode=wm,
            meta=meta,
            first_strat=first_strat,
            restore_context="",
        )
        if el is not None:
            meta.elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
            _maybe_record_registry(registry_key, meta, by_name, locator)
            return el

    if _heal_enabled():
        try:
            xml_text = driver.page_source or ""
            l3_chain: list[tuple[str, str, str, str]] = []
            for by_key, loc in suggest_from_page_source(xml_text, text_hint=h.text or h.content_desc or h.label):
                l3_chain.append(("l3_page_source", by_key, loc, "L3"))
            el = _run_chain(
                driver,
                l3_chain,
                per_try_ms=per_try_ms,
                wait_mode=wm,
                meta=meta,
                first_strat="l3_page_source",
                restore_context=restore_context,
            )
            if el is not None:
                meta.healed = True
                meta.strategy = "l3_page_source"
                meta.level = "L3"
                meta.elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
                _maybe_record_registry(registry_key, meta, by_name, locator)
                return el
        except Exception as exc:  # noqa: BLE001
            meta.attempts.append({"strategy": "l3_page_source", "ok": False, "error": str(exc)[:120]})

    try:
        if restore_context and restore_context != _current_context(driver):
            _switch_context(driver, restore_context)
    except Exception:  # noqa: BLE001
        pass

    meta.elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
    raise RuntimeError(
        f"定位失败（已试 {len(meta.attempts)} 次，heal={'on' if _heal_enabled() else 'off'}）: "
        f"{meta.attempts[-3:] if len(meta.attempts) >= 3 else meta.attempts}"
    )


def click_with_heal(
    driver: Any,
    by_name: str,
    locator: str,
    *,
    timeout_sec: float | None = None,
    registry_key: str | None = None,
) -> None:
    """clickable 等待 + stale 元素自动重查。"""
    from selenium.common.exceptions import StaleElementReferenceException

    el = find_with_heal(
        driver,
        by_name,
        locator,
        timeout_sec=timeout_sec,
        wait_mode="clickable",
        registry_key=registry_key,
    )
    try:
        el.click()
    except StaleElementReferenceException:
        find_with_heal(
            driver,
            by_name,
            locator,
            timeout_sec=timeout_sec,
            wait_mode="clickable",
            registry_key=registry_key,
        ).click()


if __name__ == "__main__":
    print("mobile_lib.locator_healer — Appium L0/L1/L2/L3 定位自愈")
    print("环境: MOBILE_SELF_HEAL=1, MOBILE_HEAL_TIMEOUT_MS=800, MOBILE_SELECTOR_REGISTRY_PATH=...")
