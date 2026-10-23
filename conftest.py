"""
引擎根 conftest：在 skills-专业版V3.0 根目录及其子目录（含 output/）跑 pytest 时生效。
- 会话结束自动生成进度报告 → output/reports/（PROGRESS_REPORT）
- 失败用例自动根因分析 → output/reports/failure_analysis.json（FAILURE_ANALYSIS）
- 失败用例自动生成缺陷草稿 → output/bugs/（DEFECT_DRAFTS）
- UI 失败额外写截图与 page HTML → output/ui_artifacts/（UI_ARTIFACTS_DIR）
- 可选 pytest 后自动 defect-sync（DEFECT_SYNC=1）
"""

from __future__ import annotations

import importlib.util
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent
_CODEGEN = _ROOT / "codegen"
if str(_CODEGEN) not in sys.path:
    sys.path.insert(0, str(_CODEGEN))
_HOOK = _ROOT / "bug-reporter" / "defect_drafts.py"
_PROGRESS_HOOK = _ROOT / "progress-reporter" / "session_report.py"
_FAILURE_HOOK = _ROOT / "defect-analysis" / "failure_analyzer.py"


def _load_defect_drafts():
    spec = importlib.util.spec_from_file_location("defect_drafts", _HOOK)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载 {_HOOK}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["defect_drafts"] = mod
    spec.loader.exec_module(mod)
    return mod


_dd = _load_defect_drafts()


def _load_progress_report():
    spec = importlib.util.spec_from_file_location("session_report", _PROGRESS_HOOK)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载 {_PROGRESS_HOOK}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["session_report"] = mod
    spec.loader.exec_module(mod)
    return mod


_pr = _load_progress_report()


def _load_failure_analyzer():
    spec = importlib.util.spec_from_file_location("failure_analyzer", _FAILURE_HOOK)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载 {_FAILURE_HOOK}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["failure_analyzer"] = mod
    spec.loader.exec_module(mod)
    return mod


_fa = _load_failure_analyzer()


@pytest.fixture(scope="function")
def browser_context_args(browser_context_args: dict) -> dict:
    """可选登录态：设置 UI_STORAGE_STATE 指向 Playwright storage JSON。"""
    ctx = {**browser_context_args}
    raw = os.environ.get("UI_STORAGE_STATE")
    if raw:
        p = Path(raw)
        if not p.is_absolute():
            p = _ROOT / p
        if p.is_file():
            ctx["storage_state"] = str(p)
    return ctx


_USE_SESSION_PAGE = os.environ.get("UI_SESSION_PAGE", "").strip().lower() in ("1", "true", "yes", "on")

if _USE_SESSION_PAGE:
    @pytest.fixture(scope="session")
    def context(browser, browser_context_args):
        """UI_SESSION_PAGE=1 时复用同一 browser context（cookie 不丢）。"""
        ctx = browser.new_context(**browser_context_args)
        yield ctx
        ctx.close()

    @pytest.fixture(scope="session")
    def page(context):
        """单标签页贯穿 session，各 test 仅做页内操作。"""
        pg = context.new_page()
        yield pg
        pg.close()


def _ui_artifacts_dir() -> Path:
    raw = os.environ.get("UI_ARTIFACTS_DIR", "output/ui_artifacts")
    p = Path(raw)
    if not p.is_absolute():
        p = _ROOT / p
    p.mkdir(parents=True, exist_ok=True)
    return p


def _safe_stem(nodeid: str) -> str:
    s = re.sub(r"[^0-9a-zA-Z._-]+", "_", nodeid.split("::")[-1])[:80]
    return s or "ui_failure"


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args: dict) -> dict:
    """UI 测试默认有头浏览器；设 UI_HEADLESS=1 可改回无头。"""
    if os.environ.get("UI_HEADLESS", "").strip().lower() in ("1", "true", "yes", "on"):
        return browser_type_launch_args
    return {**browser_type_launch_args, "headless": False}


