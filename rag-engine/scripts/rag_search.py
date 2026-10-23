#!/usr/bin/env python3
"""
RAG 检索入口脚本
用法：
    python rag_search.py "登录模块测试"
    python rag_search.py "Token 鉴权" --top-k 5
"""
import sys
import os
import argparse

# 添加脚本目录到路径
sys.path.insert(0, os.path.dirname(__file__))

from service import create_rag_service


def main():
    parser = argparse.ArgumentParser(description="RAG 检索增强生成")
    parser.add_argument("query", help="检索查询")
    parser.add_argument("--top-k", type=int, default=5, help="返回结果数量")
    parser.add_argument("--category", type=str, default=None, help="知识类型过滤 (case/bug/best_practice/doc)")
    parser.add_argument("--add", type=str, nargs="+", help="添加知识文本")
    parser.add_argument("--metadata", type=str, nargs="+", help="知识元数据 (JSON 格式)")
    args = parser.parse_args()
    
    rag = create_rag_service()
    
    # 添加知识
    if args.add:
        metadatas = []
        if args.metadata:
            for m in args.metadata:
                try:
                    metadatas.append(eval(m))
                except:
                    metadatas.append({"type": "doc"})
        else:
            metadatas = [{"type": "doc"}] * len(args.add)
        
        rag.add_knowledge(args.add, metadatas)
        print(f"[OK] 添加 {len(args.add)} 条知识")
        return
    
    # 检索
    results = rag.search(args.query, top_k=args.top_k, category=args.category)
    
    if not results:
        print("[FAIL] 未找到相关知识")
        return
    
    print(f"\n[DOC] 检索结果: '{args.query}' (Top {len(results)})\n")
    for i, r in enumerate(results, 1):
        metadata = r.get("metadata", {})
        title = metadata.get("title", "")
        doc_type = metadata.get("type", "doc")
        relevance = r.get("relevance", 0)
        
        print(f"{i}. [{doc_type}] {title}")
        print(f"   {r['text']}")
        print(f"   relevance={relevance:.3f}\n")
    
    # 生成上下文
    context = rag.get_context(args.query, top_k=args.top_k)
    print(f"【RAG 检索上下文】\n{context}")


if __name__ == "__main__":
    main()
