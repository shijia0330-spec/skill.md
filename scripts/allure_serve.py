#!/usr/bin/env python3
"""本地 HTTP 服务打开 Allure 报告（解决 file:// 500）。"""
from __future__ import annotations

import argparse
import http.server
import socketserver
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DIR = ROOT / "output" / "allure-report"
DEFAULT_PORT = 8765


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", type=Path, default=DEFAULT_DIR, help="报告目录")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument(
        "--page",
        default="standalone.html",
        help="入口页（默认 standalone.html；官方报告用 index.html）",
    )
    ap.add_argument("--no-open", action="store_true")
    ns = ap.parse_args()

    report_dir = ns.dir if ns.dir.is_absolute() else ROOT / ns.dir
    if not report_dir.is_dir():
        print(f"目录不存在: {report_dir}", file=sys.stderr)
        return 1

    page = ns.page
    standalone = report_dir / "standalone.html"
    if page == "standalone.html" and not standalone.is_file():
        fb = ROOT / "scripts" / "allure_fallback_report.py"
        if fb.is_file():
            import subprocess

            subprocess.run([sys.executable, str(fb)], check=False)

    url = f"http://127.0.0.1:{ns.port}/{page}"
    handler = functools_partial_handler(report_dir)

    print(f"报告目录: {report_dir.resolve()}")
    print(f"打开: {url}")
    print("按 Ctrl+C 停止服务")

    if not ns.no_open:
        webbrowser.open(url)

    with socketserver.TCPServer(("127.0.0.1", ns.port), handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n已停止")
    return 0


def functools_partial_handler(directory: Path):
    directory = str(directory.resolve())

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=directory, **kwargs)

    return Handler


if __name__ == "__main__":
    sys.exit(main())
