---
name: rag-knowledge
description: RAG知识库 — 多路检索（BM25 + 向量）+ RRF 融合 + Rerank 精排，让 AI 生成用例时引用团队历史经验。
---

# RAG知识库

从团队历史用例、最佳实践、Bug 记录中检索相关知识，注入 AI Prompt，让生成**开卷考试**。

---

## 做 / 不做

| 做 | 不做 |
|----|------|
| 多路检索（BM25 + 向量） | 执行测试（走 api-skills） |
| RRF 融合 + Rerank 精排 | 管理知识库（走独立系统） |
| ContextOptimizer 裁剪 | |

---

## 为什么需要 RAG

| 没有 RAG | 有 RAG |
|----------|--------|
| 闭卷考试，只靠模型记忆 | 开卷考试，引用团队经验 |
| 关键词搜不准（搜"登录"找不到"鉴权"） | 向量语义搜索，同义词也能找到 |
| 知识太多塞进 Prompt 会爆 token | ContextOptimizer 裁剪到 ~3000 token |

**生活例子**：像考试——没有 RAG 是闭卷，有 RAG 是开卷。

---

## 检索流水线

```
需求文本
  → 多路检索（BM25 关键词 + 向量语义 + 类型分桶）
  → RRF 融合（两路排名加权）
  → Rerank 精排（最相关的 5 条排前面）
  → ContextOptimizer 裁剪（控制在 ~3000 token）
  → 注入 case-gen Prompt
```

### 三路检索

| 检索方式 | 说明 | 示例 |
|----------|------|------|
| **BM25 关键词** | 全文索引匹配 | 搜"登录"→ 匹配标题含"登录"的文档 |
| **向量语义** | 语义相似度 | 搜"登录"→ 匹配"鉴权/Token"相关文档 |
| **类型分桶** | 按知识类型过滤 | 只检索 case/bug/best_practice |

### RRF 融合

Reciprocal Rank Fusion——把两路检索结果合并，不丢任一路的好结果：

```
RRF 得分 = 1 / (k + BM25排名) + 1 / (k + 向量排名)
k = 60（默认常数）
```

### Rerank 精排

用重排序模型对融合结果重新打分，选出最相关的 Top 5：

```
输入：需求文本 + 50 条候选知识
输出：Top 5 最相关知识（relevance > 0.8）
```

---

## 通俗例子

```
需求："用户修改密码后，旧 Token 应失效"

知识库里有（标题不含"密码"）：
  - 《鉴权设计》第 3 节：refresh_token 轮换策略
  - 《历史 Bug》#892：改密后未踢下线

RAG 检索结果（注入 Prompt 前）：
  1. [case] 改密后旧会话失效-回归用例  relevance=0.92
  2. [best_practice] refresh_token 轮换   relevance=0.88
  3. [bug] #892 改密未踢下线             relevance=0.85

AI 生成时会多出一条：
  I-安全：改密成功后，用旧 Token 调 /api/profile → 预期 401
```

---

## 降级策略

| 情况 | 降级方式 |
|------|----------|
| Milvus 挂了 | 仅用 MySQL BM25 全文索引 |
| 全文索引也失败 | 降级为 LIKE 模糊搜索 |
| 完全无知识库 | 跳过 RAG，纯靠 LLM 生成 |

生活例子：GPS 没信号时降级用纸质地图，慢但能到。

---

## 可执行引擎

**方案 B 已实现**：`rag-engine/` 目录包含可执行的 RAG 代码。

### 领域词配置（换项目只改 JSON）

默认领域为**进销存**，配置文件：

`rag-engine/config/rag_domain_keywords.json`

| 字段 | 说明 |
|------|------|
| `business_keywords` | 从 PRD 中匹配的业务词列表 |
| `test_dimension_suffix` | 拼在检索词末尾的测试维度词 |
| `max_keywords_from_prd` | 最多取几个业务词，默认 6 |

指定其它配置文件：

```bash
# 环境变量
export RAG_DOMAIN_CONFIG=/path/to/my_rag_keywords.json

# 或命令行
python3 testcase-skills/生成/scripts/rag_prefetch.py 需求.md --config my_rag_keywords.json
```

### 快速使用

```bash
# 用例生成前（推荐，与 testcase-skills/生成 Step 0a 一致）
python3 testcase-skills/生成/scripts/rag_prefetch.py 需求文档.md --top-k 5

# 底层检索
cd rag-engine/scripts
python3 rag_search.py "登录模块测试" --top-k 3

# 添加知识
python3 rag_search.py "dummy" --add "密码修改后旧 Token 失效" --metadata "{'type': 'bug', 'title': '改密未踢下线'}"
```

### Python 调用

```python
from service import create_rag_service

rag = create_rag_service()
rag.add_knowledge(["登录功能测试"], [{"type": "case", "title": "登录测试"}])
results = rag.search("登录模块测试", top_k=3)
context = rag.get_context("Token 鉴权", top_k=3)
```

### 文件结构

```
rag-engine/
├── SKILL.md
├── config/
│   └── rag_domain_keywords.json  # 领域词配置（默认进销存）
├── scripts/
│   ├── service.py        # RAGService 主服务
│   ├── query_builder.py  # PRD 抠词（读 config）
│   ├── keywords.py       # 关键词提取
│   ├── reranker.py       # 重排序服务
│   ├── embedding_store.py   # 嵌入存储（FAISS / Milvus）
│   ├── rag_prefetch.py   # 预检索入口
│   └── rag_search.py     # 检索/灌库入口
├── references/
│   └── rag_knowledge.md
└── data/
    └── faiss_index.json  # 向量索引（自动生成）
```

---

## 输出

注入到 Prompt 的知识片段：

```
【RAG 检索结果】
1. [case] 改密后旧会话失效：修改密码后，旧 Token 应失效，调用 /api/profile 返回 401
2. [best_practice] refresh_token 轮换：每次刷新 token 时，旧 token 应立即失效
3. [bug] #892 改密未踢下线：用户改密后旧会话未失效，导致安全漏洞
```
