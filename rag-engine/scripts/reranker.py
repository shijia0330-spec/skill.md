"""
RAG 重排序（独立版本）
在混合检索召回后对候选集二次打分
纯本地实现，不依赖外部服务
"""
from __future__ import annotations
import re
from typing import Any, Dict, List, Optional
from keywords import extract_keywords


def _keyword_overlap(query: str, text: str) -> float:
    """关键词重叠度"""
    kws = extract_keywords(query, top_n=12)
    if not kws or not text:
        return 0.0
    hits = sum(1 for kw in kws if kw in text)
    return hits / len(kws)


def _title_boost(query: str, title: str) -> float:
    """标题匹配度"""
    if not title:
        return 0.0
    kws = extract_keywords(query, top_n=6)
    if not kws:
        return 0.0
    hits = sum(1 for kw in kws if kw in title)
    return min(1.0, hits / max(1, len(kws) * 0.5))


class RerankService:
    """多信号重排序：原始相关性 + 关键词重叠 + 标题匹配 + 质量分 + 类型偏好"""

    def __init__(
        self,
        w_relevance: float = 0.45,
        w_keyword: float = 0.25,
        w_title: float = 0.15,
        w_quality: float = 0.10,
        w_type: float = 0.05,
    ):
        self.w_relevance = w_relevance
        self.w_keyword = w_keyword
        self.w_title = w_title
        self.w_quality = w_quality
        self.w_type = w_type

    def rerank(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """对候选集重新打分排序"""
        scored = []
        for item in candidates:
            score = (
                self.w_relevance * item.get("relevance", 0.0)
                + self.w_keyword * _keyword_overlap(query, item.get("text", ""))
                + self.w_title * _title_boost(query, item.get("title", ""))
                + self.w_quality * item.get("quality", 0.5)
                + self.w_type * self._type_score(item.get("type", ""))
            )
            scored.append((score, item))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored[:top_k]]

    @staticmethod
    def _type_score(doc_type: str) -> float:
        """类型偏好分"""
        type_scores = {
            "case": 1.0,
            "bug": 0.8,
            "best_practice": 0.7,
            "doc": 0.5,
        }
        return type_scores.get(doc_type, 0.3)


if __name__ == "__main__":
    # 自测
    print("=== RAG 重排序自测 ===\n")
    
    reranker = RerankService()
    
    candidates = [
        {"title": "登录测试用例", "text": "用户登录功能测试", "relevance": 0.8, "type": "case", "quality": 0.9},
        {"title": "支付接口文档", "text": "支付接口说明", "relevance": 0.6, "type": "doc", "quality": 0.7},
        {"title": "鉴权设计", "text": "Token 鉴权机制", "relevance": 0.9, "type": "best_practice", "quality": 0.8},
    ]
    
    results = reranker.rerank("登录模块测试", candidates, top_k=2)
    print(f"Top 2 结果:")
    for r in results:
        print(f"  - {r['title']} (relevance={r['relevance']})")
    
    assert len(results) == 2
    print("\n[OK] 重排序测试通过")
