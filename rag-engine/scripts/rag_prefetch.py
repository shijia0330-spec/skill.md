#!/usr/bin/env python3
"""
RAG 预检索 — 从 PRD/需求文本构造检索词，输出可注入 Prompt 的上下文。

领域词配置：rag-engine/config/rag_domain_keywords.json
也可通过环境变量 RAG_DOMAIN_CONFIG 或 --config 指定其它配置文件。

用法（技能包根目录）：
    python3 rag-engine/scripts/rag_prefetch.py 需求文档.md
    python3 rag-engine/scripts/rag_prefetch.py 需求文档.md --top-k 5 --out output/rag_context.md
    python3 rag-engine/scripts/rag_prefetch.py --query "采购入库 验收标准 业务规则"
    python3 rag-engine/scripts/rag_prefetch.py 需求文档.md --config my_project/rag_keywords.json
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
_SKILLS_ROOT = _SCRIPTS.parents[1]
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from query_builder import build_query_from_prd, format_output  # noqa: E402


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def run_prefetch(
    *,
    prd_path: Path | None = None,
    query: str = "",
    top_k: int = 5,
    out_path: Path | None = None,
    config_path: Path | None = None,
) -> tuple[str, int]:
    from service import create_rag_service  # noqa: E402

    q = query.strip()
    if not q:
        if prd_path is None or not prd_path.is_file():
            raise FileNotFoundError("请提供 PRD 路径，或使用 --query")
        q = build_query_from_prd(_read_text(prd_path), config_path=config_path)

    rag = create_rag_service()
    results = rag.search(q, top_k=top_k)
    context = rag.get_context(q, top_k=top_k)
    body = format_output(q, context, len(results))

    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(body, encoding="utf-8")

    return body, len(results)


def main() -> int:
    parser = argparse.ArgumentParser(description="RAG 预检索（skills 包内知识库）")
    parser.add_argument("prd", nargs="?", help="需求/PRD Markdown 路径")
    parser.add_argument("--query", help="直接指定检索词（跳过 PRD 抠词）")
    parser.add_argument("--top-k", type=int, default=5, help="返回条数，默认 5")
    parser.add_argument("--out", help="写入 Markdown 文件（默认仅 stdout）")
    parser.add_argument(
        "--config",
        help="领域词配置文件路径（默认 rag-engine/config/rag_domain_keywords.json）",
    )
    args = parser.parse_args()

    prd_path = Path(args.prd) if args.prd else None
    if prd_path and not prd_path.is_absolute():
        prd_path = (_SKILLS_ROOT / prd_path).resolve()

    out_path = Path(args.out) if args.out else None
    if out_path and not out_path.is_absolute():
        out_path = (_SKILLS_ROOT / out_path).resolve()

    config_path = Path(args.config).resolve() if args.config else None

    try:
        body, hits = run_prefetch(
            prd_path=prd_path,
            query=args.query or "",
            top_k=args.top_k,
            out_path=out_path,
            config_path=config_path,
        )
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if out_path:
        print(f"OK RAG context written: {out_path} (hits={hits})")
    else:
        print(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
