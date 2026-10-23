"""UI 批量 flow 执行（顺序 + 可选 progress jsonl）。"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Callable

from playwright.sync_api import Page

from .context import UIContext
from .locator_resolver import dismiss_page_modals
from .runner import run_ui_flow


def _lighten_login_steps(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """后续 flow：ensure_logged_in → goto（复用同一 browser context 的 cookie）。"""
    out: list[dict[str, Any]] = []
    replaced = False
    for s in steps:
        if not replaced and str(s.get("action") or "").lower() in ("ensure_logged_in", "ensure_login"):
            out.append(
                {
                    "action": "goto",
                    "path": s.get("path") or s.get("target_path") or "/products",
                    "wait_until": "domcontentloaded",
                    "timeout_ms": int(s.get("timeout_ms") or 30000),
                }
            )
            replaced = True
        else:
            out.append(s)
    return out


async def _run_flow_async(
    sem: asyncio.Semaphore,
    fn: Callable[[], None],
) -> tuple[bool, str | None]:
    async with sem:
        try:
            await asyncio.to_thread(fn)
            return True, None
        except Exception as e:
            return False, str(e)


async def run_ui_batch_async(
    items: list[dict[str, Any]],
    *,
    concurrency: int = 1,
    fail_fast: bool = True,
    progress_cb: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    sem = asyncio.Semaphore(max(1, concurrency))
    results: dict[str, Any] = {"passed": [], "failed": [], "skipped": []}

    for item in items:
        ok, err = await _run_flow_async(sem, item["run"])
        fid = item["id"]
        if ok:
            results["passed"].append(fid)
            if progress_cb:
                progress_cb({"event": "passed", "id": fid})
        else:
            results["failed"].append({"id": fid, "error": err})
            if progress_cb:
                progress_cb({"event": "failed", "id": fid, "error": err})
            if fail_fast:
                break

    return results


def run_ui_batch(
    page: Page,
    flows: list[dict[str, Any]],
    *,
    base_url: str,
    batch_cfg: dict[str, Any],
    ctx: UIContext | None = None,
) -> dict[str, Any]:
    concurrency = int(batch_cfg.get("concurrency") or 1)
    fail_fast = bool(batch_cfg.get("fail_fast", True))
    login_once = bool(batch_cfg.get("login_once", False))
    heal = bool(batch_cfg.get("healing", True))
    pretest = bool(batch_cfg.get("pretest", False))
    progress_path = batch_cfg.get("progress_path")

    progress_file = None
    if progress_path:
        progress_file = Path(progress_path)
        progress_file.parent.mkdir(parents=True, exist_ok=True)

    def _progress(event: dict[str, Any]) -> None:
        if progress_file:
            with progress_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")

    include = batch_cfg.get("flows") or [f.get("name") or f"flow_{i}" for i, f in enumerate(flows)]
    by_name = {f.get("name") or f"flow_{i}": f for i, f in enumerate(flows)}

    items: list[dict[str, Any]] = []
    for fi, fid in enumerate(include):
        flow = by_name.get(fid)
        if not flow:
            continue
        steps = [dict(s) for s in (flow.get("steps") or [])]
        if login_once and fi > 0:
            steps = _lighten_login_steps(steps)
        expects = flow.get("expect") or []

        def _make_runner(st=steps, ex=expects, name=fid, flow_idx=fi) -> Callable[[], None]:
            def _run() -> None:
                from api_lib.allure_helper import report_step

                dismiss_page_modals(page)
                flow_ctx = UIContext(ctx.as_dict()) if ctx else UIContext()
                with report_step(f"UI 用例 {flow_idx + 1}: {name}"):
                    run_ui_flow(
                        page,
                        st,
                        expects=ex,
                        base_url=base_url,
                        ctx=flow_ctx,
                        heal=heal,
                        pretest=pretest,
                    )

            return _run

        items.append({"id": fid, "run": _make_runner()})

    results: dict[str, Any] = {"passed": [], "failed": [], "skipped": []}
    for item in items:
        fid = item["id"]
        try:
            item["run"]()
            results["passed"].append(fid)
            _progress({"event": "passed", "id": fid})
        except Exception as exc:
            results["failed"].append({"id": fid, "error": str(exc)})
            _progress({"event": "failed", "id": fid, "error": str(exc)})
            if fail_fast:
                break
    return results