def pytest_configure(config):
    config.addinivalue_line("markers", "allure_layer(layer): Allure 用例分层 H/X/E")
    config.addinivalue_line("markers", "allure_priority(priority): Allure 优先级 P0-P3")
    config.addinivalue_line("markers", "allure_story(story): Allure 故事/追溯编号")

    if _dd._drafts_enabled():
        draft_dir = _dd.resolve_draft_dir()
        config._defect_draft_dir = str(draft_dir)  # noqa: SLF001

    if hasattr(config.option, "tracing"):
        tr = getattr(config.option, "tracing", None)
        if tr in (None, "off"):
            config.option.tracing = "retain-on-failure"
    if hasattr(config.option, "screenshot"):
        sc = getattr(config.option, "screenshot", None)
        if sc in (None, "off"):
            config.option.screenshot = "only-on-failure"


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_setup(item):
    try:
        from api_lib.allure_helper import apply_report_labels

        apply_report_labels(item)
    except Exception:
        pass
    yield


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)

    if rep.when != "call" or not rep.failed:
        return

    page = item.funcargs.get("page")
    if page is None:
        return

    try:
        art = _ui_artifacts_dir()
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        stem = _safe_stem(item.nodeid)
        png = art / f"{stem}_{ts}.png"
        html = art / f"{stem}_{ts}.html"
        page.screenshot(path=str(png), full_page=True)
        html.write_text(page.content(), encoding="utf-8")
        rep.sections.append(("UI 截图", str(png)))
        rep.sections.append(("UI 页面源码", str(html)))
    except Exception as exc:  # noqa: BLE001
        rep.sections.append(("UI 附件失败", str(exc)))


def pytest_sessionfinish(session, exitstatus):
    term = session.config.pluginmanager.get_plugin("terminalreporter")

    if _pr._report_enabled():
        try:
            written = _pr.process_session(session)
            if written and term is not None:
                term.write_line("")
                if "terminal" in written:
                    for line in str(written["terminal"]).splitlines():
                        term.write_line(line, cyan=True)
                if "markdown" in written:
                    term.write_line(
                        f"[progress-report] Markdown: {written['markdown']}",
                        cyan=True,
                    )
                if "json" in written:
                    term.write_line(
                        f"[progress-report] JSON: {written['json']}",
                        cyan=True,
                    )
        except Exception as exc:  # noqa: BLE001
            if term is not None:
                term.write_line(f"[progress-report] 生成失败: {exc}", red=True)

    if not _dd._drafts_enabled():
        return

    failed: list[dict] = []
    for item in session.items:
        # 依次检查 call / setup / teardown，任一阶段有 failed 或 error 就收录
        rep = None
        for phase_name in ("call", "setup", "teardown"):
            r = getattr(item, f"rep_{phase_name}", None)
            if r is not None and (r.failed or r.outcome == "error"):
                rep = r
                break
        if rep is None:
            continue
        longrepr = str(rep.longrepr) if rep.longrepr else ""
        duration = rep.duration if hasattr(rep, "duration") else None
        failed.append(
            {
                "nodeid": item.nodeid,
                "longrepr": longrepr,
                "duration": duration,
            }
        )

    if not failed:
        return

    if _fa._analysis_enabled():
        try:
            fa_written = _fa.process_session_failures(failed)
            if fa_written and term is not None:
                term.write_line("")
                analyses = [
                    _fa.analyze_failure(
                        item["nodeid"],
                        item.get("longrepr") or "",
                        item.get("duration"),
                    )
                    for item in failed
                ]
                _fa._dedupe_analyses(analyses)
                for line in _fa.format_terminal_summary(analyses).splitlines():
                    term.write_line(line, yellow=True)
                if "json" in fa_written:
                    term.write_line(
                        f"[failure-analysis] JSON: {fa_written['json']}",
                        yellow=True,
                    )
                if "markdown" in fa_written:
                    term.write_line(
                        f"[failure-analysis] Markdown: {fa_written['markdown']}",
                        yellow=True,
                    )
        except Exception as exc:  # noqa: BLE001
            if term is not None:
                term.write_line(f"[failure-analysis] 生成失败: {exc}", red=True)

    paths = _dd.process_session_failures(failed)
    draft_dir = _dd.resolve_draft_dir()
    session.config._defect_drafts_written = paths  # noqa: SLF001

    if term is None:
        term = session.config.pluginmanager.get_plugin("terminalreporter")
    if term is not None:
        term.write_line("")
        term.write_line(
            f"[defect-drafts] {len(paths)} 条失败 → 已写缺陷草稿: {draft_dir}",
            yellow=True,
        )
        for p in paths[:5]:
            term.write_line(f"  - {p.name}", yellow=True)
        if len(paths) > 5:
            term.write_line(f"  … 另有 {len(paths) - 5} 条，见 bug_list.md", yellow=True)
        term.write_line(
            f"  汇总: {draft_dir / 'bug_list.md'}",
            yellow=True,
        )
        term.write_line(
            "  推送: cd defect-sync/scripts && python defect_sync.py push <bugs目录> --platform zentao --dry-run",
            yellow=True,
        )

    # 可选：pytest 结束后自动同步到外部平台
    if os.environ.get("DEFECT_SYNC", "").strip().lower() in ("1", "true", "yes", "on"):
        _try_defect_sync(paths, term)

    # RAG 回灌：失败用例自动追加到知识库（供未来 RAG 检索）
    if failed:
        _try_rag_backfill(failed, term)


