#!/usr/bin/env python3
"""
HAR → perf_test spec（k6 / JMeter），对接 load-testing skills 执行链路。

用法:
  python codegen/har_to_perf.py -i capture.har -o templates/perf_test_k6.md --engine k6
  python codegen/har_to_perf.py -i capture.har -o templates/perf_test_jmeter.md --engine jmeter
  powershell -File run_perf_from_har.ps1 -Har capture.har -Engine k6 -Smoke
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]

sys.path.insert(0, str(Path(__file__).resolve().parent))
from har_lib import collect_har_endpoints, infer_base_url  # noqa: E402


def _load_auth_profile(path: Path | None) -> dict[str, Any] | None:
    if not path or not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    if path.suffix in (".yaml", ".yml"):
        if yaml is None:
            raise RuntimeError("需要 PyYAML: pip install PyYAML")
        data = yaml.safe_load(text)
    else:
        data = json.loads(text)
    return data if isinstance(data, dict) else None


def build_perf_meta(
    har: dict[str, Any],
    *,
    engine: str,
    base_url: str | None,
    auth_profile: dict[str, Any] | None,
    concurrent: int,
    duration: int,
    ramp_up: int,
    smoke: bool,
    filter_api_smoke_only: bool,
) -> dict[str, Any]:
    endpoints = collect_har_endpoints(har, filter_api_smoke_only=filter_api_smoke_only)
    bu = (base_url or infer_base_url(har, "http://your-server:5001")).rstrip("/")

    meta: dict[str, Any] = {
        "kind": "perf_test",
        "engine": engine,
        "base_url": bu,
        "concurrent": 1 if smoke else concurrent,
        "duration": 30 if smoke else duration,
        "ramp_up": 5 if smoke else ramp_up,
        "probe_path": "/api/health",
        "endpoints": endpoints,
    }
    if auth_profile:
        auth = {k: auth_profile[k] for k in auth_profile if k not in ("notes", "session_headers")}
        meta["auth"] = auth
        if auth_profile.get("type") in ("ui_storage_login", "ui_storage_login"):
            meta["expect_business_code"] = True
    else:
        meta["auth"] = {"type": "bearer_login", "login_path": "/api/auth/login"}
    if smoke:
        meta["smoke"] = True
    return meta


def build_markdown(meta: dict[str, Any], *, title: str, har_name: str) -> str:
    fm = yaml.safe_dump(meta, allow_unicode=True, default_flow_style=False, sort_keys=False).rstrip()
    body = f"""
# {title}

HAR 一键导入：`{har_name}`

```powershell
powershell -File run_perf_from_har.ps1 -Har {har_name} -Engine {meta.get('engine', 'k6')} -Smoke
```
"""
    return f"---\n{fm}\n---{body}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-i", "--input", type=Path, required=True, help="HAR 文件")
    ap.add_argument("-o", "--output", type=Path, required=True, help="输出 perf spec .md")
    ap.add_argument("--engine", choices=("k6", "jmeter", "locust"), default="k6")
    ap.add_argument("--base-url", default=None)
    ap.add_argument("--auth-profile", type=Path, default=Path("templates/auth_profiles/generic_rest.yaml"))
    ap.add_argument("--concurrent", type=int, default=5)
    ap.add_argument("--duration", type=int, default=30)
    ap.add_argument("--ramp-up", type=int, default=5)
    ap.add_argument("--smoke", action="store_true", help="冒烟参数：1 VU / 30s")
    ap.add_argument("--api-smoke-only", action="store_true", help="仅保留秒杀 REST /api/ 条目")
    ns = ap.parse_args()

    inp = ns.input if ns.input.is_absolute() else (ROOT / ns.input).resolve()
    out = ns.output if ns.output.is_absolute() else (ROOT / ns.output).resolve()
    auth_src = ns.auth_profile if ns.auth_profile.is_absolute() else (ROOT / ns.auth_profile).resolve()

    har = json.loads(inp.read_text(encoding="utf-8"))
    profile = _load_auth_profile(auth_src)
    meta = build_perf_meta(
        har,
        engine=ns.engine,
        base_url=ns.base_url,
        auth_profile=profile,
        concurrent=ns.concurrent,
        duration=ns.duration,
        ramp_up=ns.ramp_up,
        smoke=ns.smoke,
        filter_api_smoke_only=ns.api_smoke_only,
    )
    title = f"HAR 压测（{ns.engine} · 导入）"
    md = build_markdown(meta, title=title, har_name=inp.name)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    print(f"已写入: {out.resolve()} ({len(meta['endpoints'])} endpoints, engine={ns.engine})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
