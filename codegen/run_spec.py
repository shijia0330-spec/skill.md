#!/usr/bin/env python3
"""声明式 Markdown（YAML Frontmatter）→ pytest（requests / pytest-playwright / Appium）。本地模板，无 LLM。"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import urllib.request
from pathlib import Path
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlparse

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore

_CODEGEN_DIR = Path(__file__).resolve().parent
if str(_CODEGEN_DIR) not in sys.path:
    sys.path.insert(0, str(_CODEGEN_DIR))


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """解析首份 YAML frontmatter（按行找第二道 ---，避免正则与 CRLF/EOF 边角问题）。"""
    if yaml is None:
        raise RuntimeError("请安装: pip install PyYAML")
    if text.startswith("\ufeff"):
        text = text[1:]
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    lines = text.split("\n")
    if len(lines) < 2 or lines[0].strip() != "---":
        raise ValueError("缺少 YAML Frontmatter（文件须以单独一行的 --- 起始）")

    close: int | None = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            close = i
            break
    if close is None:
        raise ValueError("缺少闭合的 ---（frontmatter 须用第二行 --- 结束后再写正文）")

    yaml_src = "\n".join(lines[1:close])
    if not yaml_src.strip():
        raise ValueError("Frontmatter 内容不能为空（两道 --- 之间须有 YAML）")

    try:
        meta = yaml.safe_load(yaml_src)  # type: ignore[misc]
    except Exception as e:  # noqa: BLE001
        raise ValueError(f"YAML 解析失败: {e}") from e

    body = "\n".join(lines[close + 1 :]).lstrip("\n")
    if not isinstance(meta, dict):
        raise ValueError("Frontmatter 须为 YAML 映射（根节点为对象，不是数组或纯字符串）")
    return meta, body


def esc(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def _inject_rag_context(code: str, rag_path: Path | None, *, out_suffix: str = ".py") -> str:
    """将 generate.sh 预检索的 RAG markdown 注入生成物头部注释（供调试与 AI 上下文对齐）。"""
    if rag_path is None or not rag_path.is_file():
        return code
    rag_text = rag_path.read_text(encoding="utf-8", errors="replace").strip()
    if not rag_text:
        return code
    lines = rag_text.splitlines()
    if len(lines) > 120:
        lines = lines[:120] + ["... (RAG truncated)"]
    if out_suffix == ".js":
        block = "\n".join(f"// {ln}" if ln.strip() else "//" for ln in lines)
        header = f"// --- RAG context ({rag_path.name}) ---\n{block}\n// --- end RAG ---\n\n"
    else:
        block = "\n".join(f"# {ln}" if ln.strip() else "#" for ln in lines)
        header = f"# --- RAG context ({rag_path.name}) ---\n{block}\n# --- end RAG ---\n\n"
    first_nl = code.find("\n")
    if code.startswith("#") and first_nl != -1:
        return code[: first_nl + 1] + "\n" + header + code[first_nl + 1 :]
    return header + code


def _json_obj_as_py_expr(obj: Any) -> str:
    """生成可在生成代码中求值为等价 dict/list 的表达式（避免 JSON null/bool 与 Python 字面量混写）。"""
    inner = json.dumps(obj, ensure_ascii=False)
    return "json.loads(" + json.dumps(inner) + ")"

def render_api_session_fixtures(
    auth: dict[str, Any],
    session_headers: dict[str, Any],
    *,
    use_healing: bool = True,
    pool_scope: str = "session",
    max_retries: int = 3,
) -> list[str]:
    sh_expr = _json_obj_as_py_expr(session_headers) if session_headers else "None"
    auth_expr = _json_obj_as_py_expr(auth) if auth else "None"
    heal = "True" if use_healing else "False"
    scope = pool_scope if pool_scope in ("session", "function", "module") else "session"
    lines: list[str] = [
        "",
        f"@pytest.fixture(scope='{scope}')",
        "def var_pool():",
        "    return VariablePool()",
        "",
        f"@pytest.fixture(scope='{scope}')",
        "def api_session(var_pool):",
        "    s = create_api_session(",
        "        BASE_URL,",
        f"        {auth_expr},",
        "        var_pool,",
        f"        session_headers={sh_expr},",
        f"        use_healing={heal},",
        f"        max_retries={max_retries},",
        "    )",
        "    yield s",
        "    s.close()",
        "",
    ]
    return lines


def render_case_depends_helpers(pool_scope: str) -> list[str]:
    scope = pool_scope if pool_scope in ("session", "function", "module") else "session"
    return [
        "",
        f"@pytest.fixture(scope='{scope}')",
        "def _case_outcomes():",
        "    return {}",
        "",
        "def _check_case_depends(depends_on, outcomes):",
        "    for dep in depends_on or []:",
        "        if outcomes.get(dep) is not True:",
        "            pytest.skip(f'依赖 {dep} 未通过或未执行')",
        "",
    ]


def render_anon_fixture(session_headers: dict[str, Any]) -> list[str]:
    sh_expr = _json_obj_as_py_expr(session_headers) if session_headers else "None"
    return [
        "",
        "@pytest.fixture(scope='session')",
        "def api_session_anon():",
        f"    s = create_anon_session(session_headers={sh_expr})",
        "    yield s",
        "    s.close()",
        "",
    ]


def render_api_setup_fixture(
    setup_cfg: dict[str, Any],
    *,
    scope: str = "session",
    base_url_var: str = "BASE_URL",
) -> list[str]:
    """铺底：test_init / data_factory；kind=none 时不生成。scope=function 时每条用例独立造数。"""
    if setup_cfg.get("kind") == "none":
        return []
    sc = scope if scope in ("session", "function", "module") else "session"
    return [
        "",
        f"_SETUP_CFG = {_json_obj_as_py_expr(setup_cfg)}",
        "",
        f"@pytest.fixture(scope='{sc}', autouse=True)",
        "def _setup_test_data():",
        f'    """铺底（spec setup, scope={sc}）；TEST_SETUP=none 可跳过"""',
        "    from api_lib.setup_hook import run_api_setup",
        f"    run_api_setup({base_url_var}, _SETUP_CFG)",
        "",
    ]


def resolve_api_isolation(meta: dict[str, Any], setup_cfg: dict[str, Any]) -> tuple[str, str, bool]:
    """返回 (pool_scope, setup_scope, refs_teardown)。"""
    isolation = str(meta.get("isolation") or "").strip().lower()
    teardown = meta.get("teardown") if isinstance(meta.get("teardown"), dict) else {}
    setup_scope = str(setup_cfg.get("scope") or "session").strip().lower()
    per_test = isolation in ("per_test", "function", "test") or setup_scope == "function"
    refs_teardown = per_test or str(teardown.get("mode") or "").lower() in (
        "refs",
        "refs_registry",
        "tracked",
    )
    pool_scope = "function" if per_test else "session"
    setup_scope_out = "function" if per_test else (setup_scope if setup_scope in ("session", "function") else "session")
    return pool_scope, setup_scope_out, refs_teardown


def render_refs_teardown_fixtures(*, pool_scope: str = "function") -> list[str]:
    sc = pool_scope if pool_scope in ("session", "function") else "function"
    return [
        "",
        f"@pytest.fixture(scope='{sc}')",
        "def refs_registry():",
        "    from api_lib import RefsRegistry",
        "    return RefsRegistry()",
        "",
        f"@pytest.fixture(scope='{sc}', autouse=True)",
        "def _teardown_tracked_refs(api_session, var_pool, refs_registry):",
        '    """用例结束按 refs 登记表精确 DELETE，避免全表清理"""',
        "    yield",
        "    refs_registry.cleanup_all(api_session, var_pool, BASE_URL)",
        "",
    ]


def resolve_data_source_path(path_str: str, spec_path: Path | None) -> Path:
    """解析 case/batch 级 data_source 路径（相对 spec 目录或项目根）。"""
    raw = Path(path_str)
    if raw.is_file():
        return raw.resolve()
    candidates: list[Path] = []
    if spec_path is not None:
        candidates.append(spec_path.parent / raw)
        candidates.append(spec_path.parent.parent / raw)
    candidates.append(_CODEGEN_DIR.parent / raw)
    candidates.append(Path.cwd() / raw)
    for c in candidates:
        if c.is_file():
            return c.resolve()
    tried = ", ".join(str(c) for c in candidates)
    raise FileNotFoundError(f"data_source 文件不存在: {path_str}（已尝试: {tried}）")


def normalize_case_data_source(raw: Any, spec_path: Path | None) -> dict[str, Any]:
    if raw is None or (isinstance(raw, str) and not str(raw).strip()):
        raise ValueError("data_source 不能为空")
    if isinstance(raw, str):
        path_str = raw.strip()
        ext = Path(path_str).suffix.lower()
        stype = "json" if ext == ".json" else "csv"
        resolved = resolve_data_source_path(path_str, spec_path)
        return {"type": stype, "path": str(resolved)}
    if isinstance(raw, dict):
        path_str = raw.get("path") or raw.get("file")
        if not path_str:
            raise ValueError("data_source 须含 path 或 file")
        path_str = str(path_str)
        ext = Path(path_str).suffix.lower()
        stype = str(raw.get("type") or ("json" if ext == ".json" else "csv")).lower()
        resolved = resolve_data_source_path(path_str, spec_path)
        out: dict[str, Any] = {"type": stype, "path": str(resolved)}
        for k, v in raw.items():
            if k not in ("path", "file", "type"):
                out[k] = v
        return out
    raise ValueError(f"不支持的 data_source 类型: {type(raw)}")


def _format_expect_label(expect: Any) -> str:
    if isinstance(expect, list):
        return "|".join(str(x) for x in expect)
    if expect is not None:
        return str(expect)
    return "200"


def _emit_review_skip_markers(lines: list[str], case: dict[str, Any], cid: str) -> None:
    if case.get("skip"):
        reason = str(case.get("skip_reason") or case.get("name") or cid)
        lines.append(f"@pytest.mark.skip(reason={json.dumps(reason, ensure_ascii=False)})")
        return
    if case.get("review_required"):
        reason = str(
            case.get("skip_reason")
            or f"{cid} 待评审（OpenAPI X/E 导入草稿；设 REVIEW_REQUIRED_RUN=1 执行）"
        )
        lines.append(
            "@pytest.mark.skipif("
            'os.environ.get("REVIEW_REQUIRED_RUN", "").lower() not in ("1", "true", "yes"), '
            f"reason={json.dumps(reason, ensure_ascii=False)}"
            ")"
        )


def _parametrize_id_from_row(row: dict[str, Any], index: int) -> str:
    for key in ("case_id", "id", "username", "name"):
        val = row.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    return f"row{index}"


def emit_case_function(
    lines: list[str],
    case: dict[str, Any],
    idx: int,
    session_name: str,
    timeout_default: int,
    *,
    use_refs: bool = False,
    use_case_outcomes: bool = False,
    spec_path: Path | None = None,
) -> None:
    cid = case.get("id") or f"TC-{idx+1:03d}"
    method = (case.get("method") or "GET").upper()
    path = case.get("path") or "/"
    expect_label = _format_expect_label(case.get("accept_status") or case.get("expect_status"))
    depends_on = case.get("depends_on") or []

    fn = "test_" + re.sub(r"[^0-9a-zA-Z_]", "_", str(cid).lower()).strip("_")
    if fn.endswith("_") or not fn.startswith("test_"):
        fn = "test_tc_" + str(idx + 1)

    params = [session_name, "var_pool"]
    if use_refs:
        params.append("refs_registry")
    if use_case_outcomes:
        params.append("_case_outcomes")

    layer = case.get("layer")
    priority = case.get("priority")
    trace = case.get("trace")
    story = trace or cid

    data_source_raw = case.get("data_source")
    template_case = {k: v for k, v in case.items() if k != "data_source"}
    param_rows: list[dict[str, Any]] | None = None
    param_ids: list[str] | None = None
    if data_source_raw:
        from api_lib.batch import load_data_rows, merge_case_with_data_row

        ds_cfg = normalize_case_data_source(data_source_raw, spec_path)
        raw_rows = load_data_rows(ds_cfg)
        if not raw_rows:
            raise ValueError(f"case {cid} 的 data_source 无数据行: {ds_cfg.get('path')}")
        param_rows = [merge_case_with_data_row(template_case, row) for row in raw_rows]
        param_ids = [_parametrize_id_from_row(row, i) for i, row in enumerate(raw_rows)]

    lines.append("")
    if param_rows is not None:
        rows_name = f"_CASE_{idx}_ROWS"
        ids_name = f"_CASE_{idx}_IDS"
        lines.append(f"{rows_name} = {_json_obj_as_py_expr(param_rows)}")
        lines.append(f"{ids_name} = {_json_obj_as_py_expr(param_ids)}")
    else:
        lines.append(f"_CASE_{idx} = {_json_obj_as_py_expr(template_case)}")
    lines.append("")
    if layer:
        lines.append(f"@pytest.mark.allure_layer({json.dumps(str(layer))})")
    if priority:
        lines.append(f"@pytest.mark.allure_priority({json.dumps(str(priority))})")
    if story:
        lines.append(f"@pytest.mark.allure_story({json.dumps(str(story))})")
    _emit_review_skip_markers(lines, template_case, str(cid))
    if param_rows is not None:
        lines.append(
            f'@pytest.mark.parametrize("_row_case", _CASE_{idx}_ROWS, ids=_CASE_{idx}_IDS)'
        )
        params.append("_row_case")
    lines.append(f"def {fn}({', '.join(params)}):")
    if param_rows is not None:
        lines.append(f'    """{cid}: {method} {path} → {expect_label}（数据驱动 ×{len(param_rows)}）"""')
    else:
        lines.append(f'    """{cid}: {method} {path} → {expect_label}"""')
    if depends_on:
        lines.append(f"    _check_case_depends({_json_obj_as_py_expr(depends_on)}, _case_outcomes)")
    lines.append("    try:")
    refs_kw = ", refs_registry=refs_registry" if use_refs else ""
    case_expr = "_row_case" if param_rows is not None else f"_CASE_{idx}"
    lines.append(
        f"        run_case({session_name}, var_pool, {case_expr}, BASE_URL, "
        f"timeout_default={timeout_default}{refs_kw})"
    )
    if use_case_outcomes:
        lines.append(f"        _case_outcomes[{json.dumps(str(cid))}] = True")
    lines.append("    except Exception:")
    if use_case_outcomes:
        lines.append(f"        _case_outcomes[{json.dumps(str(cid))}] = False")
    lines.append("        raise")


def emit_scenario_function(
    lines: list[str],
    scenario: dict[str, Any],
    idx: int,
    session_name: str,
    timeout_default: int,
    *,
    use_refs: bool = False,
) -> None:
    """单个场景：多步 HTTP，委托 api_lib.run_scenario。"""
    name = scenario.get("name") or f"scenario_{idx+1}"
    steps = scenario.get("steps") or []
    if not steps:
        raise ValueError(f"场景 {name!r} 的 steps 不能为空")

    fn = "test_scenario_" + re.sub(r"[^0-9a-zA-Z_]+", "_", name.lower()).strip("_")
    if not fn.startswith("test_"):
        fn = "test_" + fn

    needs_anon = any(bool(st.get("no_auth")) for st in steps)
    meta_name = f"_SCENARIO_{idx}"
    params = [session_name, "var_pool"]
    if use_refs:
        params.append("refs_registry")
    if needs_anon:
        params.append("api_session_anon")

    lines.append("")
    lines.append(f"{meta_name} = {_json_obj_as_py_expr(scenario)}")
    lines.append("")
    lines.append(f"def {fn}({', '.join(params)}):")
    lines.append(f'    """场景: {name} — 多步串联"""')
    anon_arg = "api_session_anon" if needs_anon else "None"
    refs_kw = ", refs_registry=refs_registry" if use_refs else ""
    lines.append(
        f"    run_scenario({session_name}, var_pool, {meta_name}, BASE_URL, "
        f"anon_session={anon_arg}, timeout_default={timeout_default}{refs_kw})"
    )


def emit_batch_function(
    lines: list[str],
    meta: dict[str, Any],
    cases: list[dict[str, Any]],
    scenarios: list[dict[str, Any]],
    timeout_default: int,
    *,
    need_anon: bool,
) -> None:
    batch = meta.get("batch") or {}
    progress = batch.get("progress_path") or "output/batch_progress.jsonl"
    params = ["api_session", "var_pool"]
    if need_anon:
        params.append("api_session_anon")

    lines.append("")
    lines.append(f"_BATCH_CFG = {_json_obj_as_py_expr(batch)}")
    lines.append(f"_ALL_CASES = {_json_obj_as_py_expr(cases)}")
    lines.append(f"_ALL_SCENARIOS = {_json_obj_as_py_expr(scenarios)}")
    lines.append("")
    lines.append(f"def test_batch_execute({', '.join(params)}):")
    lines.append('    """批量执行：拓扑排序 + 并发 + 失败阻断"""')
    anon_arg = "api_session_anon" if need_anon else "None"
    lines.append(
        f"    result = run_batch("
        f"api_session, var_pool, BASE_URL, _ALL_CASES, _ALL_SCENARIOS, _BATCH_CFG, "
        f"anon_session={anon_arg}, timeout_default={timeout_default}, "
        f"progress_path={json.dumps(progress, ensure_ascii=False)})"
    )
    lines.append("    assert not result['failed'], result")


def render_api_pytest(meta: dict[str, Any], body: str, *, spec_path: Path | None = None) -> str:
    base_url = meta.get("base_url", "http://your-server:5000")
    cases = meta.get("cases") or []
    scenarios = meta.get("scenarios") or []
    batch_cfg = meta.get("batch")
    if not cases and not scenarios and not batch_cfg:
        raise ValueError("cases、scenarios、batch 至少填一个")
    td = int(meta.get("timeout_default") or 30)
    sh = meta.get("session_headers") or meta.get("default_headers") or {}
    auth = meta.get("auth") or {}
    use_healing = meta.get("healing", meta.get("use_healing", True))
    healing_cfg = meta.get("healing")
    max_retries = 3
    if isinstance(healing_cfg, dict):
        max_retries = int(healing_cfg.get("max_retries") or 3)

    from api_lib.setup_hook import parse_api_setup
    from api_lib.batch import topological_sort as _topo_sort_cases

    setup_cfg = parse_api_setup(meta)
    pool_scope, setup_scope, refs_teardown = resolve_api_isolation(meta, setup_cfg)

    has_case_depends = any(c.get("depends_on") for c in cases)
    if has_case_depends:
        case_ids = [str(c.get("id") or f"TC-{i+1:03d}") for i, c in enumerate(cases)]
        dep_map = {case_ids[i]: list(c.get("depends_on") or []) for i, c in enumerate(cases)}
        try:
            order_ids = _topo_sort_cases(case_ids, dep_map)
            id_to_case = {case_ids[i]: cases[i] for i in range(len(cases))}
            cases = [id_to_case[cid] for cid in order_ids if cid in id_to_case]
        except ValueError:
            pass

    lines = [
        "# Auto-generated by spec runner (api_lib)",
        "",
        "from __future__ import annotations",
        "",
        "import json",
        "import os",
        "import sys",
        "from pathlib import Path",
        "",
        "_codegen = Path(__file__).resolve().parent.parent / 'codegen'",
        "if _codegen.is_dir() and str(_codegen) not in sys.path:",
        "    sys.path.insert(0, str(_codegen))",
        "",
        "import pytest",
        "import requests",
        "",
        "from api_lib import VariablePool, run_batch, run_case, run_scenario",
        "from api_lib.http_client import create_anon_session, create_api_session",
        "",
        f"BASE_URL = os.environ.get('TEST_BASE_URL', {esc(base_url)})",
        "",
    ]
    business = meta.get("business")
    if isinstance(business, str) and business.strip():
        lines.append(f"os.environ.setdefault('ALLURE_BUSINESS', {json.dumps(business.strip(), ensure_ascii=False)})")
        lines.append("")

    lines.extend(render_api_setup_fixture(setup_cfg, scope=setup_scope))
    if refs_teardown:
        lines.extend(render_refs_teardown_fixtures(pool_scope=pool_scope))

    need_anon = any(c.get("no_auth") for c in cases) or any(
        st.get("no_auth") for sc in scenarios for st in (sc.get("steps") or [])
    )

    lines.extend(
        render_api_session_fixtures(
            auth, sh, use_healing=bool(use_healing), pool_scope=pool_scope, max_retries=max_retries
        )
    )

    if has_case_depends:
        lines.extend(render_case_depends_helpers(pool_scope))

    if need_anon:
        lines.extend(render_anon_fixture(sh))

    batch_only = bool(batch_cfg and batch_cfg.get("only"))
    if not batch_only:
        for i, case in enumerate(cases):
            sess = "api_session_anon" if case.get("no_auth") else "api_session"
            emit_case_function(
                lines, case, i, sess, td,
                use_refs=refs_teardown,
                use_case_outcomes=has_case_depends,
                spec_path=spec_path,
            )

        for si, scenario in enumerate(scenarios):
            emit_scenario_function(lines, scenario, si, "api_session", td, use_refs=refs_teardown)

    if batch_cfg:
        emit_batch_function(lines, meta, cases, scenarios, td, need_anon=need_anon)

    if body.strip():
        lines.extend(["", "# --- spec 正文 ---", "# " + body.replace("\n", "\n# ")])
    return "\n".join(lines) + "\n"


def _emit_ui_flow_test_via_lib(
    lines: list[str],
    flow: dict[str, Any],
    fn: str,
    *,
    prefix: str = "test_ui_",
    healing: bool = True,
    pretest: bool = False,
) -> None:
    nm = flow.get("name") or fn.replace(prefix, "")
    fst = flow.get("steps") or []
    if not fst:
        raise ValueError(f"flow {nm!r} 缺 steps")
    const = fn.upper().replace("TEST_", "_META_")
    default_expect = flow.get("expect") or []
    param_rows = flow.get("parametrize") or []

    lines.append(f"{const}_STEPS = {_json_obj_as_py_expr(fst)}")
    lines.append(f"{const}_EXPECTS = {_json_obj_as_py_expr(default_expect)}")
    lines.append("")

    heal_lit = "True" if healing else "False"
    pre_lit = "True" if pretest else "False"

    layer = flow.get("layer")
    priority = flow.get("priority")
    story = flow.get("trace") or flow.get("id") or nm

    def _append_allure_marks() -> None:
        if layer:
            lines.append(f"@pytest.mark.allure_layer({json.dumps(str(layer))})")
        if priority:
            lines.append(f"@pytest.mark.allure_priority({json.dumps(str(priority))})")
        if story:
            lines.append(f"@pytest.mark.allure_story({json.dumps(str(story))})")

    if param_rows:
        if not isinstance(param_rows, list):
            raise ValueError("parametrize 须为数组")
        case_const = f"{const}_PARAMS"
        lines.append(f"{case_const} = {_json_obj_as_py_expr(param_rows)}")
        lines.append("")
        lines.append(
            f'@pytest.mark.parametrize("case", {case_const}, '
            f"ids=[str(c.get('id') or i) for i, c in enumerate({case_const})])"
        )
        _append_allure_marks()
        lines.append(f"def {fn}(page: Page, case):")
        lines.append(f'    """{nm}（数据驱动）"""')
        lines.append(f"    ctx = UIContext(dict(case.get('vars') or {{}}))")
        lines.append(f"    _ex = case.get('expect') if case.get('expect') is not None else {const}_EXPECTS")
        lines.append(
            f"    run_ui_flow(page, {const}_STEPS, expects=_ex, base_url=BASE_URL, "
            f"ctx=ctx, heal={heal_lit}, pretest={pre_lit})"
        )
        lines.append("")
        return

    _append_allure_marks()
    lines.append(f"def {fn}(page: Page):")
    lines.append(f'    """{nm}"""')
    lines.append(
        f"    run_ui_flow(page, {const}_STEPS, expects={const}_EXPECTS, base_url=BASE_URL, "
        f"heal={heal_lit}, pretest={pre_lit})"
    )
    lines.append("")


def emit_ui_batch_function(
    lines: list[str],
    meta: dict[str, Any],
    flows: list[dict[str, Any]],
) -> None:
    batch = meta.get("batch") or {}
    lines.append(f"_UI_BATCH_CFG = {_json_obj_as_py_expr(batch)}")
    lines.append(f"_UI_ALL_FLOWS = {_json_obj_as_py_expr(flows)}")
    lines.append("")
    lines.append("def test_ui_batch_execute(page: Page):")
    lines.append('    """UI 批量 flow 执行"""')
    lines.append(
        "    result = run_ui_batch(page, _UI_ALL_FLOWS, base_url=BASE_URL, batch_cfg=_UI_BATCH_CFG)"
    )
    lines.append("    assert not result['failed'], result")
    lines.append("")


def render_ui_pytest(meta: dict[str, Any], body: str) -> str:
    base_url = meta.get("base_url", "http://your-server:5000")
    vp = meta.get("viewport") or {"width": 1280, "height": 720}
    w, h = int(vp.get("width", 1280)), int(vp.get("height", 720))
    flow_list: list[dict[str, Any]] = list(meta.get("flows") or [])
    scenario_list: list[dict[str, Any]] = list(meta.get("scenarios") or [])
    steps = meta.get("steps") or []
    exp = meta.get("expect") or []
    batch_cfg = meta.get("batch")
    healing = bool(meta.get("healing", meta.get("use_healing", True)))
    pretest = bool(meta.get("pretest", False))
    storage_state = meta.get("storage_state")

    if storage_state:
        fx = f'''@pytest.fixture(scope="function")
def browser_context_args(browser_context_args: dict) -> dict:
    from pathlib import Path
    ctx = {{
        **browser_context_args,
        "viewport": {{"width": {w}, "height": {h}}},
    }}
    storage = os.environ.get("UI_STORAGE_STATE", {esc(str(storage_state))})
    if Path(storage).is_file():
        ctx["storage_state"] = storage
    return ctx
'''
    else:
        fx = f'''@pytest.fixture(scope="function")
def browser_context_args(browser_context_args: dict) -> dict:
    return {{
        **browser_context_args,
        "viewport": {{"width": {w}, "height": {h}}},
    }}
'''

    heal_lit = "True" if healing else "False"
    pre_lit = "True" if pretest else "False"
    selector_registry = meta.get("selector_registry")
    use_registry = bool(selector_registry)

    lines = [
        "# Auto-generated by spec runner (ui_lib)",
        "",
        "from __future__ import annotations",
        "",
        "import json",
        "import os",
        "import sys",
        "from pathlib import Path",
        "",
        "_codegen = Path(__file__).resolve().parent.parent / 'codegen'",
        "if _codegen.is_dir() and str(_codegen) not in sys.path:",
        "    sys.path.insert(0, str(_codegen))",
        "",
        "import pytest",
        "from playwright.sync_api import Page",
        "",
        "from ui_lib import UIContext, run_ui_batch, run_ui_flow",
        "",
        f"BASE_URL = os.environ.get('TEST_BASE_URL', {esc(base_url)})",
        "",
        fx,
    ]
    business = meta.get("business")
    if isinstance(business, str) and business.strip():
        lines.insert(-1, f"os.environ.setdefault('ALLURE_BUSINESS', {json.dumps(business.strip(), ensure_ascii=False)})")
        lines.insert(-1, "")

    from api_lib.setup_hook import parse_api_setup

    ui_setup_cfg = parse_api_setup(meta)
    if ui_setup_cfg.get("kind") != "none":
        lines.extend(render_api_setup_fixture(ui_setup_cfg, scope="session"))
    if use_registry:
        reg_path = str(selector_registry)
        lines.extend(
            [
                f"os.environ.setdefault('SELECTOR_REGISTRY_PATH', {esc(reg_path)})",
                "",
            ]
        )

    lines.append("")

    all_flows = flow_list + scenario_list
    batch_only = bool(batch_cfg and batch_cfg.get("only"))

    if not batch_only:
        if all_flows:
            for fi, flow in enumerate(flow_list):
                nm = flow.get("name") or f"flow_{fi+1}"
                slug = re.sub(r"[^a-z0-9_]+", "_", str(nm).lower()).strip("_") or f"flow_{fi+1}"
                _emit_ui_flow_test_via_lib(
                    lines, flow, "test_ui_" + slug, healing=healing, pretest=pretest
                )
            for si, scenario in enumerate(scenario_list):
                nm = scenario.get("name") or f"scenario_{si+1}"
                slug = re.sub(r"[^a-z0-9_]+", "_", str(nm).lower()).strip("_") or f"scenario_{si+1}"
                _emit_ui_flow_test_via_lib(
                    lines,
                    scenario,
                    "test_scenario_ui_" + slug,
                    prefix="test_scenario_ui_",
                    healing=healing,
                    pretest=pretest,
                )
        else:
            if not steps:
                raise ValueError("须提供 steps、flows 或 scenarios")
            lines.append(f"_UI_STEPS = {_json_obj_as_py_expr(steps)}")
            lines.append(f"_UI_EXPECTS = {_json_obj_as_py_expr(exp)}")
            lines.append("")
            lines.append("def test_declarative_ui_flow(page: Page):")
            lines.append('    """UI 声明式流程"""')
            lines.append(
                f"    run_ui_flow(page, _UI_STEPS, expects=_UI_EXPECTS, base_url=BASE_URL, "
                f"heal={heal_lit}, pretest={pre_lit})"
            )
            lines.append("")

    if batch_cfg:
        emit_ui_batch_function(lines, meta, all_flows or [{"name": "default", "steps": steps, "expect": exp}])

    if body.strip():
        lines.extend(["", "# --- spec 正文 ---", "# " + body.replace("\n", "\n# ")])
    return "\n".join(lines) + "\n"
def _appium_step_extra_kwargs(step: dict[str, Any]) -> str:
    """生成 _find/_click/_fill 的可选关键字参数字符串。"""
    parts: list[str] = []
    rk = step.get("registry_key")
    if rk:
        parts.append(f"registry_key={esc(str(rk))}")
    wm = step.get("wait") or step.get("wait_mode")
    if wm:
        parts.append(f"wait_mode={esc(str(wm))}")
    return (", " + ", ".join(parts)) if parts else ""


def emit_appium_steps(lines: list[str], steps: list[dict[str, Any]]) -> None:
    """Appium 单条用例内的 steps（与 UI spec 的 action 命名保持一致）。"""
    ind = "    "
    for step in steps:
        a = (step.get("action") or "").lower().replace(" ", "_")
        wait_override = step.get("wait_sec")
        wo = "" if wait_override is None else f", timeout={float(wait_override)}"
        if a == "wait_timeout_ms":
            ms = int(step.get("ms", 500))
            lines.append(f"{ind}time.sleep({ms} / 1000.0)")
        elif a == "switch_context":
            ctx = step.get("name") or step.get("context") or "NATIVE_APP"
            lines.append(f"{ind}_switch_context(driver, {esc(ctx)})")
        elif a in ("open_url", "goto", "navigate"):
            url = step.get("url") or step.get("value") or ""
            lines.append(f"{ind}_open_url(driver, {esc(str(url))})")
        elif a == "back":
            lines.append(f"{ind}driver.back()")
        elif a == "hide_keyboard":
            lines.append(f"{ind}try:")
            lines.append(f"{ind}    driver.hide_keyboard()")
            lines.append(f"{ind}except Exception:")
            lines.append(f"{ind}    pass")
        elif a in ("permission_allow", "permission_deny", "permission"):
            allow = a != "permission_deny"
            if a == "permission":
                allow = bool(step.get("allow", True))
            btn = step.get("button_text") or step.get("text")
            btn_arg = "None" if btn is None else esc(str(btn))
            lines.append(f"{ind}_handle_permission(driver, allow={allow}, button_text={btn_arg})")
        elif a == "swipe":
            sx = int(step.get("start_x", step.get("from_x", 500)))
            sy = int(step.get("start_y", step.get("from_y", 1500)))
            ex = int(step.get("end_x", step.get("to_x", 500)))
            ey = int(step.get("end_y", step.get("to_y", 500)))
            dur = int(step.get("duration_ms", step.get("duration", 800)))
            lines.append(f"{ind}_swipe(driver, {sx}, {sy}, {ex}, {ey}, {dur})")
        elif a == "scroll":
            direction = step.get("direction") or step.get("value") or "down"
            percent = float(step.get("percent", 0.75))
            lines.append(f"{ind}_scroll(driver, {esc(str(direction))}, {percent})")
        elif a == "tap":
            x = int(step.get("x", 0))
            y = int(step.get("y", 0))
            lines.append(f"{ind}_tap(driver, {x}, {y})")
        elif a == "click":
            by = step.get("by") or "accessibility_id"
            loc = step.get("value") or step.get("selector") or ""
            extra = _appium_step_extra_kwargs(step)
            if not loc:
                lines.append(f'{ind}raise RuntimeError("click: 需要 value 或 selector（定位符）")')
            else:
                lines.append(f"{ind}_click(driver, {esc(by)}, {esc(loc)}{wo}{extra})")
        elif a == "fill":
            by = step.get("by") or "accessibility_id"
            loc = step.get("value") or step.get("selector") or ""
            text = step.get("input")
            if text is None:
                text = step.get("text", "")
            extra = _appium_step_extra_kwargs(step)
            if not loc:
                lines.append(f'{ind}raise RuntimeError("fill: 需要 value 或 selector")')
            else:
                lines.append(f"{ind}_fill(driver, {esc(by)}, {esc(loc)}, {esc(str(text))}{wo}{extra})")
        else:
            lines.append(f'{ind}raise RuntimeError({esc("未知 action: " + a)})')


def emit_appium_expects(lines: list[str], expects: list[dict[str, Any]]) -> None:
    ind = "    "
    for ex in expects or []:
        raw_t = ex.get("type")
        t = str(raw_t).strip().lower() if raw_t is not None else ""
        if not t:
            lines.append(
                f'{ind}raise RuntimeError('
                f'{esc("expect 缺少 type：请填写 element_visible 或 text_in_page_source")})'
            )
            continue
        if t == "element_visible":
            by = ex.get("by") or "accessibility_id"
            loc = ex.get("value") or ex.get("selector") or ""
            if not loc:
                lines.append(f'{ind}raise RuntimeError("expect element_visible: 需要 value")')
            else:
                wo = ex.get("wait_sec")
                wos = "" if wo is None else f", timeout={float(wo)}"
                extra = _appium_step_extra_kwargs(ex)
                lines.append(f"{ind}assert _find(driver, {esc(by)}, {esc(loc)}{wos}{extra}).is_displayed()")
        elif t == "text_in_page_source":
            sub = ex.get("text", "")
            lines.append(f"{ind}assert {esc(sub)} in driver.page_source  # 弱断言：跨端慎用")
        else:
            lines.append(f'{ind}raise RuntimeError({esc("未知 expect type: " + t)})')


def render_appium_pytest(meta: dict[str, Any], body: str) -> str:
    """声明式 Appium spec → pytest（Appium-Python-Client + Selenium Wait）。"""
    caps = meta.get("capabilities")
    if not isinstance(caps, dict) or not caps:
        raise ValueError("capabilities 须为非空字典（platformName、automationName、app 或 appPackage 等）")
    server = meta.get("appium_server") or "http://127.0.0.1:4723"
    base_url = meta.get("base_url") or "http://your-server:5001"
    api_base_url = meta.get("api_base_url") or base_url
    implicit = int(meta.get("implicit_wait_sec", 10))
    explicit = float(meta.get("explicit_wait_sec", 15))
    driver_scope = str(meta.get("driver_scope") or "class").strip().lower()
    if driver_scope not in ("class", "function", "module", "session"):
        driver_scope = "class"
    layer = meta.get("layer")
    priority = meta.get("priority")
    business = meta.get("business")
    flows = meta.get("flows")
    steps = meta.get("steps") or []
    exp = meta.get("expect") or []
    selector_registry = meta.get("selector_registry")

    caps_expr = _json_obj_as_py_expr(caps)

    from api_lib.setup_hook import parse_api_setup

    setup_cfg = parse_api_setup(meta)

    helpers = f'''
def _by(name: str):
    key = (name or "").strip().lower().replace(" ", "_").replace("-", "_")
    if key in ("content_desc", "contentdesc"):
        key = "accessibility_id"
    mapping = {{
        "accessibility_id": AppiumBy.ACCESSIBILITY_ID,
        "id": AppiumBy.ID,
        "xpath": AppiumBy.XPATH,
        "class_name": AppiumBy.CLASS_NAME,
        "name": AppiumBy.NAME,
        "android_uiautomator": AppiumBy.ANDROID_UIAUTOMATOR,
        "ios_predicate": AppiumBy.IOS_PREDICATE,
        "ios_class_chain": AppiumBy.IOS_CLASS_CHAIN,
        "css": AppiumBy.CSS_SELECTOR,
        "css_selector": AppiumBy.CSS_SELECTOR,
    }}
    if key not in mapping:
        raise ValueError(f"未知 by: {{name!r}}，可选: {{', '.join(sorted(mapping))}}")
    return mapping[key]


def _find(driver, by_name: str, locator: str, timeout: float | None = None, *, wait_mode: str | None = None, registry_key: str | None = None):
    wait_sec = {explicit} if timeout is None else float(timeout)
    try:
        from mobile_lib.locator_healer import find_with_heal
        return find_with_heal(
            driver, by_name, locator,
            timeout_sec=wait_sec,
            wait_mode=wait_mode,
            registry_key=registry_key,
        )
    except ImportError:
        wm = (wait_mode or os.environ.get("MOBILE_WAIT_MODE", "presence")).strip().lower()
        by = _by(by_name)
        wait = WebDriverWait(driver, wait_sec)
        if wm in ("clickable", "click", "enabled"):
            cond = EC.element_to_be_clickable((by, locator))
        elif wm in ("visible", "displayed", "visibility"):
            cond = EC.visibility_of_element_located((by, locator))
        else:
            cond = EC.presence_of_element_located((by, locator))
        return wait.until(cond)


def _click(driver, by_name: str, locator: str, timeout: float | None = None, *, wait_mode: str | None = None, registry_key: str | None = None):
    try:
        from mobile_lib.locator_healer import click_with_heal
        click_with_heal(
            driver, by_name, locator,
            timeout_sec={explicit} if timeout is None else float(timeout),
            registry_key=registry_key,
        )
    except ImportError:
        from selenium.common.exceptions import StaleElementReferenceException
        el = _find(driver, by_name, locator, timeout, wait_mode=wait_mode or "clickable", registry_key=registry_key)
        try:
            el.click()
        except StaleElementReferenceException:
            _find(driver, by_name, locator, timeout, wait_mode=wait_mode or "clickable", registry_key=registry_key).click()


def _fill(driver, by_name: str, locator: str, text: str, timeout: float | None = None, *, wait_mode: str | None = None, registry_key: str | None = None):
    from selenium.common.exceptions import StaleElementReferenceException
    el = _find(driver, by_name, locator, timeout, wait_mode=wait_mode or "clickable", registry_key=registry_key)
    try:
        try:
            el.clear()
        except Exception:
            pass
        el.send_keys(text)
    except StaleElementReferenceException:
        el = _find(driver, by_name, locator, timeout, wait_mode=wait_mode or "clickable", registry_key=registry_key)
        try:
            el.clear()
        except Exception:
            pass
        el.send_keys(text)


def _resolve_url(url: str) -> str:
    u = (url or "").replace("${{TEST_BASE_URL}}", BASE_URL).replace("${{BASE_URL}}", BASE_URL)
    if u.startswith("$") and not u.startswith("http"):
        env_key = u.lstrip("${{").rstrip("}}")
        u = os.environ.get(env_key, u)
    return u


def _switch_context(driver, name: str) -> None:
    key = (name or "NATIVE_APP").strip()
    if key.upper() in ("NATIVE_APP", "NATIVE"):
        driver.switch_to.context("NATIVE_APP")
        return
    for ctx in driver.contexts:
        if key in ctx:
            driver.switch_to.context(ctx)
            return
    raise RuntimeError(f"未找到 context 含 {{key!r}}，当前: {{driver.contexts}}")


def _open_url(driver, url: str) -> None:
    driver.get(_resolve_url(url))


def _swipe(driver, start_x: int, start_y: int, end_x: int, end_y: int, duration_ms: int = 800) -> None:
    try:
        driver.execute_script(
            "mobile: swipeGesture",
            {{
                "left": min(start_x, end_x),
                "top": min(start_y, end_y),
                "width": max(abs(end_x - start_x), 1),
                "height": max(abs(end_y - start_y), 1),
                "direction": "up" if end_y < start_y else "down" if end_y > start_y else ("left" if end_x < start_x else "right"),
                "percent": 0.75,
            }},
        )
    except Exception:
        driver.swipe(start_x, start_y, end_x, end_y, duration_ms)


def _scroll(driver, direction: str = "down", percent: float = 0.75) -> None:
    size = driver.get_window_size()
    w, h = size["width"], size["height"]
    left, top, width, height = int(w * 0.1), int(h * 0.2), int(w * 0.8), int(h * 0.6)
    try:
        driver.execute_script(
            "mobile: scrollGesture",
            {{"left": left, "top": top, "width": width, "height": height, "direction": direction, "percent": percent}},
        )
    except Exception:
        _swipe(driver, w // 2, int(h * 0.7), w // 2, int(h * 0.3), 800)


def _tap(driver, x: int, y: int) -> None:
    try:
        driver.execute_script("mobile: clickGesture", {{"x": x, "y": y}})
    except Exception:
        driver.tap([(x, y)], 100)


def _handle_permission(driver, allow: bool = True, button_text: str | None = None) -> None:
    ids = (
        ["com.android.permissioncontroller:id/permission_allow_button", "com.android.packageinstaller:id/permission_allow_button"]
        if allow
        else ["com.android.permissioncontroller:id/permission_deny_button", "com.android.packageinstaller:id/permission_deny_button"]
    )
    if button_text:
        try:
            el = driver.find_element(
                AppiumBy.ANDROID_UIAUTOMATOR,
                f'new UiSelector().textContains({{button_text}})',
            )
            el.click()
            return
        except Exception:
            pass
    for rid in ids:
        try:
            driver.find_element(AppiumBy.ID, rid).click()
            return
        except Exception:
            continue
'''

    lines = [
        "# Auto-generated by spec runner — Appium",
        "",
        "from __future__ import annotations",
        "",
        "import json",
        "import os",
        "import sys",
        "import time",
        "from pathlib import Path",
        "",
        "_codegen = Path(__file__).resolve().parent.parent / 'codegen'",
        "if _codegen.is_dir() and str(_codegen) not in sys.path:",
        "    sys.path.insert(0, str(_codegen))",
        "",
        "import pytest",
        "from appium import webdriver",
        "from appium.options.common import AppiumOptions",
        "from appium.webdriver.common.appiumby import AppiumBy",
        "from selenium.webdriver.support.ui import WebDriverWait",
        "from selenium.webdriver.support import expected_conditions as EC",
        "",
        f"APPIUM_SERVER = os.environ.get('APPIUM_SERVER_URL', {esc(server)})",
        f"BASE_URL = os.environ.get('TEST_BASE_URL', {esc(base_url)})",
        f"API_BASE_URL = os.environ.get('TEST_API_BASE_URL', {esc(api_base_url)})",
        f"CAPABILITIES = json.loads(os.environ.get('APPIUM_CAPABILITIES', json.dumps({caps_expr})))",
        f"IMPLICIT_WAIT_SEC = {implicit}",
        f"APPIUM_ARTIFACTS_DIR = Path(os.environ.get('APPIUM_ARTIFACTS_DIR', 'output/appium_artifacts'))",
        "",
        helpers,
        "",
    ]

    if selector_registry:
        lines.extend(
            [
                f"os.environ.setdefault('MOBILE_SELECTOR_REGISTRY_PATH', {esc(str(selector_registry))})",
                "",
            ]
        )

    if isinstance(business, str) and business.strip():
        lines.append(f"os.environ.setdefault('ALLURE_BUSINESS', {json.dumps(business.strip(), ensure_ascii=False)})")
        lines.append("")

    setup_scope = str(setup_cfg.get("scope") or "session").strip().lower()
    if setup_scope not in ("session", "function", "module"):
        setup_scope = "session"
    lines.extend(
        render_api_setup_fixture(setup_cfg, scope=setup_scope, base_url_var="API_BASE_URL")
    )

    lines.extend([
        "",
        f'@pytest.fixture(scope="{driver_scope}")',
        "def driver():",
        "    opts = AppiumOptions()",
        "    opts.load_capabilities(CAPABILITIES)",
        "    d = webdriver.Remote(APPIUM_SERVER, options=opts)",
        "    d.implicitly_wait(IMPLICIT_WAIT_SEC)",
        "    yield d",
        "    d.quit()",
        "",
        "@pytest.hookimpl(tryfirst=True, hookwrapper=True)",
        "def pytest_runtest_makereport(item, call):",
        "    outcome = yield",
        "    rep = outcome.get_result()",
        "    if rep.when == 'call' and rep.failed:",
        "        drv = item.funcargs.get('driver')",
        "        if drv:",
        "            APPIUM_ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)",
        "            png = APPIUM_ARTIFACTS_DIR / f'{item.name}_fail.png'",
        "            try:",
        "                drv.save_screenshot(str(png))",
        "            except Exception:",
        "                pass",
        "            try:",
        "                xml = APPIUM_ARTIFACTS_DIR / f'{item.name}_source.xml'",
        "                xml.write_text(drv.page_source, encoding='utf-8')",
        "            except Exception:",
        "                pass",
        "",
    ])

    def _append_allure(flow_meta: dict[str, Any] | None = None) -> None:
        fm = flow_meta or {}
        ly = fm.get("layer") or layer
        pr = fm.get("priority") or priority
        st = fm.get("story") or fm.get("name")
        if ly:
            lines.append(f"@pytest.mark.allure_layer({json.dumps(str(ly))})")
        if pr:
            lines.append(f"@pytest.mark.allure_priority({json.dumps(str(pr))})")
        if st:
            lines.append(f"@pytest.mark.allure_story({json.dumps(str(st))})")

    if flows:
        for fi, flow in enumerate(flows):
            nm = flow.get("name") or f"flow_{fi+1}"
            slug = re.sub(r"[^a-z0-9_]+", "_", str(nm).lower()).strip("_")
            if not slug:
                slug = f"flow_{fi+1}"
            fn = "test_appium_" + slug
            fst = flow.get("steps") or []
            if not fst:
                raise ValueError(f"flows[{fi}] 缺 steps")
            _append_allure(flow if isinstance(flow, dict) else None)
            lines.append(f"def {fn}(driver):")
            lines.append(f'    """{nm}"""')
            emit_appium_steps(lines, fst)
            emit_appium_expects(lines, flow.get("expect") or [])
            lines.append("")
    else:
        if not steps:
            raise ValueError("须提供 steps 或 flows")
        _append_allure(None)
        lines.append("def test_declarative_appium_flow(driver):")
        lines.append('    """Appium 声明式流程"""')
        emit_appium_steps(lines, steps)
        emit_appium_expects(lines, exp)
        lines.append("")

    if body.strip():
        lines.extend(["", "# --- spec 正文 ---", "# " + body.replace("\n", "\n# ")])
    return "\n".join(lines) + "\n"


# ──────────────────────────────────────────────
# OpenAPI / Swagger 导入功能
# ──────────────────────────────────────────────

def _resolve_ref_node(data: dict[str, Any], ref: str, seen: set[str]) -> Any:
    """解析 JSON Pointer 式 $ref（#/components/schemas/X 或 #/definitions/X）。"""
    if not isinstance(ref, str) or not ref.startswith("#/") or ref in seen:
        return None
    seen.add(ref)
    parts = ref[2:].split("/")
    node: Any = data
    for p in parts:
        if not isinstance(node, dict):
            return None
        node = node.get(p)
    if isinstance(node, dict) and "$ref" in node:
        return _resolve_ref_node(data, node["$ref"], seen)
    return node


