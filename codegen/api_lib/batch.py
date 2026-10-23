"""批量执行：拓扑排序 + asyncio 并发 + 失败阻断。"""
from __future__ import annotations

import asyncio
import csv
import json
from collections import deque
from pathlib import Path
from typing import Any, Callable

import requests

from .json_path import extract_by_path
from .executor import run_case, run_scenario
from .variable_pool import VariablePool


def topological_sort(items: list[str], depends_on: dict[str, list[str]]) -> list[str]:
    """Kahn 算法；循环依赖时抛出 ValueError。"""
    deps: dict[str, set[str]] = {k: set(v) for k, v in depends_on.items()}
    for item in items:
        deps.setdefault(item, set())

    in_degree = {item: 0 for item in items}
    for item in items:
        for dep in deps.get(item, set()):
            if dep in in_degree:
                in_degree[item] += 1

    queue = deque([n for n in items if in_degree[n] == 0])
    order: list[str] = []

    while queue:
        node = queue.popleft()
        order.append(node)
        for item in items:
            if node in deps.get(item, set()):
                in_degree[item] -= 1
                if in_degree[item] == 0:
                    queue.append(item)

    if len(order) != len(items):
        raise ValueError(f"依赖存在环或未解析项: {items} vs {order}")
    return order


# CSV/JSON 行合并进 case 时：元数据列跳过写入 json_body；expect_status 等写入 case 顶层
_ROW_BODY_META_KEYS = frozenset({"case_id", "id", "name", "desc", "description"})
_ROW_PATH_SKIP_KEYS = frozenset({"case_id", "name", "desc", "description"})
_ROW_CASE_KEYS = frozenset({"expect_status", "expected_status", "timeout", "max_response_ms", "no_auth"})


def resolve_row_placeholders(text: str, row: dict[str, Any]) -> str:
    """将 path/query 中的 ${col} / {col} 替换为 CSV/JSON 行值。"""
    out = text
    for k, v in row.items():
        if k in _ROW_PATH_SKIP_KEYS or k in _ROW_CASE_KEYS:
            continue
        sv = "" if v is None else str(v)
        out = out.replace("${" + k + "}", sv)
        out = out.replace("{{" + k + "}}", sv)
        out = out.replace("{" + k + "}", sv)
    return out


def merge_case_with_data_row(case: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    body = dict(case.get("json_body") or {})
    patch: dict[str, Any] = {}
    for k, v in row.items():
        if k in _ROW_BODY_META_KEYS:
            continue
        if k in ("expect_status", "expected_status"):
            if v is not None and str(v).strip() != "":
                patch["expect_status"] = int(v) if str(v).strip().isdigit() else v
        elif k in _ROW_CASE_KEYS:
            patch[k] = v
        else:
            body[k] = v
    merged: dict[str, Any] = {**case, **patch, "json_body": body}
    merged.pop("data_source", None)
    path = merged.get("path")
    if isinstance(path, str):
        merged["path"] = resolve_row_placeholders(path, row)
    query = merged.get("query")
    if isinstance(query, dict):
        merged["query"] = {
            k: resolve_row_placeholders(str(v), row) if isinstance(v, str) else v
            for k, v in query.items()
        }
    return merged


def load_data_rows(source: dict[str, Any]) -> list[dict[str, Any]]:
    stype = (source.get("type") or "json").lower()
    path = Path(source.get("path") or "")
    if not path.is_file():
        raise FileNotFoundError(f"数据源不存在: {path}")

    if stype == "csv":
        with path.open(encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))
    if stype == "json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            key = source.get("key") or "rows"
            rows = data.get(key)
            if isinstance(rows, list):
                return rows
        raise ValueError("JSON 数据源须为数组或 {key: [...]}")
    raise ValueError(f"不支持的数据源类型: {stype}")


async def _run_one(
    sem: asyncio.Semaphore,
    fn: Callable[[], None],
) -> tuple[bool, str | None]:
    async with sem:
        try:
            await asyncio.to_thread(fn)
            return True, None
        except Exception as e:
            return False, str(e)


