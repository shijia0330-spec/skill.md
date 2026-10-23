"""
RAG 服务（独立版本）
整合关键词检索、向量检索、RRF 融合、Rerank 精排
"""
import os
import json
import logging
from typing import List, Dict, Any, Optional
from keywords import extract_keywords, build_search_query
from reranker import RerankService
from embedding_store import create_embedding_store

logger = logging.getLogger(__name__)


class RAGService:
    """RAG 检索增强生成服务"""
    
    def __init__(
        self,
        data_dir: str = None,
        store_type: str = "faiss",
        top_k: int = 5,
    ):
        self.data_dir = data_dir or os.path.join(os.path.dirname(__file__), "..", "data")
        self.top_k = top_k
        self.reranker = RerankService()
        self.embedding_store = create_embedding_store(store_type, data_dir=self.data_dir)
        self.knowledge_base = []  # 知识库（BM25 用）
        self._hydrate_knowledge_base()

    def _hydrate_knowledge_base(self):
        """从持久化向量索引恢复 BM25 语料（与 faiss_index.json 同步）"""
        store = self.embedding_store
        texts = getattr(store, "texts", None) or []
        metas = getattr(store, "metadatas", None) or []
        seen = {item["text"] for item in self.knowledge_base}
        for i, text in enumerate(texts):
            if text in seen:
                continue
            meta = metas[i] if i < len(metas) else {}
            self.knowledge_base.append({"text": text, "metadata": meta})
            seen.add(text)
    
    def add_knowledge(self, texts: List[str], metadatas: List[Dict] = None):
        """添加知识到知识库"""
        for i, text in enumerate(texts):
            self.knowledge_base.append({
                "text": text,
                "metadata": metadatas[i] if metadatas else {},
            })
        self.embedding_store.add(texts, metadatas)
        logger.info(f"添加 {len(texts)} 条知识")
    
    def search(
        self,
        query: str,
        top_k: int = None,
        category: str = None,
    ) -> List[Dict]:
        """检索相关知识"""
        top_k = top_k or self.top_k
        
        # 1. BM25 关键词检索
        bm25_results = self._bm25_search(query, top_k * 2)
        
        # 2. 向量语义检索
        vector_results = self.embedding_store.search(query, top_k * 2)
        
        # 3. RRF 融合
        fused_results = self._rrf_fusion(bm25_results, vector_results)
        
        # 4. 类型过滤
        if category:
            fused_results = [r for r in fused_results if r.get("metadata", {}).get("type") == category]
        
        # 5. Rerank 精排
        reranked = self.reranker.rerank(query, fused_results, top_k)
        
        return reranked
    
    def _bm25_search(self, query: str, top_k: int) -> List[Dict]:
        """BM25 关键词检索（简化版：使用关键词匹配）"""
        keywords = extract_keywords(query, top_n=8)
        if not keywords:
            return []
        
        results = []
        for item in self.knowledge_base:
            text = item["text"]
            # 计算关键词匹配度
            matches = sum(1 for kw in keywords if kw in text)
            if matches > 0:
                relevance = matches / len(keywords)
                results.append({
                    "text": text,
                    "metadata": item["metadata"],
                    "relevance": relevance,
                })
        
        # 按相关性排序
        results.sort(key=lambda x: x["relevance"], reverse=True)
        return results[:top_k]
    
    def _rrf_fusion(
        self,
        bm25_results: List[Dict],
        vector_results: List[Dict],
        k: int = 60,
    ) -> List[Dict]:
        """RRF 融合（Reciprocal Rank Fusion）"""
        # 建立文本到结果的映射
        text_to_bm25 = {r["text"]: r for r in bm25_results}
        text_to_vector = {r["text"]: r for r in vector_results}
        
        # 合并所有文本
        all_texts = set(text_to_bm25.keys()) | set(text_to_vector.keys())
        
        # 计算 RRF 得分
        fused = []
        for text in all_texts:
            bm25_rank = bm25_results.index(text_to_bm25[text]) + 1 if text in text_to_bm25 else len(bm25_results) + 1
            vector_rank = vector_results.index(text_to_vector[text]) + 1 if text in text_to_vector else len(vector_results) + 1
            
            rrf_score = 1 / (k + bm25_rank) + 1 / (k + vector_rank)
            
            # 使用较高的 relevance
            relevance = max(
                text_to_bm25.get(text, {}).get("relevance", 0),
                text_to_vector.get(text, {}).get("relevance", 0),
            )
            
            # 合并 metadata
            metadata = {**text_to_bm25.get(text, {}).get("metadata", {}),
                       **text_to_vector.get(text, {}).get("metadata", {})}
            
            fused.append({
                "text": text,
                "metadata": metadata,
                "relevance": relevance,
                "rrf_score": rrf_score,
            })
        
        # 按 RRF 得分排序
        fused.sort(key=lambda x: x["rrf_score"], reverse=True)
        return fused
    
    def get_context(
        self,
        query: str,
        top_k: int = 5,
        max_tokens: int = 3000,
    ) -> str:
        """获取检索上下文（裁剪到 max_tokens）"""
        results = self.search(query, top_k=top_k)
        
        # 构建上下文
        context_parts = []
        for i, r in enumerate(results, 1):
            text = r["text"]
            metadata = r.get("metadata", {})
            title = metadata.get("title", "")
            doc_type = metadata.get("type", "doc")
            
            part = f"{i}. [{doc_type}] {title}: {text}"
            context_parts.append(part)
        
        # 裁剪到 max_tokens（简化：按字符数）
        context = "\n".join(context_parts)
        if len(context) > max_tokens * 4:  # 粗略估计：1 token ≈ 4 字符
            context = context[:max_tokens * 4] + "..."
        
        return context


def create_rag_service(**kwargs) -> RAGService:
    """创建 RAG 服务"""
    return RAGService(**kwargs)


if __name__ == "__main__":
    # 自测
    print("=== RAG 服务自测 ===\n")
    
    rag = RAGService()
    
    # 添加测试知识
    texts = [
        "用户登录功能需要支持用户名密码登录、手机号验证码登录",
        "Token 鉴权机制：每次请求需要携带 Bearer Token",
        "支付接口测试：验证支付成功、失败、超时等场景",
        "订单创建流程：用户下单→库存扣减→支付→发货",
        "改密后旧 Token 失效：修改密码后旧会话应踢下线",
        "密码错误 5 次锁定账号 30 分钟",
        "API 接口测试需要覆盖正常、异常、边界场景",
        "性能测试需要关注 P95/P99 响应时间",
    ]
    metadatas = [
        {"type": "case", "title": "登录测试"},
        {"type": "best_practice", "title": "鉴权设计"},
        {"type": "case", "title": "支付测试"},
        {"type": "case", "title": "订单测试"},
        {"type": "bug", "title": "改密未踢下线"},
        {"type": "case", "title": "密码锁定"},
        {"type": "best_practice", "title": "API测试规范"},
        {"type": "best_practice", "title": "性能测试规范"},
    ]
    
    rag.add_knowledge(texts, metadatas)
    print(f"[OK] 添加 {len(texts)} 条知识")
    
    # 搜索
    query = "登录模块测试"
    results = rag.search(query, top_k=3)
    print(f"\n搜索 '{query}' Top 3:")
    for r in results:
        print(f"  - {r['text'][:30]}... (relevance={r['relevance']:.3f})")
    
    # 获取上下文
    context = rag.get_context("Token 鉴权", top_k=3)
    print(f"\n【RAG 检索结果】\n{context}")
    
    print("\n[OK] RAG 服务测试通过")