def dereference_schema(data: dict[str, Any], schema: Any, seen: set[str] | None = None) -> dict[str, Any]:
    """展开 $ref、合并 allOf，得到用于生成示例的对象 schema。"""
    if seen is None:
        seen = set()
    if not isinstance(schema, dict):
        return {}
    if "$ref" in schema:
        resolved = _resolve_ref_node(data, schema["$ref"], set(seen))
        if not isinstance(resolved, dict):
            return {}
        return dereference_schema(data, resolved, seen)
    if "allOf" in schema and isinstance(schema.get("allOf"), list):
        merged: dict[str, Any] = {"type": "object", "properties": {}, "required": []}
        req_acc: list[str] = []
        for sub in schema["allOf"]:
            if not isinstance(sub, dict):
                continue
            d = dereference_schema(data, sub, set(seen))
            props = d.get("properties")
            if isinstance(props, dict):
                merged["properties"].update(props)
            if isinstance(d.get("required"), list):
                req_acc.extend(str(x) for x in d["required"] if isinstance(x, str))
        if req_acc:
            merged["required"] = req_acc
        return merged
    out = dict(schema)
    props = out.get("properties")
    if isinstance(props, dict):
        newp: dict[str, Any] = {}
        for k, v in props.items():
            if isinstance(v, dict) and "$ref" in v:
                newp[k] = dereference_schema(data, v, set(seen))
            else:
                newp[k] = v
        out["properties"] = newp
    return out


