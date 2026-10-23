#!/usr/bin/env python3
"""
将 Markdown/文本片段入库到 skills 包内 RAG 索引。

用法：
    python rag-engine/scripts/rag_ingest.py output/bugs/BUG-xxx.md --type bug --title "改密未踢下线"
  python rag-engine/scripts/rag_ingest.py --text "登录需支持 Token 刷新" --type best_practice --title "鉴权"
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from service import create_rag_service  # noqa: E402


def _skills_root() -> Path:
    return _SCRIPTS.parents[1]


def _read_body(path: Path) -> str:
    raw = path.read_text(encoding="utf-8", errors="replace")
    # 缺陷草稿：优先取「现象/复现/根因」段落，否则全文截断
    for marker in ("## 现象", "## 复现步骤", "## 根因", "## 摘要"):
        if marker in raw:
            start = raw.index(marker)
            chunk = raw[start : start + 2000]
            return chunk.strip()
    return raw.strip()[:2000]


def main() -> int:
    parser = argparse.ArgumentParser(description="RAG 知识入库")
    parser.add_argument("file", nargs="?", help="Markdown/文本文件路径")
    parser.add_argument("--text", help="直接入库的文本（与 file 二选一）")
    parser.add_argument("--type", default="doc", help="case / bug / best_practice / doc")
    parser.add_argument("--title", default="", help="条目标题")
    args = parser.parse_args()

    if args.text:
        body = args.text.strip()
    elif args.file:
        p = Path(args.file)
        if not p.is_absolute():
            p = (_skills_root() / p).resolve()
        if not p.is_file():
            print(f"ERROR: file not found: {p}", file=sys.stderr)
            return 1
        body = _read_body(p)
    else:
        parser.error("请提供 file 或 --text")

    if len(body) < 4:
        print("ERROR: text too short", file=sys.stderr)
        return 1

    title = args.title or (Path(args.file).stem if args.file else body[:40])
    meta = {"type": args.type, "title": title}
    rag = create_rag_service()
    rag.add_knowledge([body], [meta])
    print(f"OK ingested [{args.type}] {title} ({len(body)} chars)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