def _try_rag_backfill(failed: list[dict], term) -> None:
    """将失败用例信息追加到 RAG 知识库。"""
    rag_scripts = _ROOT / "rag-engine" / "scripts"
    service_file = rag_scripts / "service.py"
    if not service_file.is_file():
        return
    try:
        import importlib.util
        import sys as _sys
        # 把 rag-scripts 目录加入 path，解决 keywords/reranker 等相对导入
        _sys.path.insert(0, str(rag_scripts))
        spec = importlib.util.spec_from_file_location("rag_service", service_file)
        if spec is None or spec.loader is None:
            return
        mod = importlib.util.module_from_spec(spec)
        _sys.modules["rag_service"] = mod
        spec.loader.exec_module(mod)
        rag = mod.create_rag_service()

        added = 0
        for item in failed:
            nodeid = item.get("nodeid", "unknown")
            longrepr = item.get("longrepr", "")
            # 提取关键错误信息（截断到 500 字符）
            error_snippet = longrepr[:500].replace("\n", " ").strip()
            if not error_snippet:
                continue
            # 提取模块名（从 nodeid 推导）
            module = nodeid.split("::")[0].replace("/", ".").replace("\\", ".") if "::" in nodeid else nodeid
            # 构造检索关键词
            keywords = f"{module} 测试失败 {error_snippet[:100]}"
            metadata = {
                "type": "bug",
                "title": f"测试失败: {nodeid}",
                "module": module,
                "nodeid": nodeid,
            }
            rag.add_knowledge([keywords], [metadata])
            added += 1

        if added > 0 and term is not None:
            term.write_line("", yellow=True)
            term.write_line(
                f"[rag-backfill] {added} 条失败用例已追加到 RAG 知识库",
                yellow=True,
            )
    except Exception as exc:  # noqa: BLE001
        if term is not None:
            term.write_line(f"[rag-backfill] 回灌失败: {exc}", red=True)


def _try_defect_sync(draft_paths: list, term) -> None:
    sync_script = _ROOT / "defect-sync" / "scripts" / "sync_service.py"
    if not sync_script.is_file():
        return
    spec = importlib.util.spec_from_file_location("sync_service", sync_script)
    if spec is None or spec.loader is None:
        return
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    try:
        report = mod.sync_after_pytest(draft_paths)
        if report and term is not None:
            term.write_line("")
            term.write_line(mod.format_report(report), yellow=True)
    except Exception as exc:  # noqa: BLE001
        if term is not None:
            term.write_line(f"[defect-sync] 自动同步失败: {exc}", red=True)