def _schema_to_example(data: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    """从 OpenAPI schema 生成示例 JSON body（解析 $ref / allOf / anyOf，嵌套 object/array）。"""
    sch = dereference_schema(data, schema)
    if not isinstance(sch, dict):
        return {}
    
    # 处理 anyOf：取第一个非 null 选项
    if "anyOf" in sch:
        any_of = sch["anyOf"]
        if isinstance(any_of, list):
            for option in any_of:
                if isinstance(option, dict):
                    opt_type = option.get("type")
                    if opt_type and opt_type != "null":
                        sch = dereference_schema(data, option)
                        break
    
    # 处理 oneOf：取第一个选项
    if "oneOf" in sch:
        one_of = sch["oneOf"]
        if isinstance(one_of, list) and one_of:
            sch = dereference_schema(data, one_of[0])
    result: dict[str, Any] = {}
    properties = sch.get("properties")
    if not isinstance(properties, dict):
        properties = {}
    required = sch.get("required")
    req_names = {str(x) for x in required} if isinstance(required, list) else set()

    type_defaults = {
        "string": "example",
        "integer": 1,  # 改为 1，避免 0 被误判为无效
        "number": 1.0,
        "boolean": True,
        "array": [],
        "object": {},
    }

    names = list(dict.fromkeys([*sorted(req_names), *properties.keys()]))
    for name in names:
        prop = properties.get(name, {"type": "string"})
        if not isinstance(prop, dict):
            result[name] = "example"
            continue
        prop = dereference_schema(data, prop, set())
        
        # 处理 anyOf/oneOf：取第一个非 null 选项的类型
        if "anyOf" in prop:
            any_of = prop["anyOf"]
            if isinstance(any_of, list):
                for option in any_of:
                    if isinstance(option, dict):
                        opt_type = option.get("type")
                        if opt_type and opt_type != "null":
                            prop = dereference_schema(data, option, set())
                            break
        if "oneOf" in prop:
            one_of = prop["oneOf"]
            if isinstance(one_of, list) and one_of:
                prop = dereference_schema(data, one_of[0], set())
        
        ptype = prop.get("type", "string")

        if "example" in prop:
            result[name] = prop["example"]
            continue
        if "default" in prop:
            result[name] = prop["default"]
            continue

        if ptype == "object" or "properties" in prop:
            nested = _schema_to_example(data, prop)
            result[name] = nested if nested else {}
            continue
        if ptype == "array":
            items = prop.get("items")
            if isinstance(items, dict):
                it = dereference_schema(data, items, set())
                if it.get("type") == "object" or "properties" in it:
                    one = _schema_to_example(data, it)
                    result[name] = [one] if one else []
                else:
                    itype = it.get("type", "string")
                    result[name] = [type_defaults.get(itype, "example")]
            else:
                result[name] = []
            continue

        # 智能类型推断
        result[name] = _smart_default(prop, name, ptype)
    return result


def _build_json_expr(obj, runtime_replace: bool = True) -> str:
    """将 dict 转为 Python 表达式字符串，__ENV__:VAR 转为 os.environ.get(...)。
    
    支持运行时占位符替换（当 runtime_replace=True）：
    - {{timestamp}} → 当前时间戳字符串（秒级）
    - {{uuid}} → UUID4 前 8 位
    - {{token}} → 从 _saved_token 变量读取（由 save_token: true 设置）
    """
    if isinstance(obj, str):
        if obj.startswith('__ENV__:'):
            return f"os.environ.get({json.dumps(obj[8:])}, '')"
        # 运行时占位符替换：生成字符串拼接表达式
        if runtime_replace and '{{' in obj:
            placeholders = {
                '{{timestamp}}': 'str(int(__import__("time").time()))',
                '{{uuid}}': 'str(__import__("uuid").uuid4())[:8]',
                '{{token}}': 'str(_saved_token if _saved_token else "")',
            }
            parts = [obj]
            for ph, expr in placeholders.items():
                new_parts = []
                for p in parts:
                    if ph in p:
                        sub = p.split(ph)
                        for si, s in enumerate(sub):
                            if si > 0:
                                new_parts.append(expr)
                            if s:
                                new_parts.append(json.dumps(s))
                        parts = new_parts if new_parts else [p]
                    else:
                        new_parts.append(p)
                parts = new_parts
            if len(parts) == 1:
                return json.dumps(obj)
            return ' + '.join(parts)
        return json.dumps(obj)
    if isinstance(obj, dict):
        pairs = []
        for k, v in obj.items():
            pairs.append(f"{json.dumps(k)}: {_build_json_expr(v)}")
        return "{" + ", ".join(pairs) + "}"
    if isinstance(obj, list):
        items = [_build_json_expr(x) for x in obj]
        return "[" + ", ".join(items) + "]"
    return json.dumps(obj)

def _smart_default(prop: dict[str, Any], name: str, ptype: str) -> Any:
    """根据 OpenAPI schema 生成智能默认值，避免 'example' 导致的 422 报错。"""
    # 根据字段名推断
    name_lower = name.lower()
    if "platform" in name_lower or "channel" in name_lower:
        return "web"
    
    # 默认值
    type_defaults = {
        "string": "测试值",
        "integer": 1,
        "number": 1.0,
        "boolean": True,
        "array": [],
        "object": {},
    }
    return type_defaults.get(ptype, "测试值")



def _json_body_from_request_body(data: dict[str, Any], request_body: dict[str, Any]) -> dict[str, Any] | None:
    """从 requestBody 取示例 JSON：优先 content.example，其次解析 schema（含 $ref）。"""
    content = request_body.get("content")
    if not isinstance(content, dict):
        return None
    for ck in ("application/json", "application/json; charset=utf-8"):
        if ck not in content:
            continue
        media = content[ck]
        if not isinstance(media, dict):
            continue
        ex = media.get("example")
        if isinstance(ex, dict):
            return dict(ex)
        examples = media.get("examples")
        if isinstance(examples, dict) and examples:
            first = next(iter(examples.values()))
            if isinstance(first, dict):
                val = first.get("value")
                if isinstance(val, dict):
                    return dict(val)
        schema = media.get("schema")
        if isinstance(schema, dict):
            gen = _schema_to_example(data, dereference_schema(data, schema))
            if gen:
                return gen
    return None


def _requires_bearer(data: dict[str, Any], path_item: dict[str, Any], op: dict[str, Any]) -> bool:
    """该 operation 是否需要 Bearer（OpenAPI security 非空数组）。"""
    if "security" in op:
        sec = op.get("security")
        return isinstance(sec, list) and sec != []
    if "security" in path_item:
        sec = path_item.get("security")
        return isinstance(sec, list) and sec != []
    gs = data.get("security")
    return bool(gs)


def _case_use_no_auth(data: dict[str, Any], path: str, path_item: dict[str, Any], op: dict[str, Any]) -> bool:
    """是否使用匿名 session（未带登录 Token）。"""
    if path in ("/api/auth/register", "/api/auth/login"):
        return True
    return not _requires_bearer(data, path_item, op)


def _chain_list_prefix(paths: dict[str, Any], templated_path: str) -> tuple[str, str] | None:
    """若路径形如 .../xxx/{param}/... 且仅含一段 {param}，返回 (列表 GET 前缀, 参数名)。"""
    if templated_path.count("{") != 1 or templated_path.count("}") != 1:
        return None
    i = templated_path.index("{")
    j = templated_path.index("}")
    param = templated_path[i + 1 : j]
    if not param or "{" in templated_path[j + 1 :]:
        return None
    prefix = templated_path[:i].rstrip("/") or "/"
    if prefix != "/" and "/" not in prefix.lstrip("/"):
        pass
    pi = paths.get(prefix)
    if not isinstance(pi, dict):
        return None
    if "get" not in pi:
        return None
    return prefix, param


def _build_list_chain_scenario(
    data: dict[str, Any],
    paths: dict[str, Any],
    path: str,
    method_upper: str,
    path_item: dict[str, Any],
    op: dict[str, Any],
    expect_status: int,
    request_body: Any,
) -> dict[str, Any] | None:
    """对「单路径参数 + 存在同前缀 GET 列表」生成两步场景：列表 capture 0.id → 带占位符的请求。"""
    hit = _chain_list_prefix(paths, path)
    if not hit:
        return None
    prefix, param_name = hit
    path_item_p = paths[prefix]
    get_op = path_item_p.get("get")
    if not isinstance(get_op, dict):
        return None
    list_no_auth = not _requires_bearer(data, path_item_p, get_op)
    jb2: dict[str, Any] | None = None
    if isinstance(request_body, dict):
        jb2 = _json_body_from_request_body(data, request_body)
    step1: dict[str, Any] = {
        "method": "GET",
        "path": prefix,
        "expect_status": 200,
        "capture": {param_name: "0.id"},
    }
    if list_no_auth:
        step1["no_auth"] = True
    step2: dict[str, Any] = {
        "method": method_upper,
        "path": path,
        "expect_status": expect_status,
    }
    if jb2 is not None and method_upper in ("POST", "PUT", "PATCH"):
        step2["json_body"] = jb2
    name = f"链式-{method_upper}-{path}"
    return {"name": name, "steps": [step1, step2]}


def _extract_expect_status(responses: dict[str, Any]) -> int:
    """从 responses 中提取期望状态码，优先 201 > 200 > 202 > 默认 200。"""
    if not isinstance(responses, dict):
        return 200
    # 按优先级查找
    for code in ["201", "200", "202", "204"]:
        if code in responses:
            return int(code)
    # 如果只有其他状态码，取第一个数字状态码
    for code, val in responses.items():
        try:
            return int(code)
        except (ValueError, TypeError):
            continue
    return 200


def load_openapi(source: str) -> dict[str, Any]:
    """从本地文件路径或 HTTP URL 加载 OpenAPI（JSON；本地 .yaml/.yml 在已安装 PyYAML 时也可用）。"""
    # 判断是否为 HTTP URL
    if source.startswith("http://") or source.startswith("https://"):
        try:
            req = urllib.request.Request(source, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as e:
            print(f" HTTP 请求失败: {e.code} {e.reason}", file=sys.stderr)
            sys.exit(1)
        except urllib.error.URLError as e:
            print(f" URL 请求失败: {e.reason}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f" 请求 OpenAPI 文档失败: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # 本地文件
        p = Path(source)
        if not p.exists():
            print(f" 文件不存在: {source}", file=sys.stderr)
            sys.exit(1)
        if not p.is_file():
            print(f" 不是文件: {source}", file=sys.stderr)
            sys.exit(1)
        try:
            raw = p.read_bytes()
        except PermissionError:
            print(f" 无权限读取: {source}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f" 读取文件失败: {e}", file=sys.stderr)
            sys.exit(1)

    text = raw.decode("utf-8", errors="replace")
    p = Path(source) if not (source.startswith("http://") or source.startswith("https://")) else None
    suffix = (p.suffix.lower() if p else "")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        if suffix in (".yaml", ".yml") and yaml is not None:
            try:
                data = yaml.safe_load(text)
            except yaml.YAMLError as e:  # type: ignore[union-attr]
                print(f" YAML 解析失败: {e}", file=sys.stderr)
                sys.exit(1)
        else:
            print(f" JSON 解析失败（若为 YAML 请安装 PyYAML 并使用 .yaml/.yml 扩展名）", file=sys.stderr)
            sys.exit(1)

    if not isinstance(data, dict):
        print(" OpenAPI 文档根须为 JSON/YAML 对象", file=sys.stderr)
        sys.exit(1)

    return data


def extract_openapi_base_url(data: dict[str, Any]) -> str | None:
    """从 OpenAPI 3 servers 或 Swagger 2 host/basePath 推断 base_url（不含末尾 /）。"""
    servers = data.get("servers")
    if isinstance(servers, list) and servers:
        first = servers[0]
        if isinstance(first, dict):
            url = first.get("url")
            if isinstance(url, str) and url.strip():
                u = url.strip().rstrip("/")
                if u.startswith("http://") or u.startswith("https://"):
                    return u
    if data.get("swagger"):
        host = data.get("host")
        if isinstance(host, str) and host.strip():
            schemes = data.get("schemes")
            scheme = "https" if isinstance(schemes, list) and schemes and schemes[0] == "https" else "http"
            if isinstance(schemes, list) and schemes and isinstance(schemes[0], str):
                scheme = schemes[0]
            bp = data.get("basePath") or ""
            if not isinstance(bp, str):
                bp = ""
            return f"{scheme}://{host.strip()}{bp}".rstrip("/")
    return None


def _path_param_example_value(param: dict[str, Any]) -> str:
    """根据 parameter（path）生成用于 URL 的示例片段。"""
    if "example" in param:
        v = param["example"]
    else:
        schema = param.get("schema")
        if not isinstance(schema, dict) and param.get("type"):
            schema = {"type": param.get("type")}
        if isinstance(schema, dict):
            if "example" in schema:
                v = schema["example"]
            elif "default" in schema:
                v = schema["default"]
            else:
                t = schema.get("type", "string")
                if t == "integer":
                    v = 1
                elif t == "number":
                    v = 1.0
                elif t == "boolean":
                    v = True
                elif t == "array":
                    v = []
                elif t == "object":
                    v = {}
                else:
                    v = "example"
        else:
            v = "example"
    if isinstance(v, bool):
        return "true" if v else "false"
    if v is None:
        return "null"
    s = str(v)
    return quote(s, safe="")


def resolve_openapi_path(path: str, parameters: list[Any]) -> str:
    """将 /items/{id} 中的 path 参数替换为示例值（来自 example/default/schema 类型）。
    
    增强：当参数名与路径占位符不匹配时（如路径用 {product_id} 但参数名是 id），
    按位置顺序填充剩余的 {xxx} 占位符。
    """
    if not parameters:
        return path
    out = path
    # Step 1: 按名字匹配替换
    for param in parameters:
        if not isinstance(param, dict):
            continue
        if (param.get("in") or "").lower() != "path":
            continue
        name = param.get("name")
        if not isinstance(name, str) or not name:
            continue
        token = "{" + name + "}"
        if token not in out:
            continue
        out = out.replace(token, _path_param_example_value(param), 1)
    # Step 2: 按位置顺序填充剩余的 {xxx} 占位符（处理参数名不匹配的情况）
    remaining_params = [p for p in parameters if isinstance(p, dict) and (p.get("in") or "").lower() == "path"]
    for param in remaining_params:
        # 找第一个未被填充的 {xxx}
        import re as _re
        m = _re.search(r'\{[a-zA-Z_]\w*\}', out)
        if not m:
            break
        out = out[:m.start()] + _path_param_example_value(param) + out[m.end():]
    # Step 3: 兜底 - 如果还有未填充的 {xxx} 且没有任何 path 参数定义，用 1 填充
    if not remaining_params:
        import re as _re2
        out = _re2.sub(r'\{[a-zA-Z_]\w*\}', '1', out)
    return out


def openapi_to_spec(data: dict[str, Any], base_url: str = "http://your-server:port") -> str:
    """将 OpenAPI 数据转换为 spec markdown 内容（$ref 请求体、security/no_auth、列表→详情链式场景）。"""
    paths = data.get("paths")
    if not paths:
        print(" OpenAPI 文档中缺少 'paths' 字段", file=sys.stderr)
        sys.exit(1)

    if not isinstance(paths, dict):
        print(" 'paths' 必须是映射对象", file=sys.stderr)
        sys.exit(1)

    valid_methods = {"get", "post", "put", "delete", "patch"}
    cases: list[dict[str, Any]] = []
    scenarios: list[dict[str, Any]] = []

    any_bearer = False
    for _p, _pi in paths.items():
        if not isinstance(_pi, dict):
            continue
        for _m, _op in _pi.items():
            if _m.lower() in valid_methods and isinstance(_op, dict) and _requires_bearer(data, _pi, _op):
                any_bearer = True
                break
        if any_bearer:
            break

    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        path_level = path_item.get("parameters") or []
        if not isinstance(path_level, list):
            path_level = []
        for method, op in path_item.items():
            if method.lower() not in valid_methods:
                continue
            if not isinstance(op, dict):
                continue

            method_upper = method.upper()
            expect_status = _extract_expect_status(op.get("responses", {}))
            request_body = op.get("requestBody")

            chain = _build_list_chain_scenario(
                data,
                paths,
                path,
                method_upper,
                path_item,
                op,
                expect_status,
                request_body if isinstance(request_body, dict) else None,
            )
            if chain is not None:
                scenarios.append(chain)
                continue

            cid = f"TC-{method_upper}-{path}"
            op_level = op.get("parameters") or []
            if not isinstance(op_level, list):
                op_level = []
            merged_params = path_level + op_level
            resolved_path = resolve_openapi_path(path, merged_params)

            case: dict[str, Any] = {
                "id": cid,
                "method": method_upper,
                "path": resolved_path,
                "expect_status": expect_status,
            }
            if isinstance(request_body, dict):
                jb = _json_body_from_request_body(data, request_body)
                if jb:
                    # 登录接口：用环境变量引用代替 example 值
                    login_patterns = ["/login", "/auth/login", "/auth/signin", "/signin", "/token"]
                    is_login = any(path.endswith(lp) or path.endswith(lp + "/") for lp in login_patterns)
                    if is_login and method_upper == "POST":
                        for key in list(jb.keys()):
                            if "user" in key.lower() or "name" in key.lower():
                                jb[key] = "__ENV__:TEST_USERNAME"
                            elif "pass" in key.lower() or "pwd" in key.lower():
                                jb[key] = "__ENV__:TEST_PASSWORD"
                    case["json_body"] = jb
            if _case_use_no_auth(data, path, path_item, op):
                case["no_auth"] = True
            cases.append(case)

    if yaml is None:
        print(" OpenAPI 导入需要 PyYAML（pip install PyYAML）", file=sys.stderr)
        sys.exit(1)

    spec_data: dict[str, Any] = {
        "kind": "api_pytest",
        "base_url": base_url,
        "cases": cases,
    }
    if scenarios:
        spec_data["scenarios"] = scenarios
    if any_bearer:
        spec_data["auth"] = {
            "type": "bearer_login",
            "login_path": "/api/auth/login",
            "username_field": "username",
            "password_field": "password",
            "username_env": "TEST_USERNAME",
            "password_env": "TEST_PASSWORD",
        }
    frontmatter = "---\n" + yaml.dump(spec_data, allow_unicode=True, default_flow_style=False).rstrip() + "\n---"

    body = "\n# OpenAPI 导入 - 自动生成\n"
    return frontmatter + body


def render_data_factory(meta: dict[str, Any], body: str) -> str:
    """生成 MySQL 造数脚本。"""
    db = meta.get("database") or {}
    host = db.get("host", "localhost")
    port = db.get("port", 3306)
    dbname = db.get("name", "test_db")
    user = db.get("user", "root")
    password = db.get("password", "")
    tables = meta.get("tables") or []
    csv_export = meta.get("csv_export") or []
    if not tables:
        raise ValueError("tables 不能为空")

    # 安全检查：拒绝生产库
    prod_keywords = ["prod", "production", "live", "real"]
    for kw in prod_keywords:
        if kw in dbname.lower():
            raise ValueError(f"拒绝向生产库写入数据（数据库名包含 '{kw}'）")

    lines = [
        "# Auto-generated by spec runner — 测试数据造数脚本",
        "# 用法: python this_script.py",
        "",
        "import os",
        "import sys",
        "import random",
        "import string",
        "from datetime import datetime, timedelta",
    ]
    if csv_export:
        lines.append("import csv")
    lines.extend([
        "",
        "try:",
        "    import pymysql",
        "except ImportError:",
        "    print(' 缺少 pymysql，请安装: pip install pymysql')",
        "    sys.exit(1)",
        "",
        f"DB_CONFIG = {{",
        f"    'host': os.environ.get('DB_HOST', {esc(host)}),",
        f"    'port': int(os.environ.get('DB_PORT', {port})),",
        f"    'user': os.environ.get('DB_USER', {esc(user)}),",
        f"    'password': os.environ.get('DB_PASSWORD', {esc(password)}),",
        f"    'database': os.environ.get('DB_NAME', {esc(dbname)}),",
        f"    'charset': 'utf8mb4',",
        f"}}",
        "",
        "def connect():",
        "    return pymysql.connect(**DB_CONFIG)",
        "",
        "# ── 字段生成策略 ──",
        "",
        "def _gen_value(strategy: str, i: int, refs: dict) -> object:",
        "    \"\"\"根据策略字符串生成字段值。\"\"\"",
        "    if strategy.startswith('ref('):",
        "        # ref('users.id') → 从 refs 随机取一个 ID",
        "        key = strategy[4:-1].strip('\"').strip(\"'\")",
        "        # 模板写 ref('users.id')，refs 存的是 users.ids，自动补 s",
        "        parts = key.rsplit('.', 1)",
        "        lookup_key = parts[0] + '.ids' if len(parts) == 2 else key",
        "        vals = refs.get(lookup_key, [0])",
        "        return random.choice(vals) if isinstance(vals, list) else vals",
        "    if strategy.startswith('random_choice('):",
        "        inner = strategy[14:-1]",
        "        choices = [c.strip().strip('\"').strip(\"'\") for c in inner.split(',')]",
        "        return random.choice(choices)",
        "    if strategy.startswith('random_float('):",
        "        inner = strategy.split('(')[1].rstrip(')')",
        "        parts = [float(x.strip()) for x in inner.split(',')]",
        "        return round(random.uniform(parts[0], parts[1]), 2) if len(parts) == 2 else 0.0",
        "    if strategy.startswith('random_int('):",
        "        inner = strategy.split('(')[1].rstrip(')')",
        "        parts = [int(x.strip()) for x in inner.split(',')]",
        "        return random.randint(parts[0], parts[1]) if len(parts) == 2 else 0",
        "    if strategy.startswith('random_date('):",
        "        inner = strategy.split('(')[1].rstrip(')')",
        "        parts = [x.strip().strip('\"') for x in inner.split(',')]",
        "        if len(parts) == 2:",
        "            start = datetime.strptime(parts[0], '%Y-%m-%d')",
        "            end = datetime.strptime(parts[1], '%Y-%m-%d')",
        "            delta = (end - start).days",
        "            return (start + timedelta(days=random.randint(0, delta))).strftime('%Y-%m-%d %H:%M:%S')",
        "        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')",
        "    if strategy == 'auto_increment':",
        "        return i + 1",
        "    if strategy == 'uuid':",
        "        import uuid",
        "        return str(uuid.uuid4())",
        "    if strategy == 'now':",
        "        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')",
        "    if strategy.startswith('hash_password('):",
        "        inner = strategy[14:-1].strip().strip('\"').strip(\"'\")",
        "        try:",
        "            from werkzeug.security import generate_password_hash",
        "        except ImportError:",
        "            print(' 缺少 werkzeug，请安装: pip install werkzeug')",
        "            sys.exit(1)",
        "        return generate_password_hash(inner, method='scrypt')",
        "    # 包含 {i} 或 {uuid} 的模板字符串",
        "    if '{i}' in strategy:",
        "        return strategy.replace('{i}', str(i).zfill(3))",
        "    if '{uuid}' in strategy:",
        "        import uuid",
        "        return strategy.replace('{uuid}', str(uuid.uuid4())[:8])",
        "    # 纯字符串",
        "    return strategy",
        "",
    ])

    # 为每个表生成插入函数
    _ident = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

    for ti, table in enumerate(tables):
        tname = table.get("name", f"table_{ti}")
        if not isinstance(tname, str) or not _ident.match(tname):
            raise ValueError(f"表名须为合法 MySQL 标识符（字母/数字/下划线）：{tname!r}")
        count = table.get("count", 10)
        fields = table.get("fields") or {}
        special_rows = table.get("special_rows") or []

        field_names = list(fields.keys())
        if not field_names:
            raise ValueError(f"表 {tname!r} 的 fields 不能为空")
        for fname in field_names:
            if not isinstance(fname, str) or not _ident.match(fname):
                raise ValueError(f"表 {tname} 含非法字段名：{fname!r}")
        fn = f"insert_{tname}"

        lines.append(f"# ── {tname} ({count} 条) ──")
        lines.append(f"")
        lines.append(f"def {fn}(conn, refs: dict) -> int:")
        lines.append(f'    """向 {tname} 插入 {count} 条数据。返回实际插入数。"""')
        lines.append(f"    cursor = conn.cursor()")
        lines.append(f"    inserted = 0")
        placeholders = ", ".join(["%s"] * len(field_names))
        cols = ", ".join(field_names)
        lines.append(f"    try:")
        lines.append(f"        sql = f\"INSERT INTO `{tname}` ({cols}) VALUES ({placeholders})\"")
        lines.append(f"        for _i in range({count}):")

        # 构建值列表
        val_exprs = []
        for fname, fstrat in fields.items():
            val_exprs.append(f"            _gen_value({esc(str(fstrat))}, _i, refs)")

        lines.append(f"            values = (")
        for ve in val_exprs:
            lines.append(ve + ",")
        lines.append(f"            )")
        lines.append(f"            cursor.execute(sql, values)")
        lines.append(f"            inserted += 1")

        # 特殊行
        if special_rows:
            lines.append(f"        # 特殊行（边界值/异常数据）")
            for si, srow in enumerate(special_rows):
                if not isinstance(srow, dict):
                    continue
                svals = []
                for fname in field_names:
                    sval = srow.get(fname)
                    if sval is None:
                        svals.append("                None,")
                    elif isinstance(sval, str):
                        svals.append(f"                {esc(sval)},")
                    else:
                        svals.append(f"                {json.dumps(sval)},")
                lines.append(f"            cursor.execute(sql, (")
                for sv in svals:
                    lines.append(sv)
                lines.append(f"            ))")
                lines.append(f"            inserted += 1")

        lines.append(f"        conn.commit()")
        lines.append(f"        if inserted > 0:")
        lines.append(f"            refs[{esc(tname + '.ids')}] = list(range(cursor.lastrowid - inserted + 1, cursor.lastrowid + 1))")
        lines.append(f"        cursor.close()")
        lines.append(f"        return inserted")
        lines.append(f"    except Exception as e:")
        lines.append(f"        conn.rollback()")
        lines.append(f"        raise")
        lines.append(f"")

    # 生成 main 函数
    lines.extend([
        "# ── 主入口 ──",
        "",
        "def main():",
        "    import sys",
        "    import json",
        "    from pathlib import Path",
        "    reset = '--reset' in sys.argv",
        "    cleanup = '--cleanup' in sys.argv",
        "    refs_file = Path(__file__).resolve().parent / 'data_refs.json'",
        "",
        "    # ── Cleanup 模式：读取 refs 精确删除 ──",
        "    if cleanup:",
        "        if not refs_file.is_file():",
        "            print(' 无 refs 文件，跳过清理')",
        "            return",
        "        refs = json.loads(refs_file.read_text(encoding='utf-8'))",
        "        print(f' 清理数据（{len(refs)} 个表）')",
        "        conn = connect()",
        "        try:",
        "            cur = conn.cursor()",
        "            cur.execute('SET FOREIGN_KEY_CHECKS=0')",
        "            for tname, ids in sorted(refs.items(), reverse=True):",
        "                if not isinstance(ids, list) or not ids:",
        "                    continue",
        "                placeholders = ','.join(['%s'] * len(ids))",
        "                sql = f'DELETE FROM `{tname}` WHERE id IN ({placeholders})'",
        "                cur.execute(sql, ids)",
        "                print(f'   ✓ {tname}: 删除 {cur.rowcount} 条')",
        "            cur.execute('SET FOREIGN_KEY_CHECKS=1')",
        "            conn.commit()",
        "            refs_file.unlink()",
        "            print(' 清理完成')",
        "        except Exception as e:",
        "            print(f' 清理失败: {e}')",
        "            conn.rollback()",
        "        finally:",
        "            conn.close()",
        "        return",
        "",
        "    print(' 连接数据库: ' + DB_CONFIG['host'] + ':' + str(DB_CONFIG['port']) + '/' + DB_CONFIG['database'])",
        "    conn = connect()",
        "    print(' 连接成功')",
        "",
        "    if reset:",
        "        print(' --reset: 清空已有数据')",
        "        cur = conn.cursor()",
        "        cur.execute('SET FOREIGN_KEY_CHECKS=0')",
        "        cur.execute('TRUNCATE TABLE orders')",
        "        cur.execute('TRUNCATE TABLE users')",
        "        cur.execute('SET FOREIGN_KEY_CHECKS=1')",
        "        conn.commit()",
        "        print(' --reset: 已清空')",
        "",
        "    refs: dict = {}",
        "    total = 0",
        "    try:",
    ])

    for ti, table in enumerate(tables):
        tname = table.get("name", f"table_{ti}")
        fn = f"insert_{tname}"
        count = table.get("count", 10)
        lines.append(f"        # 插入 {tname}")
        lines.append(f"        n = {fn}(conn, refs)")
        lines.append(f"        print(f'   ✓ {tname}: ' + str(n) + ' 条')")
        lines.append(f"        total += n")
        lines.append("")

    lines.extend([
        "        print(f'\\n 全部完成，共插入 ' + str(total) + ' 条数据')",
        "",
        "        # 保存 refs 供 teardown 精确清理",
        "        refs_file = Path(__file__).resolve().parent / 'data_refs.json'",
        "        refs_file.write_text(json.dumps(refs, ensure_ascii=False, indent=2), encoding='utf-8')",
        "        print(f' refs 已保存: {refs_file}')",
    ])

    # ── CSV 导出（供 JMeter 等性能测试工具使用） ──
    if csv_export:
        for ci, exp in enumerate(csv_export):
            exp_table = exp.get("table", "")
            exp_file = exp.get("file", f"output/export_{ci}.csv")
            exp_fields = exp.get("fields", [])
            extra_columns = exp.get("extra_columns") or {}
            if not exp_table or not exp_fields:
                continue
            export_cols = list(exp_fields) + list(extra_columns.keys())
            lines.extend([
                "",
                f"        # 导出 CSV: {exp_table} -> {exp_file}",
                f"        _csv_path = Path(__file__).resolve().parent / {esc(exp_file)}",
                f"        _csv_path.parent.mkdir(parents=True, exist_ok=True)",
                f"        _cur2 = conn.cursor()",
                f"        _cols = {json.dumps(exp_fields)}",
                f"        _extra_cols = {json.dumps(extra_columns)}",
                f"        _export_cols = {json.dumps(export_cols)}",
                f"        _cur2.execute('SELECT ' + ', '.join(_cols) + ' FROM `{exp_table}` ORDER BY id')",
                f"        _rows = _cur2.fetchall()",
                f"        _cur2.close()",
                f"        with open(_csv_path, 'w', newline='', encoding='utf-8') as _f:",
                f"            _w = csv.writer(_f)",
                f"            _w.writerow(_export_cols)",
                f"            for _row in _rows:",
                f"                _extra_vals = [_extra_cols[k] for k in _extra_cols]",
                f"                _w.writerow([str(v) if v is not None else '' for v in _row] + _extra_vals)",
                f"        print('  CSV 已导出: ' + str(_csv_path) + ' (' + str(len(_rows)) + ' 行)')",
            ])

    lines.extend([
        "    except Exception as e:",
        "        print(f' 插入失败: {e}')",
        "        conn.rollback()",
        "        raise",
        "    finally:",
        "        conn.close()",
        "",
        "",
        "if __name__ == '__main__':",
        "    main()",
    ])

    if body.strip():
        lines.extend(["", "# --- spec 正文 ---", "# " + body.replace("\n", "\n# ")])
    return "\n".join(lines) + "\n"


@dataclass
class PerfEndpoint:
    name: str
    method: str
    path: str
    weight: int
    json_body: Any
    headers: dict[str, Any]
    expect_status: int | None
    max_response_ms: int | None
    save_token: bool = False
    token_json_path: str | None = None


@dataclass
class PerfDataSource:
    file: str
    variables: list[str]
    delimiter: str = ","
    recycle: bool = False
    share_mode: str = "thread"
    ignore_first_line: bool = True


@dataclass
class PerfSpec:
    engine: str
    base_url: str
    concurrent: int
    duration: int
    ramp_up: int
    endpoints: list[PerfEndpoint]
    data_source: PerfDataSource | None = None
    token_json_path: str = "$.token"


def _perf_endpoint_fn_name(ei: int, name: str) -> str:
    fn_name = (
        f"test_endpoint_{ei + 1}_"
        f"{re.sub(r'[^0-9a-zA-Z_]', '_', name.lower().encode('utf-8').decode('ascii', 'ignore')).strip('_')}"
    )
    if not fn_name.split("_")[-1]:
        fn_name = f"test_endpoint_{ei + 1}"
    return fn_name


def _append_spec_body_comment(lines: list[str], body: str) -> None:
    if body.strip():
        lines.extend(["", "# --- spec 正文 ---", "# " + body.replace("\n", "\n# ")])


def parse_perf_meta(meta: dict[str, Any]) -> PerfSpec:
    endpoints_raw = meta.get("endpoints") or []
    if not endpoints_raw:
        raise ValueError("endpoints 不能为空")
    engine = str(meta.get("engine") or "k6").strip().lower()
    if engine not in ("locust", "k6", "jmeter"):
        raise ValueError(f"不支持的 engine: {engine}（可选 locust / k6 / jmeter）")
    auth_cfg = meta.get("auth") or {}
    default_token_path = str(auth_cfg.get("token_json_path") or "$.token")
    endpoints: list[PerfEndpoint] = []
    for ei, ep in enumerate(endpoints_raw):
        endpoints.append(
            PerfEndpoint(
                name=ep.get("name") or f"endpoint_{ei + 1}",
                method=(ep.get("method") or "GET").upper(),
                path=ep.get("path", "/"),
                weight=max(1, int(ep.get("weight", 1))),
                json_body=ep.get("json_body"),
                headers=ep.get("headers") or {},
                expect_status=ep.get("expect_status"),
                max_response_ms=ep.get("max_response_ms"),
                save_token=bool(ep.get("save_token")),
                token_json_path=ep.get("token_json_path"),
            )
        )
    data_source: PerfDataSource | None = None
    ds_raw = meta.get("data_source")
    if isinstance(ds_raw, dict) and ds_raw.get("file"):
        vars_raw = ds_raw.get("variables") or []
        if not vars_raw:
            raise ValueError("data_source.variables 不能为空")
        data_source = PerfDataSource(
            file=str(ds_raw["file"]),
            variables=[str(v) for v in vars_raw],
            delimiter=str(ds_raw.get("delimiter") or ","),
            recycle=bool(ds_raw.get("recycle", False)),
            share_mode=str(ds_raw.get("share_mode") or "thread"),
            ignore_first_line=bool(ds_raw.get("ignore_first_line", True)),
        )
    return PerfSpec(
        engine=engine,
        base_url=meta.get("base_url", "http://your-server:5001"),
        concurrent=int(meta.get("concurrent", 10)),
        duration=int(meta.get("duration", 60)),
        ramp_up=int(meta.get("ramp_up", 10)),
        endpoints=endpoints,
        data_source=data_source,
        token_json_path=default_token_path,
    )


def perf_test_output_suffix(meta: dict[str, Any]) -> str:
    engine = str(meta.get("engine") or "k6").strip().lower()
    return {"locust": ".py", "k6": ".js", "jmeter": ".jmx"}.get(engine, ".py")


def output_suffix_for_kind(meta: dict[str, Any]) -> str:
    kind = str(meta.get("kind") or "").strip()
    if kind == "perf_test":
        return perf_test_output_suffix(meta)
    return ".py"


def render_perf_locust(spec: PerfSpec, body: str) -> str:
    """生成 Locust 性能测试脚本。"""
    lines = [
        "# Auto-generated by spec runner — Locust 性能测试脚本",
        "#",
        "# ⚠️ 能力边界（2026-07）：",
        "#   - 单 HttpUser 类，所有虚拟用户共享 cookies/连接池",
        "#   - 不支持 auth.login / Bearer token 链 / data_source CSV 多账号",
        "#   - 需要登录或多用户时，请改用 templates/perf_test_k6.md 或 templates/jmeter_test.md",
        "#",
        "# 用法: locust -f this_file.py --host <base_url>",
        "# 或:   locust -f this_file.py --headless -u <users> -r <rate> -t <duration>",
        "",
        "import os",
        "import random",
        "from locust import HttpUser, task, between",
        "",
        f"BASE_URL = os.environ.get('TEST_BASE_URL', {esc(spec.base_url)})",
        f"CONCURRENT_USERS = {spec.concurrent}",
        f"DURATION_SEC = {spec.duration}",
        f"RAMP_UP_SEC = {spec.ramp_up}",
        "",
        "class APITester(HttpUser):",
        "    wait_time = between(1, 3)  # 每次请求间隔 1-3 秒",
        "    host = BASE_URL",
        "",
    ]

    for ei, ep in enumerate(spec.endpoints):
        fn_name = _perf_endpoint_fn_name(ei, ep.name)
        lines.append(f"    @task({ep.weight})")
        lines.append(f"    def {fn_name}(self):")
        lines.append(f'        """{ep.name}: {ep.method} {ep.path}"""')

        hdr_str = ""
        if ep.headers:
            hdr_json = json.dumps(ep.headers, ensure_ascii=False)
            lines.append(f"        _hdrs = {hdr_json}")
            hdr_str = ", headers=_hdrs"

        if ep.method == "GET":
            lines.append(
                f"        with self.client.get({esc(ep.path)}{hdr_str}, name={esc(ep.name)}, catch_response=True) as resp:"
            )
        elif ep.method == "POST":
            body_str = f", json={json.dumps(ep.json_body, ensure_ascii=False)}" if ep.json_body else ""
            lines.append(
                f"        with self.client.post({esc(ep.path)}{body_str}{hdr_str}, name={esc(ep.name)}, catch_response=True) as resp:"
            )
        elif ep.method == "PUT":
            body_str = f", json={json.dumps(ep.json_body, ensure_ascii=False)}" if ep.json_body else ""
            lines.append(
                f"        with self.client.put({esc(ep.path)}{body_str}{hdr_str}, name={esc(ep.name)}, catch_response=True) as resp:"
            )
        elif ep.method == "DELETE":
            lines.append(
                f"        with self.client.delete({esc(ep.path)}{hdr_str}, name={esc(ep.name)}, catch_response=True) as resp:"
            )
        else:
            lines.append(f"        pass  # 不支持的方法: {ep.method}")

        if ep.expect_status:
            lines.append(
                f"            assert resp.status_code == {ep.expect_status}, f'期望 {ep.expect_status}，实际 {{resp.status_code}}'"
            )
        if ep.max_response_ms:
            lines.append(
                f"            assert resp.elapsed.total_seconds() * 1000 <= {ep.max_response_ms}, "
                f"f'响应超时: {{resp.elapsed.total_seconds() * 1000:.0f}}ms > {ep.max_response_ms}ms'"
            )
        lines.append("")

    _append_spec_body_comment(lines, body)
    return "\n".join(lines) + "\n"


def _k6_endpoint_js_obj(ep: PerfEndpoint) -> str:
    parts = [
        f"name: {esc(ep.name)}",
        f"method: {esc(ep.method)}",
        f"path: {esc(ep.path)}",
        f"weight: {ep.weight}",
    ]
    if ep.headers:
        parts.append(f"headers: {json.dumps(ep.headers, ensure_ascii=False)}")
    if ep.json_body is not None:
        parts.append(f"bodyTemplate: {esc(json.dumps(ep.json_body, ensure_ascii=False))}")
    if ep.expect_status is not None:
        parts.append(f"expect_status: {ep.expect_status}")
    if ep.max_response_ms is not None:
        parts.append(f"max_response_ms: {ep.max_response_ms}")
    return "{ " + ", ".join(parts) + " }"


def _render_perf_k6_login_bearer(
    spec: PerfSpec,
    meta: dict[str, Any],
    body: str,
    login_eps: list[PerfEndpoint],
    biz_eps: list[PerfEndpoint],
) -> str:
    """k6：环境变量单账号登录 + Bearer token 业务压测。"""
    login_ep = login_eps[0]
    token_path = login_ep.token_json_path or spec.token_json_path or "$.token"
    json_path_key = token_path.replace("$.", "") if token_path.startswith("$.") else token_path
    max_ms_values = [ep.max_response_ms for ep in biz_eps if ep.max_response_ms]
    threshold_ms = max(max_ms_values) if max_ms_values else 1000
    endpoint_objs = ",\n  ".join(_k6_endpoint_js_obj(ep) for ep in biz_eps)
    login_body = json.dumps(login_ep.json_body, ensure_ascii=False) if login_ep.json_body else "{}"
    smoke = bool(meta.get("smoke", False))

    lines = [
        "// Auto-generated — k6 登录 + Bearer 业务压测",
        "import http from 'k6/http';",
        "import { check, sleep } from 'k6';",
        "",
        f"const BASE_URL = __ENV.BASE_URL || __ENV.TEST_BASE_URL || {esc(spec.base_url)};",
        "const USERNAME = __ENV.TEST_USERNAME || 'admin';",
        "const PASSWORD = __ENV.TEST_PASSWORD || '123456';",
        f"const TOKEN_JSON_PATH = {esc(json_path_key)};",
        "",
        "const ENDPOINTS = [",
        f"  {endpoint_objs},",
        "];",
        "",
        "export const options = {",
    ]
    if smoke:
        lines.extend(["  vus: 1,", "  duration: '30s',"])
    else:
        lines.extend([
            "  stages: [",
            f"    {{ duration: '{spec.ramp_up}s', target: {spec.concurrent} }},",
            f"    {{ duration: '{spec.duration}s', target: {spec.concurrent} }},",
            "  ],",
        ])
    lines.extend([
        "  thresholds: {",
        f"    http_req_duration: ['p(95)<{threshold_ms}'],",
        "    http_req_failed: ['rate<0.01'],",
        "  },",
        "};",
        "",
        "const vuTokens = {};",
        "",
        "function login() {",
        f"  let bodyStr = {esc(login_body)};",
        "  bodyStr = bodyStr.replace(/\\$\\{username\\}/g, USERNAME).replace(/\\$\\{password\\}/g, PASSWORD);",
        f"  const res = http.post(`${{BASE_URL}}{login_ep.path}`, bodyStr, {{",
        "    headers: { 'Content-Type': 'application/json' },",
        f"    tags: {{ name: {esc(login_ep.name)} }},",
        "  });",
        "  check(res, { 'login status': (r) => r.status === 200 });",
        "  try {",
        "    const j = res.json();",
        "    const parts = TOKEN_JSON_PATH.split('.');",
        "    let cur = j;",
        "    for (const p of parts) { cur = cur[p]; }",
        "    return cur;",
        "  } catch (e) { return null; }",
        "}",
        "",
        "export default function () {",
        "  if (!vuTokens[__VU]) vuTokens[__VU] = login();",
        "  const token = vuTokens[__VU];",
        "  const ep = ENDPOINTS[Math.floor(Math.random() * ENDPOINTS.length)];",
        "  const url = `${BASE_URL}${ep.path}`;",
        "  const headers = {};",
        "  for (const [k, v] of Object.entries(ep.headers || {})) {",
        "    headers[k] = String(v).replace(/\\$\\{token\\}/g, token || '');",
        "  }",
        "  if (ep.bodyTemplate && !headers['Content-Type']) headers['Content-Type'] = 'application/json';",
        "  const params = Object.keys(headers).length ? { headers } : {};",
        "  let body = ep.bodyTemplate || null;",
        "  if (body) {",
        "    body = body.replace(/\\{\\{timestamp\\}\\}/g, String(Date.now()));",
        "  }",
        "  let res;",
        "  if (ep.method === 'GET') res = http.get(url, params);",
        "  else if (ep.method === 'POST') res = http.post(url, body, params);",
        "  else if (ep.method === 'PUT') res = http.put(url, body, params);",
        "  else res = http.del(url, null, params);",
        "  if (ep.expect_status !== undefined) {",
        "    check(res, { [`${ep.name} status`]: (r) => r.status === ep.expect_status });",
        "  }",
        "  sleep(Math.random() * 2 + 1);",
        "}",
    ])
    if body.strip():
        lines.extend(["", "// --- spec ---"])
        for line in body.splitlines():
            lines.append("// " + line)
    return "\n".join(lines) + "\n"


def _render_perf_k6_csv_multiuser(spec: PerfSpec, meta: dict[str, Any], body: str) -> str:
    """k6：CSV 多用户 + 每 VU 登录 + Bearer 业务压测。"""
    ds = spec.data_source
    assert ds is not None
    login_eps = [ep for ep in spec.endpoints if ep.save_token]
    biz_eps = [ep for ep in spec.endpoints if not ep.save_token] or spec.endpoints
    login_ep = login_eps[0] if login_eps else None
    token_path = (login_ep.token_json_path if login_ep else None) or spec.token_json_path or "$.token"
    json_path_key = token_path.replace("$.", "") if token_path.startswith("$.") else token_path
    vars_js = json.dumps(ds.variables)
    max_ms_values = [ep.max_response_ms for ep in biz_eps if ep.max_response_ms]
    threshold_ms = max(max_ms_values) if max_ms_values else 1000
    endpoint_objs = ",\n  ".join(_k6_endpoint_js_obj(ep) for ep in biz_eps)
    login_path_str = login_ep.path if login_ep else "/api/auth/login"
    login_body_tpl = (
        esc(json.dumps(login_ep.json_body, ensure_ascii=False))
        if login_ep and login_ep.json_body
        else '{"username":"${username}","password":"${password}"}'
    )
    smoke = bool(meta.get("smoke", False))

    lines = [
        "// Auto-generated — k6 CSV 多用户压测",
        "import http from 'k6/http';",
        "import { check, sleep } from 'k6';",
        "import { SharedArray } from 'k6/data';",
        "",
        f"const BASE_URL = __ENV.BASE_URL || __ENV.TEST_BASE_URL || {esc(spec.base_url)};",
        f"const CSV_FILE = {esc(ds.file)};",
        f"const CSV_VARS = {vars_js};",
        f"const TOKEN_JSON_PATH = {esc(json_path_key)};",
        "",
        "const USERS = new SharedArray('users', function () {",
        "  const raw = open(CSV_FILE);",
        "  const lines = raw.trim().split('\\n');",
        "  if (lines.length < 2) return [];",
        "  const headers = lines[0].split(',');",
        "  return lines.slice(1).map((line) => {",
        "    const cols = line.split(',');",
        "    const row = {};",
        "    headers.forEach((h, i) => { row[h.trim()] = (cols[i] || '').trim(); });",
        "    return row;",
        "  });",
        "});",
        "",
        "const ENDPOINTS = [",
        f"  {endpoint_objs},",
        "];",
        "",
        "export const options = {",
    ]
    if smoke:
        lines.extend(["  vus: 1,", "  duration: '30s',"])
    else:
        lines.extend([
            "  stages: [",
            f"    {{ duration: '{spec.ramp_up}s', target: {spec.concurrent} }},",
            f"    {{ duration: '{spec.duration}s', target: {spec.concurrent} }},",
            "  ],",
        ])
    lines.extend([
        "  thresholds: {",
        f"    http_req_duration: ['p(95)<{threshold_ms}'],",
        "    http_req_failed: ['rate<0.01'],",
        "  },",
        "};",
        "",
        "const vuTokens = {};",
        "",
        "function pickUser() {",
        "  if (!USERS.length) throw new Error('CSV 无数据行');",
        "  return USERS[(__VU - 1) % USERS.length];",
        "}",
        "",
        "function login(user) {",
        f"  let bodyStr = {login_body_tpl};",
        "  bodyStr = bodyStr.replace(/\\$\\{username\\}/g, user.username || '')",
        "    .replace(/\\$\\{password\\}/g, user.password || '');",
        f"  const res = http.post(`${{BASE_URL}}{login_path_str}`, bodyStr, {{",
        "    headers: { 'Content-Type': 'application/json' }, tags: { name: 'login' },",
        "  });",
        "  check(res, { 'login 200': (r) => r.status === 200 });",
        "  try {",
        "    const j = res.json();",
        "    const parts = TOKEN_JSON_PATH.split('.');",
        "    let cur = j;",
        "    for (const p of parts) { cur = cur[p]; }",
        "    return cur;",
        "  } catch (e) { return null; }",
        "}",
        "",
        "export default function () {",
        "  const user = pickUser();",
        "  if (!vuTokens[__VU]) vuTokens[__VU] = login(user);",
        "  const token = vuTokens[__VU];",
        "  const ep = ENDPOINTS[Math.floor(Math.random() * ENDPOINTS.length)];",
        "  const url = `${BASE_URL}${ep.path}`;",
        "  const headers = {};",
        "  for (const [k, v] of Object.entries(ep.headers || {})) {",
        "    headers[k] = String(v).replace(/\\$\\{token\\}/g, token || '');",
        "  }",
        "  const params = Object.keys(headers).length ? { headers } : {};",
        "  let body = ep.bodyTemplate || null;",
        "  let res;",
        "  if (ep.method === 'GET') res = http.get(url, params);",
        "  else if (ep.method === 'POST') res = http.post(url, body, params);",
        "  else res = http.del(url, null, params);",
        "  if (ep.expect_status !== undefined) check(res, { status: (r) => r.status === ep.expect_status });",
        "  sleep(Math.random() * 2 + 1);",
        "}",
    ])
    if body.strip():
        lines.extend(["", "// --- spec ---"])
        for line in body.splitlines():
            lines.append("// " + line)
    return "\n".join(lines) + "\n"


def render_perf_k6(spec: PerfSpec, meta: dict[str, Any], body: str) -> str:
    """生成 k6 性能测试脚本（支持 Token、CSV 多用户、登录 token 关联）。"""
    if spec.data_source:
        return _render_perf_k6_csv_multiuser(spec, meta, body)
    login_eps = [ep for ep in spec.endpoints if ep.save_token]
    biz_eps = [ep for ep in spec.endpoints if not ep.save_token]
    if login_eps and biz_eps:
        return _render_perf_k6_login_bearer(spec, meta, body, login_eps, biz_eps)
    max_ms_values = [ep.max_response_ms for ep in spec.endpoints if ep.max_response_ms]
    threshold_ms = max(max_ms_values) if max_ms_values else 1000
    endpoint_objs = ",\n  ".join(_k6_endpoint_js_obj(ep) for ep in spec.endpoints)
    expect_business = bool(meta.get("expect_business_code", False))
    smoke = bool(meta.get("smoke", False))

    lines = [
        "// Auto-generated by spec runner — k6 性能测试脚本",
        "// 用法: run_perf_from_har.ps1 -Har xxx.har -Engine k6 -Smoke",
        "// 或:   k6 run -e PERF_ACCESS_TOKEN=<token> this_file.js",
        "",
        "import http from 'k6/http';",
        "import { check, sleep } from 'k6';",
        "",
        f"const BASE_URL = __ENV.BASE_URL || __ENV.TEST_BASE_URL || {esc(spec.base_url)};",
        "const TENANT_ID = __ENV.PERF_TENANT_ID || '1';",
        f"const PROBE_PATH = __ENV.PERF_PROBE_PATH || {esc(meta.get('probe_path') or '/api/health')};",
        f"const EXPECT_BUSINESS = {'true' if expect_business else 'false'};",
        "const CHECK_FAILURES = [];",
        "",
        "function getToken() {",
        "  return __ENV.PERF_ACCESS_TOKEN || '';",
        "}",
        "",
        "const ENDPOINTS = [",
        f"  {endpoint_objs},",
        "];",
        "",
        "export const options = {",
    ]
    if smoke:
        lines.extend([
            "  vus: 1,",
            "  duration: '30s',",
        ])
    else:
        lines.extend([
            "  stages: [",
            f"    {{ duration: '{spec.ramp_up}s', target: {spec.concurrent} }},",
            f"    {{ duration: '{spec.duration}s', target: {spec.concurrent} }},",
            "  ],",
        ])
    threshold_lines = [
        "  thresholds: {",
        f"    http_req_duration: ['p(95)<{threshold_ms}'],",
        "    http_req_failed: ['rate<0.01'],",
    ]
    if expect_business:
        threshold_lines.append("    checks: ['rate>0.99'],")
    threshold_lines.extend(["  },", "};", ""])
    lines.extend(threshold_lines)
    lines.extend([
        "function resolveHeaderValue(v) {",
        "  return String(v)",
        "    .replace(/\\$\\{PERF_ACCESS_TOKEN\\}/g, getToken())",
        "    .replace(/\\$\\{PERF_TENANT_ID\\}/g, TENANT_ID);",
        "}",
        "",
        "function businessCodeOk(r) {",
        "  try {",
        "    const body = r.json();",
        "    if (!body || typeof body !== 'object') return false;",
        "    const code = body.code;",
        "    return code === 0 || code === '0';",
        "  } catch (_) {",
        "    return false;",
        "  }",
        "}",
        "",
        "function businessCodeSummary(r) {",
        "  try {",
        "    const body = r.json();",
        "    return body && typeof body === 'object' ? body.code : 'non_object';",
        "  } catch (_) {",
        "    return 'parse_error';",
        "  }",
        "}",
        "",
        "function recordCheckFailure(ep, r, reason) {",
        "  CHECK_FAILURES.push({",
        "    time: new Date().toISOString(),",
        "    endpoint: ep.name,",
        "    method: ep.method,",
        "    path: ep.path,",
        "    reason,",
        "    http_status: r.status,",
        "    business_code: businessCodeSummary(r),",
        "    body_preview: String(r.body || '').slice(0, 500),",
        "    token_prefix: getToken().slice(0, 8),",
        "  });",
        "}",
        "",
        "function buildParams(ep) {",
        "  const headers = {};",
        "  for (const [k, val] of Object.entries(ep.headers || {})) {",
        "    headers[k] = resolveHeaderValue(val);",
        "  }",
        "  if (ep.bodyTemplate && !headers['Content-Type'] && !headers['content-type']) {",
        "    headers['Content-Type'] = 'application/json';",
        "  }",
        "  if (!getToken() && headers.Authorization) {",
        "    throw new Error('缺少 PERF_ACCESS_TOKEN：请先运行 codegen/fetch_perf_token.py 或 run_perf_from_har.ps1');",
        "  }",
        "  return Object.keys(headers).length ? { headers } : {};",
        "}",
        "",
        "function buildBody(ep) {",
        "  if (!ep.bodyTemplate) return null;",
        "  const ts = Date.now();",
        "  return ep.bodyTemplate",
        "    .replace(/\\{\\{timestamp\\}\\}/g, String(ts))",
        "    .replace(/\\{\\{vu\\}\\}/g, String(__VU))",
        "    .replace(/\\{\\{iter\\}\\}/g, String(__ITER));",
        "}",
        "",
        "function pickWeighted(endpoints) {",
        "  const total = endpoints.reduce((sum, ep) => sum + ep.weight, 0);",
        "  let r = Math.random() * total;",
        "  for (const ep of endpoints) {",
        "    r -= ep.weight;",
        "    if (r <= 0) return ep;",
        "  }",
        "  return endpoints[endpoints.length - 1];",
        "}",
        "",
        "export default function () {",
        "  const ep = pickWeighted(ENDPOINTS);",
        "  const url = `${BASE_URL}${ep.path}`;",
        "  const params = buildParams(ep);",
        "  const body = buildBody(ep);",
        "  let res;",
        "  if (ep.method === 'GET') res = http.get(url, params);",
        "  else if (ep.method === 'POST') res = http.post(url, body, params);",
        "  else if (ep.method === 'PUT') res = http.put(url, body, params);",
        "  else if (ep.method === 'DELETE') res = http.del(url, null, params);",
        "  else throw new Error(`不支持的方法: ${ep.method}`);",
        "",
        "  const checks = {};",
        "  if (ep.expect_status !== undefined) {",
        "    checks[`${ep.name} status`] = (r) => r.status === ep.expect_status;",
        "  }",
        "  if (EXPECT_BUSINESS) {",
        "    checks[`${ep.name} business code`] = (r) => {",
        "      const ok = businessCodeOk(r);",
        "      if (!ok) {",
        "        recordCheckFailure(ep, r, 'business_code');",
        "        console.warn(",
        "          `[${ep.name}] business code=${businessCodeSummary(r)} status=${r.status} ` +",
        "          `token=${getToken().slice(0, 8) || 'EMPTY'}... body=${String(r.body).slice(0, 120)}`,",
        "        );",
        "      }",
        "      return ok;",
        "    };",
        "  }",
        "  if (ep.max_response_ms !== undefined) {",
        "    checks[`${ep.name} duration`] = (r) => r.timings.duration <= ep.max_response_ms;",
        "  }",
        "  if (Object.keys(checks).length) check(res, checks);",
        "  sleep(Math.random() * 2 + 1);",
        "}",
        "",
        "export function setup() {",
        "  const token = getToken();",
        "  if (!token) {",
        "    throw new Error('setup: 缺少 PERF_ACCESS_TOKEN');",
        "  }",
        "  const probe = http.get(",
        "    `${BASE_URL}${PROBE_PATH}`,",
        "    { headers: { Authorization: `Bearer ${token}`, 'tenant-id': TENANT_ID } },",
        "  );",
        "  if (!businessCodeOk(probe)) {",
        "    throw new Error(",
        "      `setup: Token 探针失败 status=${probe.status} code=${businessCodeSummary(probe)} ` +",
        "      `body=${String(probe.body).slice(0, 120)}`,",
        "    );",
        "  }",
        "  return { token_ok: true };",
        "}",
        "",
        "export function handleSummary(data) {",
        "  const out = {",
        "    stdout: JSON.stringify({",
        "      p95_ms: data.metrics.http_req_duration.values['p(95)'],",
        "      error_rate: data.metrics.http_req_failed.values.rate,",
        "      check_failures: CHECK_FAILURES.length,",
        "    }, null, 2),",
        "  };",
        "  if (CHECK_FAILURES.length) {",
        "    out['output/k6_check_failures.json'] = JSON.stringify(CHECK_FAILURES, null, 2);",
        "  }",
        "  return out;",
        "}",
    ])

    if body.strip():
        lines.extend(["", "// --- spec 正文 ---"])
        for line in body.splitlines():
            lines.append("// " + line)
    return "\n".join(lines) + "\n"


def _jmeter_string_prop(parent: ET.Element, name: str, value: str) -> ET.Element:
    el = ET.SubElement(parent, "stringProp", name=name)
    el.text = value
    return el


def _jmeter_int_prop(parent: ET.Element, name: str, value: int) -> ET.Element:
    el = ET.SubElement(parent, "intProp", name=name)
    el.text = str(value)
    return el


def _jmeter_bool_prop(parent: ET.Element, name: str, value: bool) -> ET.Element:
    el = ET.SubElement(parent, "boolProp", name=name)
    el.text = "true" if value else "false"
    return el


def _jmeter_parse_base_url(base_url: str) -> tuple[str, str, str]:
    parsed = urlparse(base_url)
    protocol = parsed.scheme or "http"
    domain = parsed.hostname or "127.0.0.1"
    if parsed.port:
        port = str(parsed.port)
    else:
        port = "443" if protocol == "https" else "80"
    return protocol, domain, port


def _jmeter_resolve_header_value(value: Any) -> str:
    """JMeter 头里直接用 __P 读 -J 参数，避免 UDV 初始化时序导致 Token 为空。"""
    text = str(value)
    text = text.replace("${PERF_ACCESS_TOKEN}", "${__P(PERF_ACCESS_TOKEN)}")
    text = text.replace("${PERF_TENANT_ID}", "${__P(PERF_TENANT_ID,1)}")
    text = text.replace("${PERF_ACCESS_TOKEN}", "${__P(PERF_ACCESS_TOKEN)}")
    text = text.replace("${PERF_TENANT_ID}", "${__P(PERF_TENANT_ID,1)}")
    return text


def _jmeter_add_header_manager(parent_ht: ET.Element, headers: dict[str, Any]) -> None:
    if not headers:
        return
    hm = ET.SubElement(
        parent_ht,
        "HeaderManager",
        {
            "guiclass": "HeaderPanel",
            "testclass": "HeaderManager",
            "testname": "HTTP Header Manager",
            "enabled": "true",
        },
    )
    coll = ET.SubElement(hm, "collectionProp", name="HeaderManager.headers")
    for key, value in headers.items():
        hp = ET.SubElement(coll, "elementProp", name="", elementType="Header")
        _jmeter_string_prop(hp, "Header.name", str(key))
        _jmeter_string_prop(hp, "Header.value", _jmeter_resolve_header_value(value))
    ET.SubElement(parent_ht, "hashTree")


def _jmeter_body_text(ep: PerfEndpoint) -> str:
    if ep.json_body is None:
        return ""
    text = json.dumps(ep.json_body, ensure_ascii=False)
    return (
        text.replace("{{timestamp}}", "${__time()}")
        .replace("{{vu}}", "${__threadNum}")
        .replace("{{iter}}", "${__iterationNum}")
    )


def _jmeter_share_mode_prop(share_mode: str) -> str:
    mapping = {
        "all_threads": "shareMode.all",
        "all": "shareMode.all",
        "thread_group": "shareMode.group",
        "group": "shareMode.group",
        "current_thread": "shareMode.thread",
        "thread": "shareMode.thread",
    }
    return mapping.get(share_mode.strip().lower(), "shareMode.group")


def _jmeter_add_csv_data_set(parent_ht: ET.Element, ds: PerfDataSource) -> None:
    csv_el = ET.SubElement(
        parent_ht,
        "CSVDataSet",
        {
            "guiclass": "TestBeanGUI",
            "testclass": "CSVDataSet",
            "testname": "CSV Data Set Config",
            "enabled": "true",
        },
    )
    _jmeter_string_prop(csv_el, "delimiter", ds.delimiter)
    _jmeter_string_prop(csv_el, "fileEncoding", "UTF-8")
    _jmeter_string_prop(csv_el, "filename", ds.file)
    _jmeter_bool_prop(csv_el, "ignoreFirstLine", ds.ignore_first_line)
    _jmeter_bool_prop(csv_el, "quotedData", False)
    _jmeter_bool_prop(csv_el, "recycle", ds.recycle)
    _jmeter_string_prop(csv_el, "shareMode", _jmeter_share_mode_prop(ds.share_mode))
    _jmeter_bool_prop(csv_el, "stopThread", False)
    _jmeter_string_prop(csv_el, "variableNames", ",".join(ds.variables))
    ET.SubElement(parent_ht, "hashTree")


def _jmeter_add_json_post_processor(
    parent_ht: ET.Element,
    *,
    var_name: str = "token",
    json_path: str = "$.token",
) -> None:
    jpp = ET.SubElement(
        parent_ht,
        "JSONPostProcessor",
        {
            "guiclass": "JSONPostProcessorGui",
            "testclass": "JSONPostProcessor",
            "testname": f"Extract {var_name}",
            "enabled": "true",
        },
    )
    _jmeter_string_prop(jpp, "JSONPostProcessor.referenceNames", var_name)
    _jmeter_string_prop(jpp, "JSONPostProcessor.jsonPathExprs", json_path)
    _jmeter_string_prop(jpp, "JSONPostProcessor.match_numbers", "0")
    ET.SubElement(parent_ht, "hashTree")


def _jmeter_add_user_defined_variables(parent_ht: ET.Element, *, include_perf_token: bool = True) -> None:
    args = ET.SubElement(
        parent_ht,
        "Arguments",
        {
            "guiclass": "ArgumentsPanel",
            "testclass": "Arguments",
            "testname": "User Defined Variables",
            "enabled": "true",
        },
    )
    coll = ET.SubElement(args, "collectionProp", name="Arguments.arguments")
    defaults: list[tuple[str, str]] = []
    if include_perf_token:
        defaults = [("PERF_ACCESS_TOKEN", ""), ("PERF_TENANT_ID", "1")]
    for name, default in defaults:
        prop = ET.SubElement(coll, "elementProp", name=name, elementType="Argument")
        _jmeter_string_prop(prop, "Argument.name", name)
        _jmeter_string_prop(prop, "Argument.value", f"${{__P({name},{default})}}")
        _jmeter_string_prop(prop, "Argument.metadata", "=")
    ET.SubElement(parent_ht, "hashTree")


def _jmeter_add_sampler(
    parent_ht: ET.Element,
    ep: PerfEndpoint,
    protocol: str,
    domain: str,
    port: str,
    *,
    expect_business: bool = False,
    extract_token: bool = False,
    token_json_path: str = "$.token",
) -> None:
    sampler = ET.SubElement(
        parent_ht,
        "HTTPSamplerProxy",
        {
            "guiclass": "HttpTestSampleGui",
            "testclass": "HTTPSamplerProxy",
            "testname": ep.name,
            "enabled": "true",
        },
    )
    args = ET.SubElement(
        sampler,
        "elementProp",
        {
            "name": "HTTPsampler.Arguments",
            "elementType": "Arguments",
            "guiclass": "HTTPArgumentsPanel",
            "testclass": "Arguments",
            "enabled": "true",
        },
    )
    coll = ET.SubElement(args, "collectionProp", name="Arguments.arguments")
    if ep.json_body is not None and ep.method in ("POST", "PUT", "PATCH"):
        body_text = _jmeter_body_text(ep)
        ap = ET.SubElement(coll, "elementProp", name="", elementType="HTTPArgument")
        _jmeter_bool_prop(ap, "HTTPArgument.always_encode", False)
        _jmeter_string_prop(ap, "Argument.value", body_text)
        _jmeter_string_prop(ap, "Argument.metadata", "=")
        _jmeter_bool_prop(sampler, "HTTPSampler.postBodyRaw", True)
    _jmeter_string_prop(sampler, "HTTPSampler.domain", domain)
    _jmeter_string_prop(sampler, "HTTPSampler.port", port)
    _jmeter_string_prop(sampler, "HTTPSampler.protocol", protocol)
    _jmeter_string_prop(sampler, "HTTPSampler.path", ep.path)
    _jmeter_string_prop(sampler, "HTTPSampler.method", ep.method)
    _jmeter_bool_prop(sampler, "HTTPSampler.follow_redirects", True)
    _jmeter_bool_prop(sampler, "HTTPSampler.use_keepalive", True)

    sampler_ht = ET.SubElement(parent_ht, "hashTree")
    _jmeter_add_header_manager(sampler_ht, ep.headers)

    if ep.expect_status is not None:
        ra = ET.SubElement(
            sampler_ht,
            "ResponseAssertion",
            {
                "guiclass": "AssertionGui",
                "testclass": "ResponseAssertion",
                "testname": "Response Assertion",
                "enabled": "true",
            },
        )
        test_strings = ET.SubElement(ra, "collectionProp", name="Asserion.test_strings")
        _jmeter_string_prop(test_strings, "0", str(ep.expect_status))
        _jmeter_string_prop(ra, "Assertion.test_field", "Assertion.response_code")
        _jmeter_bool_prop(ra, "Assertion.assume_success", False)
        _jmeter_int_prop(ra, "Assertion.test_type", 8)
        ET.SubElement(sampler_ht, "hashTree")

    if ep.max_response_ms is not None:
        da = ET.SubElement(
            sampler_ht,
            "DurationAssertion",
            {
                "guiclass": "DurationAssertionGui",
                "testclass": "DurationAssertion",
                "testname": "Duration Assertion",
                "enabled": "true",
            },
        )
        _jmeter_string_prop(da, "DurationAssertion.duration", str(ep.max_response_ms))
        ET.SubElement(sampler_ht, "hashTree")

    if expect_business:
        jpa = ET.SubElement(
            sampler_ht,
            "JSONPathAssertion",
            {
                "guiclass": "JSONPathAssertionGui",
                "testclass": "JSONPathAssertion",
                "testname": "Business code==0",
                "enabled": "true",
            },
        )
        _jmeter_string_prop(jpa, "JSON_PATH", "$.code")
        _jmeter_string_prop(jpa, "EXPECTED_VALUE", "0")
        _jmeter_bool_prop(jpa, "JSONVALIDATION", True)
        _jmeter_bool_prop(jpa, "EXPECT_NULL", False)
        _jmeter_bool_prop(jpa, "INVERT", False)
        _jmeter_bool_prop(jpa, "ISREGEX", False)
        ET.SubElement(sampler_ht, "hashTree")

    if extract_token:
        _jmeter_add_json_post_processor(sampler_ht, var_name="token", json_path=token_json_path)


def render_perf_jmeter(spec: PerfSpec, meta: dict[str, Any], body: str) -> str:
    """生成 JMeter JMX 性能测试脚本（支持 CSV 多用户 + 登录 token 关联）。"""
    expect_business = bool(meta.get("expect_business_code", False))
    protocol, domain, port = _jmeter_parse_base_url(spec.base_url)
    login_eps = [ep for ep in spec.endpoints if ep.save_token]
    biz_eps = [ep for ep in spec.endpoints if not ep.save_token]
    if not biz_eps:
        biz_eps = spec.endpoints
        login_eps = []

    root = ET.Element(
        "jmeterTestPlan",
        version="1.2",
        properties="5.0",
        jmeter="5.6.3",
    )
    ht_root = ET.SubElement(root, "hashTree")

    test_plan = ET.SubElement(
        ht_root,
        "TestPlan",
        {
            "guiclass": "TestPlanGui",
            "testclass": "TestPlan",
            "testname": "perf_test",
            "enabled": "true",
        },
    )
    _jmeter_bool_prop(test_plan, "TestPlan.functional_mode", False)
    _jmeter_bool_prop(test_plan, "TestPlan.serialize_threadgroups", False)
    ht_plan = ET.SubElement(ht_root, "hashTree")

    _jmeter_add_user_defined_variables(ht_plan, include_perf_token=spec.data_source is None)

    thread_group = ET.SubElement(
        ht_plan,
        "ThreadGroup",
        {
            "guiclass": "ThreadGroupGui",
            "testclass": "ThreadGroup",
            "testname": "Thread Group",
            "enabled": "true",
        },
    )
    _jmeter_int_prop(thread_group, "ThreadGroup.num_threads", spec.concurrent)
    _jmeter_int_prop(thread_group, "ThreadGroup.ramp_time", spec.ramp_up)
    _jmeter_bool_prop(thread_group, "ThreadGroup.scheduler", True)
    _jmeter_string_prop(thread_group, "ThreadGroup.duration", str(spec.duration))
    _jmeter_string_prop(thread_group, "ThreadGroup.delay", "0")
    loop_ctrl = ET.SubElement(
        thread_group,
        "elementProp",
        {
            "name": "ThreadGroup.main_controller",
            "elementType": "LoopController",
            "guiclass": "LoopControlPanel",
            "testclass": "LoopController",
        },
    )
    _jmeter_bool_prop(loop_ctrl, "LoopController.continue_forever", True)
    _jmeter_int_prop(loop_ctrl, "LoopController.loops", -1)

    ht_tg = ET.SubElement(ht_plan, "hashTree")

    if spec.data_source:
        _jmeter_add_csv_data_set(ht_tg, spec.data_source)

    auth_cfg = meta.get("auth") or {}
    login_each_iteration = bool(auth_cfg.get("login_each_iteration"))

    if login_eps:
        if login_each_iteration:
            login_ht = ht_tg
        else:
            ET.SubElement(
                ht_tg,
                "OnceOnlyController",
                {
                    "guiclass": "OnceOnlyControllerGui",
                    "testclass": "OnceOnlyController",
                    "testname": "Once Only - Login",
                    "enabled": "true",
                },
            )
            login_ht = ET.SubElement(ht_tg, "hashTree")
        for ep in login_eps:
            token_path = ep.token_json_path or spec.token_json_path
            _jmeter_add_sampler(
                login_ht,
                ep,
                protocol,
                domain,
                port,
                expect_business=expect_business,
                extract_token=True,
                token_json_path=token_path,
            )

    random_ctrl = ET.SubElement(
        ht_tg,
        "RandomController",
        {
            "guiclass": "RandomControllerGui",
            "testclass": "RandomController",
            "testname": "Weighted Endpoints",
            "enabled": "true",
        },
    )
    ht_random = ET.SubElement(ht_tg, "hashTree")

    expanded: list[PerfEndpoint] = []
    for ep in biz_eps:
        expanded.extend([ep] * ep.weight)

    for ep in expanded:
        _jmeter_add_sampler(ht_random, ep, protocol, domain, port, expect_business=expect_business)

    ET.indent(root, space="  ")
    xml_body = ET.tostring(root, encoding="unicode")
    comment = ""
    if body.strip():
        comment = "\n".join(f"<!-- {line} -->" for line in body.splitlines()) + "\n"
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f"{comment}"
        f"{xml_body}\n"
    )


def render_perf_test(meta: dict[str, Any], body: str) -> str:
    """按 engine 分发：locust / k6 / jmeter。"""
    spec = parse_perf_meta(meta)
    if spec.engine == "k6":
        return render_perf_k6(spec, meta, body)
    if spec.engine == "jmeter":
        return render_perf_jmeter(spec, meta, body)
    return render_perf_locust(spec, body)
def render_jmeter_script(meta: dict[str, Any], body: str) -> str:
    """生成 JMeter JMX 脚本（从 OpenAPI 或 spec 定义）。"""
    base_url = meta.get("base_url", "http://your-server:5001")
    threads = int(meta.get("threads", 10))
    duration = int(meta.get("duration", 60))
    ramp_time = int(meta.get("ramp_time", 10))
    endpoints = meta.get("endpoints") or []
    data_source = meta.get("data_source")  # CSV data for JMeter
    if not endpoints:
        raise ValueError("endpoints 不能为空")

    # 解析 base_url
    from urllib.parse import urlparse
    parsed = urlparse(base_url)
    host = parsed.hostname or "your-server"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    protocol = parsed.scheme or "http"

    # 检查是否需要登录（任何 endpoint 有 auth 标记）
    needs_auth = any(ep.get("auth") for ep in endpoints)
    login_endpoint = None
    if needs_auth:
        for ep in endpoints:
            if ep.get("auth") == "login":
                login_endpoint = ep
                break
        if not login_endpoint:
            # 默认登录端点
            login_endpoint = {
                "name": "登录",
                "method": "POST",
                "path": "/api/auth/login",
                "json_body": {"username": "${USERNAME}", "password": "${PASSWORD}"},
                "extract_token": True,
            }

    # 生成 JMX XML
    xml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<jmeterTestPlan version="1.2" properties="5.0" jmeter="5.6.3">',
        '  <hashTree>',
        '    <TestPlan guiclass="TestPlanGui" testclass="TestPlan" testname="API 压测" enabled="true">',
        '      <stringProp name="TestPlan.comments">OpenAPI 导入 — 自动生成</stringProp>',
        '      <boolProp name="TestPlan.functional_mode">false</boolProp>',
        '    </TestPlan>',
        '    <hashTree>',
        # User Defined Variables
        '      <Arguments guiclass="ArgumentsPanel" testclass="Arguments" testname="User Defined Variables" enabled="true">',
        '        <collectionProp name="Arguments.arguments">',
        '          <elementProp name="HOST" elementType="Argument">',
        '            <stringProp name="Argument.name">HOST</stringProp>',
        f'            <stringProp name="Argument.value">${{__P(HOST,{host})}}</stringProp>',
        '            <stringProp name="Argument.metadata">=</stringProp>',
        '          </elementProp>',
        '          <elementProp name="PORT" elementType="Argument">',
        '            <stringProp name="Argument.name">PORT</stringProp>',
        f'            <stringProp name="Argument.value">${{__P(PORT,{port})}}</stringProp>',
        '            <stringProp name="Argument.metadata">=</stringProp>',
        '          </elementProp>',
        '          <elementProp name="USERNAME" elementType="Argument">',
        '            <stringProp name="Argument.name">USERNAME</stringProp>',
        '            <stringProp name="Argument.value">${__P(USERNAME,admin)}</stringProp>',
        '            <stringProp name="Argument.metadata">=</stringProp>',
        '          </elementProp>',
        '          <elementProp name="PASSWORD" elementType="Argument">',
        '            <stringProp name="Argument.name">PASSWORD</stringProp>',
        '            <stringProp name="Argument.value">${__P(PASSWORD,admin123)}</stringProp>',
        '            <stringProp name="Argument.metadata">=</stringProp>',
        '          </elementProp>',
        '        </collectionProp>',
        '      </Arguments>',
        '      <hashTree/>',
        # HTTP Defaults
        '      <ConfigTestElement guiclass="HttpDefaultsGui" testclass="ConfigTestElement" testname="HTTP Request Defaults" enabled="true">',
        f'        <stringProp name="HTTPSampler.domain">${{HOST}}</stringProp>',
        f'        <stringProp name="HTTPSampler.port">${{PORT}}</stringProp>',
        f'        <stringProp name="HTTPSampler.protocol">{protocol}</stringProp>',
        '        <stringProp name="HTTPSampler.connect_timeout">5000</stringProp>',
        '        <stringProp name="HTTPSampler.response_timeout">10000</stringProp>',
        '      </ConfigTestElement>',
        '      <hashTree/>',
        # Thread Group
        '      <ThreadGroup guiclass="ThreadGroupGui" testclass="ThreadGroup" testname="压测线程组" enabled="true">',
        '        <stringProp name="ThreadGroup.on_sample_error">continue</stringProp>',
        '        <elementProp name="ThreadGroup.main_controller" elementType="LoopController" guiclass="LoopControlPanel" testclass="LoopController" testname="Loop Controller" enabled="true">',
        '          <boolProp name="LoopController.continue_forever">true</boolProp>',
        '          <intProp name="LoopController.loops">-1</intProp>',
        '        </elementProp>',
        f'        <stringProp name="ThreadGroup.num_threads">${{__P(THREADS,{threads})}}</stringProp>',
        f'        <stringProp name="ThreadGroup.ramp_time">${{__P(RAMP_TIME,{ramp_time})}}</stringProp>',
        '        <boolProp name="ThreadGroup.scheduler">true</boolProp>',
        f'        <stringProp name="ThreadGroup.duration">${{__P(DURATION,{duration})}}</stringProp>',
        '      </ThreadGroup>',
        '      <hashTree>',
    ]

    # CSV Data Set Config（从 data_factory 导出的 CSV 读取数据）
    if data_source:
        csv_file = data_source.get("file", "users.csv")
        csv_vars = data_source.get("variables", ["username", "password"])
        csv_delim = data_source.get("delimiter", ",")
        ignore_first = bool(data_source.get("ignore_first_line", True))
        recycle = bool(data_source.get("recycle", False))
        share_mode = str(data_source.get("share_mode") or "thread")
        share_prop = {
            "all": "shareMode.all",
            "thread": "shareMode.thread",
            "group": "shareMode.group",
        }.get(share_mode.strip().lower(), "shareMode.thread")
        xml_lines.extend([
            f'        <CSVDataSet guiclass=\"TestBeanGUI\" testclass=\"CSVDataSet\" testname=\"CSV 数据源\" enabled=\"true\">',
            f'          <stringProp name=\"delimiter\">{csv_delim}</stringProp>',
            f'          <stringProp name=\"fileEncoding\">UTF-8</stringProp>',
            f'          <stringProp name=\"filename\">{csv_file}</stringProp>',
            f'          <boolProp name=\"ignoreFirstLine\">{"true" if ignore_first else "false"}</boolProp>',
            f'          <boolProp name=\"quotedData\">true</boolProp>',
            f'          <boolProp name=\"recycle\">{"true" if recycle else "false"}</boolProp>',
            f'          <stringProp name=\"shareMode\">{share_prop}</stringProp>',
            f'          <stringProp name=\"variableNames\">{",".join(csv_vars)}</stringProp>',
            f'        </CSVDataSet>',
            f'        <hashTree/>',
        ])

    # 登录端点（如果需要）
    if login_endpoint:
        ep = login_endpoint
        name = ep.get("name", "登录")
        method = (ep.get("method") or "POST").upper()
        path = ep.get("path", "/api/auth/login")
        json_body = ep.get("json_body", {})

        xml_lines.extend([
            f'        <HTTPSamplerProxy guiclass="HttpTestSampleGui" testclass="HTTPSamplerProxy" testname="{name}" enabled="true">',
            '          <boolProp name="HTTPSampler.postBodyRaw">true</boolProp>',
            '          <elementProp name="HTTPsampler.Arguments" elementType="Arguments">',
            '            <collectionProp name="Arguments.arguments">',
            '              <elementProp name="" elementType="HTTPArgument">',
            '                <boolProp name="HTTPArgument.always_encode">false</boolProp>',
            f'                <stringProp name="Argument.value">{json.dumps(json_body, ensure_ascii=False)}</stringProp>',
            '              </elementProp>',
            '            </collectionProp>',
            '          </elementProp>',
            f'          <stringProp name="HTTPSampler.path">{path}</stringProp>',
            f'          <stringProp name="HTTPSampler.method">{method}</stringProp>',
            '        </HTTPSamplerProxy>',
            '        <hashTree>',
            # JSON Header
            '          <HeaderManager guiclass="HeaderPanel" testclass="HeaderManager" testname="JSON Header" enabled="true">',
            '            <collectionProp name="HeaderManager.headers">',
            '              <elementProp name="" elementType="Header">',
            '                <stringProp name="Header.name">Content-Type</stringProp>',
            '                <stringProp name="Header.value">application/json</stringProp>',
            '              </elementProp>',
            '            </collectionProp>',
            '          </HeaderManager>',
            '          <hashTree/>',
            # JSON Extractor for token
            '          <JSONPostProcessor guiclass="JSONPostProcessorGui" testclass="JSONPostProcessor" testname="提取 token" enabled="true">',
            '            <stringProp name="JSONPostProcessor.referenceNames">token</stringProp>',
            '            <stringProp name="JSONPostProcessor.jsonPathExprs">$.token</stringProp>',
            '            <stringProp name="JSONPostProcessor.match_numbers">0</stringProp>',
            '          </JSONPostProcessor>',
            '          <hashTree/>',
            # Status assertion
            '          <ResponseAssertion guiclass="AssertionGui" testclass="ResponseAssertion" testname="登录 200" enabled="true">',
            '            <collectionProp name="Asserion.test_strings">',
            '              <stringProp name="49586">200</stringProp>',
            '            </collectionProp>',
            '            <stringProp name="Assertion.test_field">Assertion.response_code</stringProp>',
            '          </ResponseAssertion>',
            '          <hashTree/>',
            '        </hashTree>',
        ])

    # 业务端点
    for ei, ep in enumerate(endpoints):
        if ep.get("auth") == "login":
            continue  # 已处理

        name = ep.get("name") or f"端点_{ei+1}"
        method = (ep.get("method") or "GET").upper()
        path = ep.get("path", "/")
        json_body = ep.get("json_body")
        expect_status = ep.get("expect_status", 200)
        weight = ep.get("weight", 1)
        needs_token = ep.get("auth")

        xml_lines.extend([
            f'        <HTTPSamplerProxy guiclass="HttpTestSampleGui" testclass="HTTPSamplerProxy" testname="{name}" enabled="true">',
            f'          <stringProp name="HTTPSampler.path">{path}</stringProp>',
            f'          <stringProp name="HTTPSampler.method">{method}</stringProp>',
        ])

        if json_body and method in ("POST", "PUT", "PATCH"):
            xml_lines.extend([
                '          <boolProp name="HTTPSampler.postBodyRaw">true</boolProp>',
                '          <elementProp name="HTTPsampler.Arguments" elementType="Arguments">',
                '            <collectionProp name="Arguments.arguments">',
                '              <elementProp name="" elementType="HTTPArgument">',
                '                <boolProp name="HTTPArgument.always_encode">false</boolProp>',
                f'                <stringProp name="Argument.value">{json.dumps(json_body, ensure_ascii=False)}</stringProp>',
                '              </elementProp>',
                '            </collectionProp>',
                '          </elementProp>',
            ])

        xml_lines.append('        </HTTPSamplerProxy>')
        xml_lines.append('        <hashTree>')

        # Header Manager（如果需要 token）
        if needs_token:
            xml_lines.extend([
                '          <HeaderManager guiclass="HeaderPanel" testclass="HeaderManager" testname="Bearer Token" enabled="true">',
                '            <collectionProp name="HeaderManager.headers">',
                '              <elementProp name="" elementType="Header">',
                '                <stringProp name="Header.name">Authorization</stringProp>',
                '                <stringProp name="Header.value">Bearer ${token}</stringProp>',
                '              </elementProp>',
                '            </collectionProp>',
                '          </HeaderManager>',
                '          <hashTree/>',
            ])

        if json_body and method in ("POST", "PUT", "PATCH"):
            xml_lines.extend([
                '          <HeaderManager guiclass="HeaderPanel" testclass="HeaderManager" testname="JSON Header" enabled="true">',
                '            <collectionProp name="HeaderManager.headers">',
                '              <elementProp name="" elementType="Header">',
                '                <stringProp name="Header.name">Content-Type</stringProp>',
                '                <stringProp name="Header.value">application/json</stringProp>',
                '              </elementProp>',
                '            </collectionProp>',
                '          </HeaderManager>',
                '          <hashTree/>',
            ])

        # Status assertion
        xml_lines.extend([
            '          <ResponseAssertion guiclass="AssertionGui" testclass="ResponseAssertion" testname="{name} {expect_status}" enabled="true">',
            '            <collectionProp name="Asserion.test_strings">',
            f'              <stringProp name="49586">{expect_status}</stringProp>',
            '            </collectionProp>',
            '            <stringProp name="Assertion.test_field">Assertion.response_code</stringProp>',
            '          </ResponseAssertion>',
            '          <hashTree/>',
            '        </hashTree>',
        ])

    # Close Thread Group and hashTree
    xml_lines.extend([
        '      </hashTree>',
        '    </hashTree>',
        '  </hashTree>',
        '</jmeterTestPlan>',
    ])

    return "\n".join(xml_lines) + "\n"


def render_visual_regression(meta: dict[str, Any], body: str) -> str:
    """生成视觉回归测试脚本（Playwright screenshot 对比）。"""
    base_url = meta.get("base_url", "http://your-server:5566")
    vp = meta.get("viewport") or {"width": 1280, "height": 720}
    w, h = int(vp.get("width", 1280)), int(vp.get("height", 720))
    threshold = float(meta.get("threshold", 0.2))
    max_diff = int(meta.get("max_diff_pixels", 100))
    pages = meta.get("pages") or []
    if not pages:
        raise ValueError("pages 不能为空（至少指定一个要截图的页面）")

    fx = f'''@pytest.fixture(scope="function")
def browser_context_args(browser_context_args: dict) -> dict:
    return {{
        **browser_context_args,
        "viewport": {{"width": {w}, "height": {h}}},
    }}
'''

    lines = [
        "# Auto-generated by spec runner — 视觉回归测试",
        "# 首次运行: pytest --update-snapshots（生成基线）",
        "# 后续运行: pytest（对比基线）",
        "",
        "from __future__ import annotations",
        "",
        "import pytest",
        "import os",
        "from playwright.sync_api import Page, expect",
        "",
        f"BASE_URL = os.environ.get('TEST_BASE_URL', {esc(base_url)})",
        f"THRESHOLD = {threshold}",
        f"MAX_DIFF_PIXELS = {max_diff}",
        "",
        fx,
        "",
    ]

    for pi, page in enumerate(pages):
        name = page.get("name") or f"page_{pi+1}"
        path = page.get("path", "/")
        wait_ms = int(page.get("wait_ms", 2000))
        actions = page.get("actions") or []
        # 安全文件名
        safe_name = re.sub(r"[^a-z0-9_]+", "_", name.lower()).strip("_")
        if not safe_name:
            safe_name = f"page_{pi+1}"
        fn = f"test_visual_{safe_name}"

        lines.append(f"@pytest.mark.parametrize(\"page_name\", [{esc(name)}])")
        lines.append(f"def {fn}(page: Page, page_name: str):")
        lines.append(f'    """视觉回归: {name}"""')

        # 执行前置操作（如登录）
        if actions:
            lines.append(f"    # 前置操作")
            for action in actions:
                a = (action.get("action") or "").lower()
                if a == "fill":
                    if action.get("l1_label"):
                        lines.append(f'    page.get_by_label({esc(action["l1_label"])}).fill({esc(action.get("value", ""))})')
                    elif action.get("l1_test_id"):
                        lines.append(f'    page.get_by_test_id({esc(action["l1_test_id"])}).fill({esc(action.get("value", ""))})')
                    elif action.get("l1_placeholder"):
                        lines.append(f'    page.get_by_placeholder({esc(action["l1_placeholder"])}).fill({esc(action.get("value", ""))})')
                elif a == "click":
                    if action.get("l1_role") == "button" and action.get("l1_name"):
                        lines.append(f'    page.get_by_role("button", name={esc(action["l1_name"])}).click()')
                    elif action.get("l1_role") == "link" and action.get("l1_name"):
                        lines.append(f'    page.get_by_role("link", name={esc(action["l1_name"])}).click()')
                    elif action.get("l2_css"):
                        lines.append(f'    page.locator({esc(action["l2_css"])}).click()')
                elif a == "wait_timeout_ms":
                    lines.append(f'    page.wait_for_timeout({int(action.get("ms", 500))})')
                elif a == "goto":
                    lines.append(f'    page.goto(BASE_URL + {esc(action.get("path", "/"))})')
                    lines.append(f'    page.wait_for_load_state("domcontentloaded")')

        # 导航 + 等待 + 截图对比
        lines.append(f"    page.goto(BASE_URL + {esc(path)})")
        lines.append(f'    page.wait_for_load_state("domcontentloaded")')
        lines.append(f"    page.wait_for_timeout({wait_ms})")
        lines.append(f"    expect(page).to_have_screenshot(")
        lines.append(f'        f"{{page_name}}.png",')
        lines.append(f"        threshold=THRESHOLD,")
        lines.append(f"        max_diff_pixels=MAX_DIFF_PIXELS,")
        lines.append(f"    )")
        lines.append("")

    if body.strip():
        lines.extend(["", "# --- spec 正文 ---", "# " + body.replace("\n", "\n# ")])
    return "\n".join(lines) + "\n"


EPILOG = """
kind: api_pytest | ui_pytest_playwright | appium_pytest | data_factory | perf_test | jmeter_test | visual_regression

api_pytest:
  base_url, timeout_default, session_headers / default_headers
  setup: test_init（默认，session 调 POST /api/test/init）| none | { kind: data_factory, script: output/data_factory.py }
    环境变量 TEST_SETUP=none 可跳过；TEST_INIT_PATH / TEST_INIT_BODY 可覆盖 init
    scope: session（默认）| function — function 级每条用例独立造数+清理
  teardown: 测试后清理（可选）
    { mode: api_cleanup, path: /api/test/cleanup, method: POST }  # API 清理
    { mode: data_factory_cleanup, script: output/data_factory.py }  # 造数脚本 --cleanup
    { mode: refs_cleanup }  # 读取 data_refs.json 精确删除（推荐）
    { mode: sql_cleanup, statements: ["DELETE FROM ..."] }        # SQL 清理
    scope: session（默认）| function — 与 setup 保持一致
  auth: { type: bearer_login, login_path, username_field, password_field, username_env, password_env }
  cases[]: id, method, path, query|params, json_body, headers, expect_status, timeout,
           no_auth, expect_body_substrings[], expect_json_subset{}, expect_json_schema{},
           expect_max_response_ms, save_token,
           extract_vars: { 变量名: JSONPath如 $.data.token 或 token },
           depends_on: [上游 case id]（失败则 pytest.skip 下游）,
           data_source: data/xxx.csv 或 .json（相对 spec 目录，parametrize 展开）
  variable_pool: { global: { key: value } }  # session 初值，可被 extract_vars 覆盖
  scenarios[]: 多步串联（单测函数内顺序请求）。name, steps[]
    step: method, path（可用 {var}，对应 capture 变量）, query|params, json_body（占位符同 path）,
          headers, expect_status, timeout, no_auth,
          expect_json_subset{}, capture: { 变量名: 点分路径如 data.id }

ui_pytest_playwright:
  base_url, viewport
  setup: 同 api_pytest（默认 test_init，UI 跑前 session 铺底）
  page_objects[]: 页面对象定义（可选，生成 POM 类）
    page_object: name, path, registry_key（从 selectors.json 引用）, elements[]
      element: name, type(input/button), testid/role/label/placeholder/css
      element: name, registry_key（从注册表引用，优先级高于手写）
  steps[] 或 flows[]（多场景）
  step: goto | fill | click | select_option | press | wait_timeout_ms
  expect: visible_text | url_regex | title_contains
  flows[]: name, steps[], data_source（CSV/JSON 数据驱动）, parametrize, expect
    data_source: output/users.csv（相对 spec 目录，CSV 列映射为 _context 变量）
    ensure_logged_in 自动从 _context 读取 username/password（优先于环境变量）

appium_pytest:
  appium_server（默认 http://127.0.0.1:4723）, base_url（铺底/H5 URL，用宿主机 LAN IP 勿 127.0.0.1）,
  driver_scope: class（默认，多 flow 共享 session）| function
  setup: test_init（默认 session 铺底）| none | data_factory（同 api_pytest）
  layer, priority, business — Allure 标记（flow 可覆盖 layer/priority/story）
  capabilities（字典，必填）, implicit_wait_sec, explicit_wait_sec
  steps[] 或 flows[]（多场景）
  step: click | fill | wait_timeout_ms | switch_context | back | hide_keyboard
    | open_url | goto | swipe | scroll | tap | permission | permission_allow | permission_deny
    swipe: start_x/start_y/end_x/end_y 或 from_x/from_y/to_x/to_y, duration_ms
    scroll: direction(down|up|left|right), percent
    tap: x, y
    permission*: allow, button_text（可选，中文「允许」等）
    open_url: url（支持 ${TEST_BASE_URL}）
  expect: element_visible | text_in_page_source
  运行: ./run_appium.sh → pytest；模板见 templates/appium_e2e.md / appium_seckill_h5.md

data_factory:
  database: { host, port, name, user, password }
  tables[]: name, count, fields{}, special_rows[]
  fields: 字段名 → 生成策略
    策略: auto_increment | random_choice(a,b,c) | random_float(min,max) | random_int(min,max)
        | random_date(YYYY-MM-DD,YYYY-MM-DD) | ref('table.field') | uuid | now
        | hash_password('明文') — 生成 scrypt hash 写入 password_hash 列（需 werkzeug）
        | 模板字符串: "user_{i}" | "email_{uuid}@test.com"
  csv_export[]: table, file, fields[], extra_columns{} — 插入后导出 CSV（extra_columns 为常量列，如 password）
    压测 CSV 建议 fields: [username] + extra_columns: {password: "Test123!"}，列顺序与 JMeter variableNames 一致

perf_test:
  base_url, concurrent, duration, ramp_up
  endpoints[]: name, method, path, weight, json_body, headers, expect_status, max_response_ms

jmeter_test:
  base_url, threads, duration, ramp_time
  data_source: { file, variables[], delimiter } — CSV Data Set Config（从 data_factory 导出的 CSV 读取）
  endpoints[]: name, method, path, json_body, expect_status, weight（权重，JMeter 未用，仅记录）, auth（"login" 表示登录端点，"bearer" 表示需 Bearer Token）

visual_regression:
  base_url, viewport, threshold, max_diff_pixels
  pages[]: name, path, wait_ms, actions[]（截图前操作，可选）
    action: fill | click | wait_timeout_ms | goto
  首次运行: pytest --update-snapshots（生成基线截图）
  后续运行: pytest（对比基线，差异超阈值则失败）

--import-openapi:
  从 OpenAPI/Swagger JSON/YAML 自动生成 spec 或 cases JSON
  选项: --base-url --auth-profile <yaml> --smoke-only（仅 H 主路径） --to-cases（输出 JSON 草稿）
  增强: responses 中 401/403/422/400 → X 层负例骨架；schema 约束 → E 层边界 trio
  正式回归默认流水线见 api-skills/执行/references/openapi_pipeline.md
"""


def main() -> None:
    ap = argparse.ArgumentParser(
        description="声明式 spec → 可运行脚本（pytest / Locust / 造数等，见 --print-schema）",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("spec", nargs="?", type=Path)
    ap.add_argument("-o", "--out", type=Path)
    ap.add_argument("--validate-only", action="store_true")
    ap.add_argument("--print-schema", action="store_true")
    ap.add_argument("--import-openapi", type=str, metavar="SOURCE",
                    help="从 OpenAPI/Swagger JSON 自动生成 spec 或 cases JSON")
    ap.add_argument("--base-url", type=str, default=None,
                    help="OpenAPI 导入时的 base_url；省略则从文档 servers/host 推断，仍无时为 http://your-server:port")
    ap.add_argument("--auth-profile", type=Path, default=None,
                    help="OpenAPI 导入时的鉴权 profile（YAML/JSON），见 templates/auth_profiles/")
    ap.add_argument("--smoke-only", action="store_true",
                    help="OpenAPI 导入为冒烟模式（仅 H 主路径，不含 X 负例）")
    ap.add_argument("--to-cases", action="store_true",
                    help="OpenAPI 导入输出 cases JSON 草稿（非 spec .md）")
    ap.add_argument(
        "--rag-context",
        type=Path,
        default=None,
        help="RAG 预检索上下文 .md（由 generate.sh 传入，注入生成物注释块）",
    )
    ns = ap.parse_args()

    if ns.print_schema:
        print(EPILOG)
        return

    # ── OpenAPI 导入分支 ──
    if ns.import_openapi:
        from openapi_import import (
            build_openapi_artifacts,
            infer_auth_profile_from_openapi,
            load_auth_profile,
            spec_meta_to_markdown,
            write_cases_draft_json,
        )

        out_path = ns.out or (Path("output/imported_cases.json") if ns.to_cases else Path("output/imported_spec.md"))
        data = load_openapi(ns.import_openapi)
        inferred = extract_openapi_base_url(data)
        base = (ns.base_url or inferred or "http://your-server:port").rstrip("/")
        mode = "smoke" if ns.smoke_only else "full"
        profile = (
            load_auth_profile(ns.auth_profile)
            if ns.auth_profile
            else infer_auth_profile_from_openapi(data)
        )
        art = build_openapi_artifacts(
            data,
            base_url=base,
            auth_profile=profile,
            include_negatives=(mode != "smoke"),
            mode=mode,
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if ns.to_cases:
            write_cases_draft_json(art["cases_draft"], out_path)
            print(f" 已生成 OpenAPI cases 草稿: {out_path.resolve()}", file=sys.stderr)
            print("   下一步: 评审后 python codegen/testcase_to_api_spec.py -i ... -o templates/xxx.md", file=sys.stderr)
        else:
            spec_content = spec_meta_to_markdown(art["spec_meta"])
            out_path.write_text(spec_content, encoding="utf-8")
            from path_display import display_path

            print(f" 已生成 OpenAPI spec: {display_path(out_path)} (import_mode={mode})", file=sys.stderr)
            if mode == "smoke":
                print("   提示: 冒烟模式；正式回归见 api-skills/执行/references/openapi_pipeline.md", file=sys.stderr)
            else:
                print(f"   下一步: ./generate.sh \"{out_path}\"  # 由 spec 生成 pytest", file=sys.stderr)
        return

    if not ns.spec:
        ap.error("请指定 spec.md 或使用 --print-schema / --import-openapi")

    try:
        text = ns.spec.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f" 找不到文件: {ns.spec}", file=sys.stderr)
        print("   请检查文件路径是否正确", file=sys.stderr)
        sys.exit(1)
    except PermissionError:
        print(f" 无权限读取: {ns.spec}", file=sys.stderr)
        sys.exit(1)

    try:
        meta, bd = parse_frontmatter(text)
    except ValueError as e:
        print(f" spec 格式错误: {e}", file=sys.stderr)
        print("   文件开头需要 --- ... --- 包裹的 YAML frontmatter", file=sys.stderr)
        sys.exit(1)

    raw_kind = meta.get("kind")
    if raw_kind is None or (isinstance(raw_kind, str) and not raw_kind.strip()):
        print(" 缺少 kind 字段（api_pytest / ui_pytest_playwright / appium_pytest / data_factory / perf_test / visual_regression）", file=sys.stderr)
        sys.exit(1)
    kind = str(raw_kind).strip()

    if ns.validate_only:
        if kind not in ("api_pytest", "ui_pytest_playwright", "appium_pytest", "data_factory", "perf_test", "visual_regression", "jmeter_test"):
            print(f" 不支持的 kind: {kind}", file=sys.stderr)
            sys.exit(1)
        print("OK", kind, file=sys.stderr)
        return
    if not ns.out:
        ap.error("须指定 -o")

    try:
        if kind == "api_pytest":
            out = render_api_pytest(meta, bd, spec_path=ns.spec.resolve())
        elif kind == "ui_pytest_playwright":
            out = render_ui_pytest(meta, bd)
        elif kind == "appium_pytest":
            out = render_appium_pytest(meta, bd)
        elif kind == "data_factory":
            out = render_data_factory(meta, bd)
        elif kind == "perf_test":
            out = render_perf_test(meta, bd)
        elif kind == "visual_regression":
            out = render_visual_regression(meta, bd)
        elif kind == "jmeter_test":
            out = render_jmeter_script(meta, bd)
        else:
            print(f" 不支持的 kind: {kind}", file=sys.stderr)
            sys.exit(1)
    except ValueError as e:
        print(f" 生成失败: {e}", file=sys.stderr)
        sys.exit(1)

    if ns.rag_context and kind in ("api_pytest", "ui_pytest_playwright", "appium_pytest"):
        out = _inject_rag_context(out, ns.rag_context.resolve(), out_suffix=ns.out.suffix.lower())

    ns.out.parent.mkdir(parents=True, exist_ok=True)
    ns.out.write_text(out, encoding="utf-8")
    from path_display import display_path

    print(f"已生成: {display_path(ns.out)}", flush=True)


if __name__ == "__main__":
    main()