#!/usr/bin/env python3
"""
RAG 知识库种子数据导入 — 从 examples/ 目录导入历史用例、PRD、测试方案到 FAISS 索引。

用法:
    cd rag-engine/scripts
    python seed_knowledge.py

或从项目根目录:
    python rag-engine/scripts/seed_knowledge.py
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path


def _skills_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read_md(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _extract_sections(text: str) -> list[tuple[str, str]]:
    """从 Markdown 提取二级标题段落。"""
    sections = []
    current_title = ""
    current_body = []
    for line in text.split("\n"):
        m = re.match(r"^##\s+(.+)", line.strip())
        if m:
            if current_title and current_body:
                sections.append((current_title, "\n".join(current_body)))
            current_title = m.group(1).strip()
            current_body = []
        else:
            current_body.append(line)
    if current_title and current_body:
        sections.append((current_title, "\n".join(current_body)))
    return sections


def seed_from_examples() -> list[tuple[str, dict]]:
    """从 examples/ 目录导入种子数据。"""
    root = _skills_root()
    examples_dir = root / "examples"
    entries: list[tuple[str, dict]] = []

    if not examples_dir.exists():
        print(f"  examples/ 目录不存在: {examples_dir}")
        return entries

    for md_file in sorted(examples_dir.glob("*.md")):
        text = _read_md(md_file)
        title = md_file.stem.replace("_", " ")

        # 按类型分类
        if "prd" in md_file.name.lower():
            kind = "requirement"
        elif "test-plan" in md_file.name.lower() or "testplan" in md_file.name.lower():
            kind = "test_plan"
        elif "testcase" in md_file.name.lower() or "case" in md_file.name.lower():
            kind = "case"
        elif "bug" in md_file.name.lower():
            kind = "bug"
        else:
            kind = "general"

        # 提取关键内容（截断到 2000 字符）
        body = text[:2000].strip()

        # 构造检索关键词
        keywords = f"{title} {kind} {body[:200]}"

        entries.append((keywords, {
            "type": kind,
            "title": title,
            "source": f"examples/{md_file.name}",
        }))

        # 也按二级标题分段导入
        for sec_title, sec_body in _extract_sections(text):
            if len(sec_body.strip()) > 50:
                sec_keywords = f"{title} {sec_title} {sec_body[:300]}"
                entries.append((sec_keywords, {
                    "type": kind,
                    "title": f"{title} - {sec_title}",
                    "source": f"examples/{md_file.name}##{sec_title}",
                }))

    return entries


def seed_from_templates() -> list[tuple[str, dict]]:
    """从 templates/ 目录导入种子数据。"""
    root = _skills_root()
    templates_dir = root / "templates"
    entries: list[tuple[str, dict]] = []

    if not templates_dir.exists():
        return entries

    for md_file in sorted(templates_dir.glob("*.md")):
        if md_file.name.startswith("testcase") or md_file.name.startswith("需求") or md_file.name.startswith("测试用例"):
            text = _read_md(md_file)[:1500]
            entries.append((
                f"{md_file.stem} {text[:300]}",
                {
                    "type": "template",
                    "title": md_file.stem,
                    "source": f"templates/{md_file.name}",
                }
            ))

    return entries


def seed_from_testcase_skills() -> list[tuple[str, dict]]:
    """从 testcase-skills/ 目录导入种子数据。"""
    root = _skills_root()
    tc_dir = root / "testcase-skills"
    entries: list[tuple[str, dict]] = []

    if not tc_dir.exists():
        return entries

    for md_file in tc_dir.rglob("*.md"):
        if "references" in str(md_file) or "SKILL.md" in md_file.name:
            text = _read_md(md_file)[:1500]
            rel = md_file.relative_to(tc_dir)
            entries.append((
                f"testcase-skills {rel} {text[:300]}",
                {
                    "type": "skill_doc",
                    "title": str(rel),
                    "source": f"testcase-skills/{rel}",
                }
            ))

    return entries


def main() -> int:
    root = _skills_root()
    rag_scripts = root / "rag-engine" / "scripts"
    sys.path.insert(0, str(rag_scripts))

    from service import create_rag_service  # noqa: E402

    rag = create_rag_service()

    all_entries = []
    all_entries.extend(seed_from_examples())
    print(f"  examples/: {len(seed_from_examples())} 条")
    all_entries.extend(seed_from_templates())
    print(f"  templates/: {len(seed_from_templates())} 条")
    all_entries.extend(seed_from_testcase_skills())
    print(f"  testcase-skills/: {len(seed_from_testcase_skills())} 条")

    # 去重（按 title + source）
    seen = set()
    unique_entries = []
    for keywords, metadata in all_entries:
        key = (metadata.get("title", ""), metadata.get("source", ""))
        if key not in seen:
            seen.add(key)
            unique_entries.append((keywords, metadata))

    print(f"\n  去重后: {len(unique_entries)} 条")

    # 批量导入
    if unique_entries:
        keywords_list = [k for k, _ in unique_entries]
        metadata_list = [m for _, m in unique_entries]
        rag.add_knowledge(keywords_list, metadata_list)
        print(f"  已导入 {len(unique_entries)} 条种子数据到 RAG 知识库")
    else:
        print("  无新数据可导入")

    # 验证
    results = rag.search("秒杀 测试", top_k=3)
    print(f"\n  验证检索 '秒杀 测试': {len(results)} 条结果")
    for r in results[:3]:
        print(f"    - {r.get('metadata', {}).get('title', '?')} (relevance={r.get('relevance', 0):.3f})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
