#!/usr/bin/env python3
"""
Markdown 功能用例候选（md_ui_filter 产出）→ ui_automation JSON。

用法:
  python codegen/md_to_ui_automation.py \\
      -i output/_pipeline/seckill_ui_candidates.json \\
      -o output/_pipeline/seckill_ui_automation.json \\
      --base-url http://your-server:5001

  python codegen/md_cases_to_ui_spec.py -i examples/output_seckill_auth_testcases.md \\
      -o templates/seckill_ui_from_cases.md
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

CLICK_QUOTED = re.compile(r"[点点击][「『\"\"]([^」』\"\"]+)[」』\"\"]")
TIMESTAMP_TOKEN = re.compile(r"\{timestamp\}", re.I)

# 秒杀 Web 表单字段 → 环境变量（与 templates/ui_login.md 对齐）
SECKILL_FIELD_ENV: dict[str, str] = {
    "用户名": "TEST_USERNAME",
    "密码": "TEST_PASSWORD",
    "邮箱": "TEST_EMAIL",
    "商品名称": "SECKILL_PRODUCT_NAME",
}

# 铺底 / seed 固定字面量 → 环境变量
SEED_LITERAL_ENV: dict[str, str] = {
    "skills-seed-product-a": "SECKILL_SEARCH_NAME",
    "skills-seed-dup-user": "SECKILL_DUPLICATE_USERNAME",
}

ENV_LITERAL_VALUES: dict[str, str] = {
    "秒杀演示商品": "SECKILL_PRODUCT_NAME",
    "wrong-password": "TEST_WRONG_PASSWORD",
}

RADIO_FIELD_HINTS = ("角色", "状态", "类型", "方式")

# Ant Design 等 SPA 常用 placeholder 而非 <label>
_PLACEHOLDER_FIELDS = frozenset({"用户名", "密码", "邮箱", "确认密码"})


def _fill_step(label: str, value: str) -> dict[str, Any]:
    step: dict[str, Any] = {"action": "fill", "value": value}
    if label in _PLACEHOLDER_FIELDS:
        step["l1_placeholder"] = label
    else:
        step["l1_label"] = label
    return step


def _slug(name: str) -> str:
    s = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "-", name.strip())[:48].strip("-")
    return s or "flow"


_PUBLIC_PATHS = frozenset({"/", "/login", "/register"})


def _is_protected_route(path: str) -> bool:
    """需登录态的 SPA 路由（非 /login /register 等公开页）。"""
    p = (path or "").rstrip("/") or "/"
    if p in _PUBLIC_PATHS or p.endswith("/login") or p.endswith("/register"):
        return False
    return True


def _has_storage_state_file() -> bool:
    import os
    from pathlib import Path

    raw = os.environ.get("UI_STORAGE_STATE", "output/.auth/ui_storage.json")
    p = Path(raw)
    if p.is_file():
        return True
    root = Path(__file__).resolve().parents[1]
    return (root / raw).is_file()


def _nav_step(page_path: str) -> dict[str, Any]:
    """有 storage_state 时仅 goto（复用 cookie），否则走 ensure_logged_in。"""
    if _is_protected_route(page_path) and _has_storage_state_file():
        return {
            "action": "goto",
            "path": page_path,
            "wait_until": "domcontentloaded",
            "timeout_ms": 30000,
        }
    if _is_protected_route(page_path):
        return {
            "action": "ensure_logged_in",
            "path": page_path,
            "wait_until": "networkidle",
            "timeout_ms": 60000,
        }
    return {"action": "goto", "path": page_path, "wait_until": "networkidle"}


def _env_for_field(label: str, page_path: str, raw_value: str) -> str:
    val = raw_value.strip()
    if val in SEED_LITERAL_ENV:
        return f"__ENV__:{SEED_LITERAL_ENV[val]}"
    if val in ENV_LITERAL_VALUES:
        return f"__ENV__:{ENV_LITERAL_VALUES[val]}"
    if TIMESTAMP_TOKEN.search(raw_value):
        if re.search(r"skills-demo-\{timestamp\}", val):
            return "__ENV__:TEST_UNIQUE_ID|-off"
        if label in SECKILL_FIELD_ENV:
            return f"__ENV__:{SECKILL_FIELD_ENV[label]}"
        return "__ENV__:TEST_UNIQUE_ID"
    return raw_value


def _infer_dialog_title(steps: list[dict[str, Any]], blob: str) -> str | None:
    for s in steps:
        if s.get("action") == "click":
            name = s.get("l1_name") or s.get("l1_name_regex") or ""
            m = re.match(r"新增(.+)", str(name))
            if m:
                return f"新增{m.group(1).strip()}"
    m = re.search(r"新增([^」」\s]+)", blob)
    if m:
        return f"新增{m.group(1).strip()}"
    return None


def _apply_dialog_scope(steps: list[dict[str, Any]], dialog_title: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    in_dialog = False
    for s in steps:
        btn_text = str(s.get("l1_name") or s.get("l1_name_regex") or "")
        if s.get("action") == "click" and "新增" in btn_text:
            out.append(s)
            in_dialog = True
            continue
        if not in_dialog:
            out.append(s)
            continue
        if s.get("action") == "click" and s.get("l1_name") in ("确认", "确定", "提交", "取消"):
            ns = dict(s)
            ns.setdefault("scope", "dialog")
            ns.setdefault("dialog_title", dialog_title)
            ns.setdefault("timeout_ms", 15000)
            out.append(ns)
            in_dialog = False
            continue
        ns = dict(s)
        if ns.get("action") in ("fill", "click", "click_radio", "select_option"):
            ns.setdefault("scope", "dialog")
            ns.setdefault("dialog_title", dialog_title)
            ns.setdefault("timeout_ms", 15000)
        out.append(ns)
    return out


def _prepend_page_entry(steps: list[dict[str, Any]], page_path: str) -> list[dict[str, Any]]:
    if not page_path:
        return steps
    if any(s.get("action") in ("ensure_logged_in", "goto") for s in steps[:2]):
        return steps
    if _is_protected_route(page_path):
        return [_nav_step(page_path), *steps]
    return [{"action": "goto", "path": page_path, "wait_until": "networkidle"}, *steps]


def _parse_step_line(line: str, *, page_path: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    steps: list[dict[str, Any]] = []
    expects: list[dict[str, Any]] = []
    c = line.strip().lstrip("-").strip()

    m = re.search(r"导航至\s+[`']?([/\w\-_.]+)[`']?", c)
    if m:
        path = m.group(1)
        if _is_protected_route(path):
            steps.append(_nav_step(path))
        else:
            steps.append({"action": "goto", "path": path, "wait_until": "networkidle"})
        return steps, expects

    m = re.match(r"(.+?)留空.*点击[「『\"\"](.+?)[」』\"\"]", c)
    if m:
        label = m.group(1).strip()
        btn = m.group(2).strip()
        steps.append(_fill_step(label, ""))
        click_step: dict[str, Any] = {"action": "click", "l1_role": "button", "l1_name": btn}
        if btn in ("登录", "登 录"):
            click_step = {"action": "click", "l1_role": "button", "l1_name_regex": r"登\s*录"}
        elif btn == "注册":
            click_step = {"action": "click", "l1_role": "button", "l1_name_regex": r"注\s*册"}
        steps.append(click_step)
        return steps, expects

    m = CLICK_QUOTED.search(c)
    if m:
        btn = m.group(1).strip()
        if btn in ("确认", "确定", "提交", "保存"):
            steps.append({"action": "click", "l1_role": "button", "l1_name": btn})
        else:
            step: dict[str, Any] = {"action": "click", "l1_role": "button", "l1_name": btn}
            if "新增" in btn:
                step["l1_name_regex"] = btn
                step.pop("l1_name", None)
            elif btn in ("登录", "登 录"):
                step["l1_name_regex"] = r"登\s*录"
                step.pop("l1_name", None)
            elif btn == "注册":
                step["l1_name_regex"] = r"注\s*册"
                step.pop("l1_name", None)
            steps.append(step)
        return steps, expects

    m = re.match(r"(?:填写|填入|输入)\s*(.+?)\s*(?:为|是|：|:)\s*(.+)", c)
    if m:
        label, val = m.group(1).strip(), m.group(2).strip()
        value = _env_for_field(label, page_path, val)
        steps.append(_fill_step(label, value))
        return steps, expects

    m = re.match(r"(.+?)(?:选择|选)\s*(.+)", c)
    if m:
        field_hint, val = m.group(1).strip(), m.group(2).strip()
        if any(h in field_hint for h in RADIO_FIELD_HINTS) or field_hint in ("角色", "状态"):
            steps.append({"action": "click_radio", "value": val})
        else:
            steps.append({"action": "click", "l1_role": "button", "l1_name": val})
        return steps, expects

    if re.search(r"列表中出现|列表可见|表格.*出现", c):
        m2 = re.search(r"列表中出现\s+(.+)", c)
        text = m2.group(1).strip() if m2 else ""
        if text in SEED_LITERAL_ENV:
            expects.append(
                {"type": "visible_text", "text": f"__ENV__:{SEED_LITERAL_ENV[text]}", "exact": False}
            )
        elif text in ENV_LITERAL_VALUES:
            expects.append(
                {"type": "visible_text", "text": f"__ENV__:{ENV_LITERAL_VALUES[text]}", "exact": False}
            )
        elif text:
            expects.append({"type": "visible_text", "text": text, "exact": False})
        return steps, expects

    if re.search(r"必填校验|不能为空|错误提示|出现必填|密码错误|用户名或密码", c):
        if re.search(r"用户名或密码|密码错误", c):
            expects.append({"type": "visible_text", "text": "还没有账号", "exact": False})
        else:
            expects.append({"type": "alert_visible", "text": "请输入", "exact": False})
        return steps, expects

    if re.search(r"用户名已存在|用户名重复|用户已存在", c):
        expects.append({"type": "visible_text", "text": "用户名已存在", "exact": False})
        return steps, expects

    if re.search(r"可见[「「](.+?)[」」]", c):
        text = re.search(r"可见[「「](.+?)[」」]", c).group(1).strip()  # type: ignore[union-attr]
        expects.append({"type": "role_visible", "l1_role": "button", "l1_name": text})
        return steps, expects

    if "已登录" in c and not steps:
        return steps, expects

    return steps, expects


def convert_candidate(
    candidate: dict[str, Any],
    *,
    skip_tags: set[str],
    allowed_tiers: frozenset[str] = frozenset({"A", "B"}),
) -> dict[str, Any] | None:
    tier = candidate.get("tier") or "exclude"
    if tier not in allowed_tiers:
        return None
    tags = set(candidate.get("tags") or [])
    if tags & skip_tags:
        return None
    if "page_unavailable" in tags:
        return None

    page_path = str(candidate.get("page_path") or "/")
    step_lines = candidate.get("steps") or []
    if not step_lines:
        return None

    all_steps: list[dict[str, Any]] = []
    all_expects: list[dict[str, Any]] = []
    blob = f"{candidate.get('title', '')} " + " ".join(step_lines)

    for line in step_lines:
        if "已登录" in line and not re.search(r"导航至|进入", line):
            continue
        st, ex = _parse_step_line(line, page_path=page_path)
        all_steps.extend(st)
        all_expects.extend(ex)

    if not all_steps:
        return None

    all_steps = _prepend_page_entry(all_steps, page_path)

    template_hint = candidate.get("template_hint") or "generic"
    if template_hint == "dialog_crud" or "弹窗" in blob or "新增" in blob:
        dialog_title = _infer_dialog_title(all_steps, blob)
        if dialog_title:
            all_steps = _apply_dialog_scope(all_steps, dialog_title)
            if not any(s.get("action") == "wait_timeout_ms" for s in all_steps):
                idx = next(
                    (i for i, s in enumerate(all_steps) if s.get("l1_name") in ("确认", "确定", "提交")),
                    None,
                )
                if idx is not None:
                    all_steps.insert(idx + 1, {"action": "wait_timeout_ms", "ms": 2000})
                else:
                    all_steps.append({"action": "wait_timeout_ms", "ms": 800})
            if all_expects and any(e.get("type") == "alert_visible" for e in all_expects):
                for e in all_expects:
                    if e.get("type") != "alert_visible":
                        continue
                    if "用户名已存在" in str(e.get("text") or ""):
                        continue
                    e.setdefault("scope", "dialog")
                    e.setdefault("dialog_title", dialog_title)

    # 弹窗表单：若用例写了「状态」但未写单选步骤，补默认「启用」（商品管理等场景）
    if any("新增" in str(s.get("l1_name") or s.get("l1_name_regex") or "") for s in all_steps):
        has_status_radio = any(
            s.get("action") == "click_radio" and s.get("value") in ("启用", "开启", "关闭")
            for s in all_steps
        )
        if not has_status_radio and "状态" in blob:
            dialog_title = _infer_dialog_title(all_steps, blob) or "新增商品"
            all_steps.append(
                {
                    "action": "click_radio",
                    "scope": "dialog",
                    "dialog_title": dialog_title,
                    "value": "开启",
                    "timeout_ms": 15000,
                }
            )

    if template_hint == "list_filter_search":
        if not any(s.get("action") == "click" and s.get("l1_name") == "搜索" for s in all_steps):
            all_steps.append({"action": "click", "l1_role": "button", "l1_name": "搜索"})

    case_id = candidate.get("case_id") or _slug(str(candidate.get("title", "case")))
    flow_name = str(candidate.get("title") or case_id)

    ui_flow: dict[str, Any] = {
        "name": flow_name,
        "steps": all_steps,
    }
    if all_expects:
        ui_flow["expect"] = all_expects

    return {
        "id": case_id,
        "name": flow_name,
        "case_id": case_id,
        "source_tier": tier,
        "source_template_hint": template_hint,
        "ui_automation": ui_flow,
    }


def load_candidates(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    meta: dict[str, Any] = {}
    if isinstance(data, dict):
        meta = {k: data[k] for k in ("source", "inputs", "stats") if k in data}
        if isinstance(data.get("candidates"), list):
            return data["candidates"], meta
        if isinstance(data.get("cases"), list):
            return data["cases"], meta
    if isinstance(data, list):
        return data, meta
    raise ValueError("输入须为 md_ui_filter 产出 JSON（含 candidates）或候选数组")


def build_automation_payload(
    candidates: list[dict[str, Any]],
    *,
    base_url: str,
    storage_state: str | None,
    viewport: dict[str, int] | None,
    skip_tags: set[str],
    merge_by_page: bool,
    allowed_tiers: frozenset[str] | None = None,
) -> dict[str, Any]:
    tiers = allowed_tiers or frozenset({"A", "B"})
    cases: list[dict[str, Any]] = []
    for c in candidates:
        converted = convert_candidate(c, skip_tags=skip_tags, allowed_tiers=tiers)
        if converted:
            cases.append(converted)

    flow_names = [str(c.get("name") or c.get("case_id") or f"flow_{i+1}") for i, c in enumerate(cases)]
    payload: dict[str, Any] = {
        "base_url": base_url.rstrip("/"),
        "cases": cases,
        "setup": {
            "kind": "test_init",
            "path": "/api/test/init",
        },
        "batch": {
            "fail_fast": False,
            "login_once": True,
            "flows": flow_names,
        },
    }
    if storage_state:
        payload["storage_state"] = storage_state
    if viewport:
        payload["viewport"] = viewport
    if merge_by_page and cases:
        # 同页多条合并为一个 spec 的多个 flows（testcase_to_ui_spec 已支持）
        pass
    return payload


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-i", "--input", type=Path, required=True, help="md_ui_filter 产出的 JSON")
    ap.add_argument("-o", "--output", type=Path, required=True, help="ui_automation JSON 路径")
    ap.add_argument("--base-url", default="http://your-server:5001")
    ap.add_argument("--storage-state", default="output/.auth/ui_storage.json")
    ap.add_argument("--skip-tag", default="needs_role,page_unavailable,stale_action", help="逗号分隔，命中则跳过")
    ap.add_argument(
        "--tier",
        default="A,B",
        help="转化档位，逗号分隔；模块冒烟 8 条可用 A,B,C",
    )
    ap.add_argument("--strict", action="store_true", help="无可用条目时退出码 1")
    ns = ap.parse_args()

    inp = ns.input if ns.input.is_absolute() else (ROOT / ns.input).resolve()
    out = ns.output if ns.output.is_absolute() else (ROOT / ns.output).resolve()
    skip_tags = {t.strip() for t in ns.skip_tag.split(",") if t.strip()}

    candidates, _meta = load_candidates(inp)
    allowed_tiers = frozenset(t.strip().upper() for t in ns.tier.split(",") if t.strip()) or frozenset({"A", "B"})
    use_storage = bool(ns.storage_state) and _has_storage_state_file()
    payload = build_automation_payload(
        candidates,
        base_url=ns.base_url,
        storage_state=ns.storage_state if use_storage else None,
        viewport={"width": 1440, "height": 900},
        skip_tags=skip_tags,
        merge_by_page=True,
        allowed_tiers=allowed_tiers,
    )

    if not payload["cases"]:
        print(
            f"没有可转换的 {','.join(sorted(allowed_tiers))} 档候选（请检查 tier / tags / steps）",
            file=sys.stderr,
        )
        return 1 if ns.strict else 0

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已写入: {out} ({len(payload['cases'])} 条 ui_automation)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
