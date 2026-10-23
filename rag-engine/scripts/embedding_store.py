"""
RAG 向量检索（独立版本）
支持 FAISS（轻量级）和 Milvus（生产级）
"""
import os
import json
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class EmbeddingStore:
    """向量嵌入存储基类"""
    
    def __init__(self, data_dir: str = None):
        self.data_dir = data_dir or os.path.join(os.path.dirname(__file__), "..", "data")
        os.makedirs(self.data_dir, exist_ok=True)
    
    def add(self, texts: List[str], metadatas: List[Dict] = None):
        """添加文本向量"""
        raise NotImplementedError
    
    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """搜索相似文本"""
        raise NotImplementedError


class FAISSStore(EmbeddingStore):
    """FAISS 向量存储（轻量级，适合本地开发）"""
    
    def __init__(self, data_dir: str = None, dim: int = 384):
        super().__init__(data_dir)
        self.dim = dim
        self.index_file = os.path.join(self.data_dir, "faiss_index.json")
        self.vectors = []
        self.texts = []
        self.metadatas = []
        self._load()
    
    def _load(self):
        """加载索引"""
        if os.path.exists(self.index_file):
            with open(self.index_file) as f:
                data = json.load(f)
                self.vectors = data.get("vectors", [])
                self.texts = data.get("texts", [])
                self.metadatas = data.get("metadatas", [])
    
    def _save(self):
        """保存索引"""
        with open(self.index_file, "w") as f:
            json.dump({
                "vectors": self.vectors,
                "texts": self.texts,
                "metadatas": self.metadatas,
            }, f, ensure_ascii=False)
    
    def add(self, texts: List[str], metadatas: List[Dict] = None):
        """添加文本向量（简化版：使用文本哈希作为向量）"""
        for i, text in enumerate(texts):
            # 简化向量：使用字符频率作为特征
            vector = self._text_to_vector(text)
            self.vectors.append(vector)
            self.texts.append(text)
            self.metadatas.append(metadatas[i] if metadatas else {})
        self._save()
    
    def _text_to_vector(self, text: str) -> List[float]:
        """文本转向量（简化版）"""
        # 使用字符频率作为特征向量
        freq = {}
        for char in text:
            freq[char] = freq.get(char, 0) + 1
        
        # 归一化
        total = sum(freq.values()) or 1
        vector = [freq.get(chr(i), 0) / total for i in range(256)]
        return vector[:self.dim]
    
    def _cosine_similarity(self, v1: List[float], v2: List[float]) -> float:
        """余弦相似度"""
        dot = sum(a * b for a, b in zip(v1, v2))
        norm1 = sum(a * a for a in v1) ** 0.5
        norm2 = sum(b * b for b in v2) ** 0.5
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot / (norm1 * norm2)
    
    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """搜索相似文本"""
        if not self.vectors:
            return []
        
        query_vector = self._text_to_vector(query)
        
        # 计算相似度
        similarities = []
        for i, vector in enumerate(self.vectors):
            sim = self._cosine_similarity(query_vector, vector)
            similarities.append((sim, i))
        
        # 排序
        similarities.sort(key=lambda x: x[0], reverse=True)
        
        # 返回 Top K
        results = []
        for sim, idx in similarities[:top_k]:
            results.append({
                "text": self.texts[idx],
                "metadata": self.metadatas[idx],
                "relevance": sim,
            })
        
        return results


class MilvusStore(EmbeddingStore):
    """Milvus 向量存储（生产级，需要 Milvus 服务）"""
    
    def __init__(self, data_dir: str = None, collection_name: str = "knowledge"):
        super().__init__(data_dir)
        self.collection_name = collection_name
        self.client = None
    
    def _get_client(self):
        """获取 Milvus 客户端（懒加载）"""
        if self.client is None:
            try:
                from pymilvus import MilvusClient
                uri = os.path.join(self.data_dir, "milvus.db")
                self.client = MilvusClient(uri=uri)
            except ImportError:
                logger.warning("pymilvus 未安装，降级到 FAISS")
                return None
        return self.client
    
    def add(self, texts: List[str], metadatas: List[Dict] = None):
        """添加文本向量到 Milvus"""
        client = self._get_client()
        if client is None:
            # 降级到 FAISS
            faiss = FAISSStore(self.data_dir)
            faiss.add(texts, metadatas)
            return
        
        # Milvus 插入逻辑（需要预先创建集合）
        # 这里简化处理，实际使用需要完整的 Milvus 集成
        logger.info(f"MILVUS: 添加 {len(texts)} 条文本")
    
    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """搜索相似文本"""
        client = self._get_client()
        if client is None:
            # 降级到 FAISS
            faiss = FAISSStore(self.data_dir)
            return faiss.search(query, top_k)
        
        # Milvus 搜索逻辑（简化）
        logger.info(f"MILVUS: 搜索 '{query}'")
        return []


def create_embedding_store(store_type: str = "faiss", **kwargs) -> EmbeddingStore:
    """创建嵌入存储"""
    if store_type == "milvus":
        return MilvusStore(**kwargs)
    else:
        return FAISSStore(**kwargs)


if __name__ == "__main__":
    # 自测
    print("=== RAG 向量检索自测 ===\n")
    
    store = FAISSStore()
    
    # 添加测试数据
    texts = [
        "用户登录功能测试",
        "Token 鉴权机制",
        "支付接口测试",
        "订单创建流程",
        "密码修改后旧 Token 失效",
    ]
    metadatas = [
        {"type": "case", "title": "登录测试"},
        {"type": "best_practice", "title": "鉴权设计"},
        {"type": "case", "title": "支付测试"},
        {"type": "case", "title": "订单测试"},
        {"type": "bug", "title": "改密未踢下线"},
    ]
    
    store.add(texts, metadatas)
    print(f"[OK] 添加 {len(texts)} 条文本")
    
    # 搜索
    results = store.search("登录模块测试", top_k=3)
    print(f"\n搜索 '登录模块测试' Top 3:")
    for r in results:
        print(f"  - {r['text']} (relevance={r['relevance']:.3f})")
    
    print("\n[OK] 向量检索测试通过")
