---
name: rag-engine
description: RAG知识库引擎 — 可执行的检索增强生成，支持 BM25 + 向量检索 + RRF 融合 + Rerank 精排。用例/方案生成前预检索；缺陷/用例可回灌索引。
---

# RAG 引擎

可执行的 RAG 检索增强生成，让 AI 生成用例/方案时引用团队历史经验。

---

## 做 / 不做

| 做 | 不做 |
|----|------|
| 添加知识到知识库 | 管理外部企业知识库系统 |
| 检索相关知识 | 执行测试（走 api-skills） |
| 生成检索上下文（预检索） | 替代 PRD 正文 |

---

## 在 skills 流水线中的位置

```text
PRD / 技术文档
  → rag_prefetch.py（Step 0a / testplan 分析 Step B）
  → output/rag_context*.md
  → @ 注入 testcase-skills/生成 或 testplan-skills/方案
```

| 环节 | 命令 |
|------|------|
| **用例生成前** | `python3 rag-engine/scripts/rag_prefetch.py 需求.md -o output/rag_context.md` |
| **方案分析前** | 同上，`-o output/rag_context_plan.md` |
| **缺陷/经验回灌** | `python3 rag-engine/scripts/rag_ingest.py output/bugs/BUG-xxx.md --type bug` |
| **pytest 失败自动回灌** | 根目录 `conftest.py`（`RAG_BACKFILL=1` 默认开启） |
| **底层检索** | `python3 rag-engine/scripts/rag_search.py "登录模块" --top-k 3` |

约定：`testcase-skills/生成/SKILL.md` **Step 0a** · `testplan-skills/分析/SKILL.md` **Step B**

---

## 快速使用

### 预检索（推荐）

```bash
python3 rag-engine/scripts/rag_prefetch.py examples/tech_mini_seckill.md --top-k 5 --out output/rag_context.md
```

### 入库

```bash
python3 rag-engine/scripts/rag_ingest.py output/bugs/BUG-001.md --type bug
python3 rag-engine/scripts/seed_knowledge.py   # 内置种子知识
```

### 命令行自测

```bash
cd rag-engine/scripts && python3 service.py
```

---

## 检索流水线

```
需求文本 → BM25 → 向量(FAISS) → RRF → Rerank → get_context → 注入 Prompt
```

---

## 文件结构

```
rag-engine/
├── SKILL.md
├── scripts/
│   ├── service.py
│   ├── rag_prefetch.py
│   ├── rag_ingest.py
│   ├── rag_search.py
│   ├── seed_knowledge.py
│   ├── keywords.py
│   ├── reranker.py
│   └── embedding_store.py
└── data/faiss_index.json
```

细则：`testcase-skills/生成/references/rag_knowledge.md`

---

## Python 调用

在 **`skills-专业版V3.0` 包根目录** 下，将 `rag-engine/scripts` 加入路径后调用：

```python
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # 技能包根目录
sys.path.insert(0, str(ROOT / "rag-engine" / "scripts"))

from service import create_rag_service

rag = create_rag_service()
rag.add_knowledge(
    ["登录失败需检查 Token 是否过期"],
    [{"type": "bug", "title": "改密后旧 Token 仍可用"}],
)
results = rag.search("登录鉴权", top_k=3)
context = rag.get_context("秒杀财务 注册 重复用户名", top_k=5)
print(context)
```

等价 CLI：

```bash
python3 rag-engine/scripts/rag_prefetch.py examples/prd_mini_seckill_auth.md -o output/rag_context.md
```

---

## 输出示例

`rag_prefetch.py` 写入的 `output/rag_context.md` 片段：

```markdown
## 知识库检索摘要

检索词：秒杀 登录 注册
命中：3 条

### [bug] 改密后旧 Token 仍可用
- 来源：BUG-20260301-001
- 要点：改密接口应使旧 Token 失效；补 P-02 鉴权用例

### [case] 重复用户名注册
- 要点：须先 POST /api/test/init；预期「用户名已存在」
```

无命中时文档头写：`RAG: 无命中（检索词：…）`，不阻塞后续生成。

---

## 降级策略

| 情况 | 降级 |
|------|------|
| FAISS 为空 | BM25 |
| 完全无命中 | 标注 `RAG: 无命中`，继续纯 PRD 生成 |