async def run_batch_async(
    items: list[dict[str, Any]],
    *,
    concurrency: int = 5,
    fail_fast: bool = True,
    progress_cb: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """items: [{id, run: callable, depends_on: [ids]}]"""
    ids = [it["id"] for it in items]
    depends_map = {it["id"]: it.get("depends_on") or [] for it in items}
    order = topological_sort(ids, depends_map)
    item_by_id = {it["id"]: it for it in items}

    sem = asyncio.Semaphore(max(1, concurrency))
    completed: set[str] = set()
    failed: set[str] = set()
    pending = list(order)
    results: dict[str, Any] = {"passed": [], "failed": [], "skipped": []}

    while pending:
        ready: list[str] = []
        blocked: list[str] = []
        for item_id in pending:
            deps = depends_map.get(item_id) or []
            if any(d in failed for d in deps):
                results["skipped"].append({"id": item_id, "reason": "依赖失败"})
                failed.add(item_id)
                if progress_cb:
                    progress_cb({"event": "skipped", "id": item_id})
                continue
            if all(d in completed for d in deps):
                ready.append(item_id)
            else:
                blocked.append(item_id)

        for item_id in list(pending):
            if item_id in failed:
                pending.remove(item_id)

        if not ready:
            for item_id in blocked:
                if item_id in pending:
                    pending.remove(item_id)
                    results["skipped"].append({"id": item_id, "reason": "依赖未完成"})
            break

        wave_outcomes = await asyncio.gather(*[_run_one(sem, item_by_id[i]["run"]) for i in ready])
        wave_failed = False
        for item_id, (ok, err) in zip(ready, wave_outcomes):
            pending.remove(item_id)
            if ok:
                completed.add(item_id)
                results["passed"].append(item_id)
                if progress_cb:
                    progress_cb({"event": "passed", "id": item_id})
            else:
                failed.add(item_id)
                wave_failed = True
                results["failed"].append({"id": item_id, "error": err})
                if progress_cb:
                    progress_cb({"event": "failed", "id": item_id, "error": err})

        if wave_failed and fail_fast:
            for item_id in pending:
                results["skipped"].append({"id": item_id, "reason": "fail_fast"})
            break

    return results


def run_batch(
    auth_session: requests.Session,
    pool: VariablePool,
    base_url: str,
    cases: list[dict[str, Any]],
    scenarios: list[dict[str, Any]],
    batch_cfg: dict[str, Any],
    *,
    anon_session: requests.Session | None = None,
    timeout_default: int = 30,
    progress_path: str | Path | None = None,
) -> dict[str, Any]:
    concurrency = int(batch_cfg.get("concurrency") or 5)
    fail_fast = bool(batch_cfg.get("fail_fast", batch_cfg.get("stop_on_failure", True)))
    depends_on: dict[str, list[str]] = dict(batch_cfg.get("depends_on") or {})
    include_cases = batch_cfg.get("cases")
    include_scenarios = batch_cfg.get("scenarios")

    case_by_id = {c.get("id") or f"case_{i}": c for i, c in enumerate(cases)}
    scenario_by_name = {s.get("name") or f"scenario_{i}": s for i, s in enumerate(scenarios)}

    selected_ids: list[str] = []
    if include_cases:
        selected_ids.extend(include_cases)
    else:
        selected_ids.extend(case_by_id.keys())
    if include_scenarios:
        selected_ids.extend(include_scenarios)
    elif batch_cfg.get("include_scenarios"):
        selected_ids.extend(scenario_by_name.keys())

    data_source = batch_cfg.get("data_source")
    data_rows: list[dict[str, Any]] | None = None
    if data_source:
        data_rows = load_data_rows(data_source)

    df_spec = batch_cfg.get("data_factory")
    if df_spec:
        from .data_factory_hook import run_data_factory_spec

        run_data_factory_spec(str(df_spec))

    progress_file = None
    if progress_path:
        progress_file = Path(progress_path)
        progress_file.parent.mkdir(parents=True, exist_ok=True)

    def _progress(event: dict[str, Any]) -> None:
        if progress_file:
            with progress_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")

    items: list[dict[str, Any]] = []
    isolate_pool = concurrency > 1

    for item_id in selected_ids:
        if item_id in case_by_id:
            case = case_by_id[item_id]

            def _make_case_runner(c: dict[str, Any], rows: list[dict[str, Any]] | None) -> Callable[[], None]:
                def _run() -> None:
                    active_pool = VariablePool(pool.as_dict()) if isolate_pool else pool
                    if rows:
                        for row in rows:
                            merged = merge_case_with_data_row(c, row)
                            run_case(
                                auth_session, active_pool, merged, base_url, timeout_default=timeout_default
                            )
                    else:
                        run_case(auth_session, active_pool, c, base_url, timeout_default=timeout_default)

                return _run

            items.append(
                {
                    "id": item_id,
                    "depends_on": depends_on.get(item_id, []),
                    "run": _make_case_runner(case, data_rows),
                }
            )
        elif item_id in scenario_by_name:
            scenario = scenario_by_name[item_id]

            def _make_scenario_runner(sc: dict[str, Any]) -> Callable[[], None]:
                def _run() -> None:
                    run_scenario(
                        auth_session,
                        pool,
                        sc,
                        base_url,
                        anon_session=anon_session,
                        timeout_default=timeout_default,
                    )

                return _run

            items.append(
                {
                    "id": item_id,
                    "depends_on": depends_on.get(item_id, []),
                    "run": _make_scenario_runner(scenario),
                }
            )

    return asyncio.run(
        run_batch_async(items, concurrency=concurrency, fail_fast=fail_fast, progress_cb=_progress)
    )
