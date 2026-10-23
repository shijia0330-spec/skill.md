#!/usr/bin/env python3
"""
skills V3.0 ↔ 自然语言 UI 服务（nl_api_server）桥接客户端。

优先调用 NL API（需先启动 nl_api_server.py）；
API 不可用时回退为直接 import 执行（同进程 Playwright）。

用法:
  python nl_ui_client.py "给我新增一个商品"
  python nl_ui_client.py --parse-only "登录后进商品页"
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import requests

DEFAULT_API = os.environ.get("NL_API_URL", "http://os.environ.get('NL_UI_SERVER', 'your-server:5010')")


def _pw_code_dir() -> Path:
    """NL 服务本地代码目录（含 nl_service.py），由环境变量 NL_PLAYWRIGHT_CODE 指定。"""
    raw = os.environ.get("NL_PLAYWRIGHT_CODE", "").strip()
    if not raw:
        raise RuntimeError(
            "NL API 不可用且未设置 NL_PLAYWRIGHT_CODE。"
            "请先启动 nl_api_server（推荐，默认 http://os.environ.get('NL_UI_SERVER', 'your-server:5010')），"
            "或将 NL_PLAYWRIGHT_CODE 指向含 nl_service.py 的目录。"
        )
    p = Path(raw).expanduser().resolve()
    if not p.is_dir():
        raise FileNotFoundError(f"NL_PLAYWRIGHT_CODE 不是有效目录: {p}")
    return p


def _api_available(base: str) -> bool:
    try:
        r = requests.get(f"{base.rstrip('/')}/api/health", timeout=2)
        return r.status_code == 200
    except Exception:
        return False


def run_via_api(text: str, *, base_url: str | None, headless: bool, parser: str | None, api: str) -> dict:
    payload = {"text": text, "headless": headless}
    if base_url:
        payload["base_url"] = base_url
    if parser:
        payload["parser"] = parser
    r = requests.post(f"{api.rstrip('/')}/api/nl/run", json=payload, timeout=300)
    return r.json()


def run_via_import(text: str, *, base_url: str | None, headless: bool, parser: str | None) -> dict:
    sys.path.insert(0, str(_pw_code_dir()))
    if parser:
        os.environ["NL_PARSER"] = parser
    from nl_service import execute_nl  # noqa: WPS433

    return execute_nl(text, base_url=base_url, headless=headless, parser=parser)


def parse_via_api(text: str, *, base_url: str | None, parser: str | None, api: str) -> dict:
    payload = {"text": text}
    if base_url:
        payload["base_url"] = base_url
    if parser:
        payload["parser"] = parser
    r = requests.post(f"{api.rstrip('/')}/api/nl/parse", json=payload, timeout=60)
    return r.json()


def main() -> int:
    p = argparse.ArgumentParser(description="一句话 UI 自动化（Skills 桥接）")
    p.add_argument("text", help="自然语言指令")
    p.add_argument("--api", default=DEFAULT_API, help=f"NL API 地址，默认 {DEFAULT_API}")
    p.add_argument("--base-url", default=None)
    p.add_argument("--parser", choices=["auto", "llm", "regex"], default=None)
    p.add_argument("--no-headless", action="store_true")
    p.add_argument("--parse-only", action="store_true")
    p.add_argument("--json", action="store_true", help="只输出 JSON")
    args = p.parse_args()

    if args.parse_only:
        if _api_available(args.api):
            out = parse_via_api(args.text, base_url=args.base_url, parser=args.parser, api=args.api)
        else:
            sys.path.insert(0, str(_pw_code_dir()))
            if args.parser:
                os.environ["NL_PARSER"] = args.parser
            from nl_service import parse_only  # noqa: WPS433

            out = parse_only(args.text, base_url=args.base_url, parser=args.parser)
    else:
        if _api_available(args.api):
            out = run_via_api(
                args.text,
                base_url=args.base_url,
                headless=not args.no_headless,
                parser=args.parser,
                api=args.api,
            )
        else:
            out = run_via_import(
                args.text,
                base_url=args.base_url,
                headless=not args.no_headless,
                parser=args.parser,
            )

    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(out.get("message") or out)
        if out.get("step_results"):
            for r in out["step_results"]:
                mark = "✓" if r.get("status") == "passed" else "✗"
                print(f"  {mark} {r.get('action')}: {r.get('detail') or r.get('error')}")

    if args.parse_only:
        return 0 if out.get("steps") or out.get("count", 0) > 0 else 1
    return 0 if out.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
