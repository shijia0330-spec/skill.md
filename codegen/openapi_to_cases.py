#!/usr/bin/env python3
"""
OpenAPI/Swagger → cases_with_automation.json 草稿（供评审 / AI 补全 / testcase_to_api_spec 合并）。

用法:
  python codegen/openapi_to_cases.py -i openapi.json -o output/seckill_cases_draft.json \\
      --base-url http://127.0.0.1:5001 \\
      --auth-profile templates/auth_profiles/generic_rest.yaml

  python codegen/testcase_to_api_spec.py -i output/seckill_cases_draft.json -o templates/seckill_api.md
  ./generate.sh templates/seckill_api.md
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 同目录模块
sys.path.insert(0, str(Path(__file__).resolve().parent))
from openapi_import import (  # noqa: E402
    build_openapi_artifacts,
    load_auth_profile,
    write_cases_draft_json,
)
from run_spec import load_openapi  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-i", "--input", type=Path, required=True, help="OpenAPI JSON/YAML 或 HTTP URL")
    ap.add_argument("-o", "--output", type=Path, required=True, help="输出 cases JSON")
    ap.add_argument("--base-url", default="http://your-server:port", help="服务 base_url")
    ap.add_argument("--auth-profile", type=Path, help="auth YAML/JSON（login_path、token 字段等）")
    ap.add_argument(
        "--mode",
        choices=("full", "smoke"),
        default="full",
        help="full=含 X 层负例骨架；smoke=仅 H 主路径",
    )
    ap.add_argument("--no-negatives", action="store_true", help="等同 --mode smoke")
    ap.add_argument("--no-boundaries", action="store_true", help="不生成 E 层 schema 边界用例")
    ap.add_argument("--no-json-subset", action="store_true", help="不生成 expect_json_subset 弱断言")
    ns = ap.parse_args()

    inp = ns.input if ns.input.is_absolute() else (ROOT / ns.input).resolve()
    out = ns.output if ns.output.is_absolute() else (ROOT / ns.output).resolve()
    auth_src = None
    if ns.auth_profile:
        auth_src = ns.auth_profile if ns.auth_profile.is_absolute() else (ROOT / ns.auth_profile).resolve()

    data = load_openapi(str(inp))
    profile = load_auth_profile(auth_src) if auth_src else None
    mode = "smoke" if ns.no_negatives else ns.mode

    art = build_openapi_artifacts(
        data,
        base_url=ns.base_url,
        auth_profile=profile,
        include_negatives=(mode != "smoke"),
        include_boundaries=not ns.no_boundaries and mode != "smoke",
        include_json_subset=not ns.no_json_subset,
        mode=mode,
    )
    write_cases_draft_json(art["cases_draft"], out)
    n_cases = len(art["cases_draft"].get("cases") or [])
    n_sc = len(art["cases_draft"].get("scenarios") or [])
    print(f"已写入: {out.resolve()} ({n_cases} cases, {n_sc} scenarios, mode={mode})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
