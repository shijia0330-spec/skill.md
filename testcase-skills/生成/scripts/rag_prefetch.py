#!/usr/bin/env python3
"""
用例生成前 RAG 预检索 — 从 PRD/需求文本构造检索词，输出可注入 Prompt 的上下文。

领域词配置：rag-engine/config/rag_domain_keywords.json（换项目只改配置文件）

用法：
    python3 rag_prefetch.py 需求文档.md
    python3 rag_prefetch.py 需求文档.md --top-k 5 --out output/rag_context_login.md
    python3 rag_prefetch.py --query "采购入库 验收标准 业务规则"
    python3 rag_prefetch.py 需求文档.md --config /path/to/my_rag_keywords.json
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _rag_scripts() -> Path:
    return Path(__file__).resolve().parents[3] / "rag-engine" / "scripts"


def main() -> int:
    rag_scripts = _rag_scripts()
    if str(rag_scripts) not in sys.path:
        sys.path.insert(0, str(rag_scripts))

    from query_builder import build_query_from_prd, format_output  # noqa: E402
    from service import create_rag_service  # noqa: E402

    parser = argparse.ArgumentParser(description="用例生成前 RAG 预检索")
    parser.add_argument("prd", nargs="?", help="需求/PRD Markdown 路径")
    parser.add_argument("--query", help="直接指定检索词（跳过 PRD 抠词）")
    parser.add_argument("--top-k", type=int, default=5, help="返回条数，默认 5")
    parser.add_argument("--out", help="写入 Markdown 文件（默认仅 stdout）")
    parser.add_argument(
        "--config",
        help="领域词配置文件路径（默认 rag-engine/config/rag_domain_keywords.json）",
    )
    args = parser.parse_args()

    config_path = Path(args.config).resolve() if args.config else None

    query = (args.query or "").strip()
    if not query:
        if not args.prd:
            parser.error("请提供 PRD 路径，或使用 --query")
        prd_path = Path(args.prd)
        if not prd_path.is_file():
            print(f"[FAIL] 文件不存在: {prd_path}", file=sys.stderr)
            return 1
        query = build_query_from_prd(
            prd_path.read_text(encoding="utf-8", errors="replace"),
            config_path=config_path,
        )

    rag = create_rag_service()
    results = rag.search(query, top_k=args.top_k)
    context = rag.get_context(query, top_k=args.top_k)
    body = format_output(query, context, len(results))

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(body, encoding="utf-8")
        print(f"[OK] RAG 上下文已写入: {out_path}")
    else:
        print(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
