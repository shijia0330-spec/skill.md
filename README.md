# 测试技能包 V3.0

> 21 个技能目录 · 133+ 个文档 · 15+ 个可执行脚本 · 企业级 AI测试框架

一套完整的测试技能包，覆盖 API测试、UI 测试、用例设计、数据工厂、性能压测、CI门禁等核心场景。支持 AI 编辑器直接读取，也可命令行执行。

---

## 架构总览

> 六层解耦 · 意图驱动 · 知识增强 · 自愈循环 · 质量门禁

```
┌─────────────────────────────────────────────────────────┐
│              接入层 (AI Editor + CLI)                    │
│  Cursor · Windsurf · VS Code · Shell / generate.sh      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │ SKILL.md │  │ 自然语言 │  │ 命令行   │              │
│  │ 自动读取 │  │ 一句话   │  │ pytest   │              │
│  └──────────┘  └──────────┘  └──────────┘              │
└────────────────────────┬────────────────────────────────┘
                         │ 引用 Skill · @路径 · 话术
┌────────────────────────▼────────────────────────────────┐
│              编排层 (intent-router/)                     │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐          │
│  │ 短语匹配   │ │ Skill 路由 │ │ Prompts    │          │
│  │ Phrases    │ │ mapping    │ │ 话术库     │          │
│  └────────────┘ └────────────┘ └────────────┘          │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│        知识与规范层 (rag-engine/ + templates/)            │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐         │
│  │ RAG 引擎   │ │ 需求建模   │ │ 模板样例   │         │
│  │ BM25+向量  │ │ Scope 锚定 │ │ 24模板·6例 │         │
│  │ RRF+Rerank │ │            │ │            │         │
│  └────────────┘ └────────────┘ └────────────┘         │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│           技能矩阵层 (21 技能目录 · Skill Matrix)         │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐         │
│  │ 用例设计   │ │ API 测试   │ │ UI 测试    │         │
│  │ 8维矩阵    │ │ 依赖图自愈 │ │ Playwright │         │
│  │ N/B/T/E... │ │ 变量池     │ │ Web七种定位│         │
│  └────────────┘ └────────────┘ └────────────┘         │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐         │
│  │ 数据工厂   │ │ 性能压测   │ │ 缺陷分析   │         │
│  │ faker注入  │ │ JMeter+k6  │ │ 指纹去重   │         │
│  │ 注入·清理  │ │ 阶梯并发   │ │ 根因分析   │         │
│  └────────────┘ └────────────┘ └────────────┘         │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐         │
│  │ 测试计划   │ │ 移动端     │ │ 缺陷同步   │         │
│  │ test-plan  │ │ Appium     │ │ defect-sync│         │
│  └────────────┘ └────────────┘ └────────────┘         │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│              引擎层 (codegen/ + pytest)                  │
│  ┌──────────────────────────────────────────┐          │
│  │ Markdown Spec → generate.sh → pytest     │          │
│  │ 分析 → 规划 → 执行 → 自愈               │          │
│  └──────────────────────────────────────────┘          │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐         │
│  │ CodeGen    │ │ 变量池     │ │ 依赖图     │         │
│  │ Spec 解析  │ │ VariablePool│ │ DAG 推断   │         │
│  └────────────┘ └────────────┘ └────────────┘         │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│              治理层 (ci-gate/)                            │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐         │
│  │ CI Gate    │ │ Quality    │ │ Auto       │         │
│  │ 四维度阈值 │ │ 四环境策略 │ │ Rollback   │         │
│  │ P95·覆盖率 │ │ dev/test/  │ │ 不达标回滚 │         │
│  └────────────┘ └────────────┘ └────────────┘         │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│                  产出层 (output/)                         │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐         │
│  │ pytest脚本 │ │ 用例文档   │ │ 测试报告   │         │
│  │ output/*.py│ │ *.md/xmind │ │ HTML·缺陷  │         │
│  └────────────┘ └────────────┘ └────────────┘         │
└─────────────────────────────────────────────────────────┘
```

### 核心工作流 · Analyze → Plan → Execute → Heal

```
┌─────────────────────────────────────────────────────────┐
│              自愈循环 (Self-Healing Loop)                │
│  ┌──────────────────────────────────────────┐          │
│  │ ① 分析 → ② 规划 → ③ 执行 → ④ 自愈       │          │
│  │ analyze → plan → execute → heal          │          │
│  └──────────────────────────────────────────┘          │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐         │
│  │ 分析子图   │ │ 规划子图   │ │ 自愈子图   │         │
│  │ 文档解析   │ │ 依赖图     │ │ 401刷新    │         │
│  │ 意图识别   │ │ 8维矩阵    │ │ 退避重试   │         │
│  │ 接口推断   │ │ 数据方案   │ │ 定位兜底   │         │
│  └────────────┘ └────────────┘ └────────────┘         │
└────────────────────────┬────────────────────────────────┘
                         │
          ┌──────────────┴──────────────┐
          │                             │
┌─────────▼──────────┐    ┌─────────────▼────────────┐
│ RAG 知识注入         │    │ CI Gate 四维度门禁        │
│ BM25 → 语义向量 →     │    │ P95 · 漏洞 · 覆盖率 ·    │
│ RRF → Rerank        │    │ 通过率 → pass / rollback │
│ ~3000 token 裁剪    │    └─────────────┬────────────┘
└─────────────────────┘                  │
                         ┌───────────────┴───────────────┐
                         │                               │
                  ┌──────▼──────┐               ┌────────▼────────┐
                  │ ✓ 发布/合并  │               │ 自动回滚 → 重分析 │
                  └─────────────┘               └─────────────────┘
```

| 层级 | 职责 | 关键组件 |
|------|------|----------|
| 接入层 | 人机交互入口 | Cursor / Windsurf / VS Code / CLI |
| 编排层 | 意图识别与路由 | `intent-router` · `prompts/` |
| 知识层 | 上下文增强与规范沉淀 | `rag-engine` · `requirement-modeling` · `templates/` |
| 技能层 | 领域能力矩阵（20 目录） | API / UI / 用例 / 数据 / 压测 / 缺陷 … |
| 引擎层 | Spec → 可执行代码 | `codegen/` · `generate.sh` · pytest |
| 治理层 | 质量门禁与回滚 | `ci-gate` · 四环境阈值策略 |
| 产出层 | 交付物与报告 | `output/` · HTML 报告 · 缺陷草稿 |

---

## 快速开始

### 方式一：AI 编辑器（推荐）

1. 解压到项目根目录
2. 在 Cursor / Windsurf / VS Code 中打开
3. AI 自动读取 `SKILL.md`，开始生成测试脚本

### 方式二：命令行

```bash
# RAG知识库检索
cd rag-engine/scripts
python3 rag_search.py "登录模块测试" --top-k 3

# CI门禁检查
cd ci-gate/scripts
python3 ci_gate.py --env prod --metrics metrics.json

# 生成测试脚本
./generate.sh templates/api_smoke.md
cd output && python3 -m pytest api_smoke.py -v
```

---

## 技能目录

**状态说明**（对外交付口径，与各 `SKILL.md` 一致）：

| 状态 | 含义 |
|------|------|
| **可执行** | 有 Python/Shell 脚本；`./verify_all.sh` 或 README 命令可本地验证 |
| **需联调** | Codegen/脚本已验；真实 HTTP / 浏览器 / MySQL / Appium / 目标站点需用户自备环境 |
| **AI 辅助** | 依赖 AI 编辑器读取 `SKILL.md` 产出用例/方案/报告；无独立 CLI |
| **规划中** | 仅 Skill 文档或 roadmap，暂无一键可执行脚本 |

| 分类 | 技能 | 用途 | 状态 |
|------|------|------|------|
| **API测试** | `api-skills/` | 分析→规划→执行→自愈（依赖图、变量池、故障自愈） | 可执行 + AI 辅助（分析/规划） |
| **UI 测试** | `UI-skills/` | Playwright + Web 七种定位 + `locator_healer.py`（generate 自动集成） | 可执行；L2.5 Scrapling / L3 AI 定位 **规划中** |
| **移动端** | `mobile-skills/` | Appium 分析→规划→执行→转化 | 需联调（codegen 已验；真机/模拟器/Appium Server） |
| **用例设计** | `testcase-skills/` | 8 维度矩阵（N/B/T/E/A/D/I/S）+ 评审 + step6 门禁 | AI 辅助；step6 校验 **可执行** |
| **测试方案** | `testplan-skills/` | 分析→方案→计划→评审（四段流水线） | AI 辅助 |
| **测试计划** | `test-plan/` | 单 SKILL 快速出测试方案/计划 | AI 辅助 |
| **用例数据** | `testcase-data-generator/` | 评审后用例→数据方案→SQL/shell/Python | AI 辅助 |
| **数据工厂** | `data-factory/` | 声明式 MySQL/CSV 造数 + pytest setup 铺底 | 可执行；**环境重置** **规划中** |
| **性能压测** | `load-testing/` | k6 / JMeter / Locust codegen + 报告四阶段 | 可执行（脚本生成）；压测报告 **AI 辅助** |
| **专项测试** | `special-testing/` | Locust 冒烟入口；视觉回归 spec | Locust/视觉回归 **可执行**；安全扫描 / UI 规范审查 / 代码质量门禁 **规划中** |
| **全站截图** | `screenshot-skills/` | 批量页面截图 → manifest + 索引 | 需联调（脚本可执行；需 Playwright + 目标 URL/HTML） |
| **需求建模** | `requirement-modeling/` | Scope 锚定、测什么/不测什么 | AI 辅助 |
| **RAG知识库** | `rag-engine/` | BM25 + 向量 + RRF + Rerank（本地可跑） | 可执行 |
| **CI门禁** | `ci-gate/` | 四维度阈值 + 自动回滚 | 可执行 |
| **缺陷报告** | `bug-reporter/` | 缺陷模板 + pytest 失败草稿 + 指纹去重 | 可执行；Chat 补全 **AI 辅助** |
| **失败分析** | `defect-analysis/` | 5 大类失败模式 + 置信度分级 | 可执行；深析 **AI 辅助** |
| **进度报告** | `progress-reporter/` | pytest 会话汇总 → `output/reports/` | 可执行 |
| **意图路由** | `intent-router/` | 用户说法 → 默认 Skill（`mapping.yaml`） | 可执行 |
| **缺陷同步** | `defect-sync/` | 草稿 → 禅道/云效/自研 Webhook | 可执行（dry-run 已验）；真实推送 **需联调**（配 Token） |
| **生成引擎** | `codegen/` | Markdown spec → pytest / Playwright / k6 / JMeter / Appium | 可执行 |
| **模板** | `templates/` | 19 个 codegen spec + 5 个用例/需求文档 | 配套资源 |
| **示例** | `examples/` | PRD / 用例 / spec / 缺陷 / 测试计划黄金样例 | 配套资源 |
| **话术** | `prompts/` | 常用 AI 编辑器话术 | 配套资源 |

> **演示后端**：秒杀财务示例系统 `seckill_finance_system`（进销存演示项目）与技能包**分开发放**，**不在本 zip 内**。**联系交付方获取**。无后端时仍可用 `./verify_all.sh` + `pytest --collect-only` 验收生成链路。

---

## 核心能力

### 1. 依赖图推断（4 种策略）

```
POST /login
  ├──→ GET /users/me          (认证链)
  ├──→ POST /orders           (认证链)
  │     └──→ GET /orders/{id} (路径参数引用)
  └──→ DELETE /orders/{id}    (认证链 + 路径参数引用)
```

### 2. 变量池 + 链式执行

```json
// 步骤1 登录 → 提取 token
{"data": {"token": "***", "user_id": 42}}

// 步骤2 创建订单 → 自动注入 ${token}
POST /api/orders
Headers: { "Authorization": "Bearer ${token}" }
Body:    { "user_id": "${user_id}", "sku": "BOOK-001" }
```

### 3. 故障自愈（5 类策略）

| 故障 | 策略 | 重试 | 延迟 |
|------|------|------|------|
| 401 | 刷新 Token | 最多 5 次 | 0.5s 固定 |
| 500 | 指数退避 | 最多 3 次 | 1s × 2^attempt + Jitter |
| 429 | 等待后重试 | 最多 3 次 | 2^attempt + Jitter |
| 超时 | 调整超时 | 最多 2 次 | 每次 +10s |
| 连接失败 | 指数退避 | 最多 3 次 | 2s × 2^attempt + Jitter |

### 4. UI 自愈定位（Web · 七种 Playwright 策略）

**仅浏览器 E2E**（Playwright）。App 端见 `mobile-skills/`。

```
testid → role+name → label → placeholder → id → text → css → L2 DOM 推断
```

| # | 策略 | API |
|---|------|-----|
| 1 | data-testid | `get_by_test_id` |
| 2 | role + name | `get_by_role` |
| 3 | label | `get_by_label` |
| 4 | placeholder | `get_by_placeholder` |
| 5 | id | `locator("#id")` |
| 6 | text | `get_by_text` |
| 7 | CSS | `locator(".class")` |

可执行：`UI-skills/执行/scripts/locator_healer.py`（Web L1 + L2 DOM 推断）。  
**`./generate.sh` 生成的 UI 脚本已自动调用 healer**（`fill_with_heal` / `click_with_heal`），`UI_SELF_HEAL=0` 可关闭。  
完整说明：`UI-skills/执行/references/locator_strategy_web.md`

**规划中（尚未接入 codegen）**：L2.5 Scrapling 服务、L3 AI 选元素（`UI_ENABLE_AI_LOCATOR=0`）。见 `UI-skills/执行/references/locator_degradation_chain.md`。

### 5. 8 维度用例矩阵

N（正常）/ B（边界）/ T（类型）/ E（异常）/ A（权限）/ D（依赖）/ I（幂等）/ S（安全）

### 6. RAG知识库（可执行）

```
需求文本
  → BM25 关键词检索
  → 向量语义检索（FAISS / Milvus）
  → RRF 融合（两路排名加权）
  → Rerank 精排（多信号打分）
  → ContextOptimizer 裁剪（~3000 token）
  → 注入 Prompt
```

### 7. CI门禁（可执行）

| 维度 | 开发环境 | 测试环境 | 生产环境 |
|------|----------|----------|----------|
| P95 响应时间 | ≤ 1000ms | ≤ 800ms | ≤ 500ms |
| 严重漏洞 | ≤ 2 | ≤ 0 | 0 |
| 代码覆盖率 | ≥ 60% | ≥ 80% | ≥ 90% |
| 测试通过率 | ≥ 80% | ≥ 95% | ≥ 98% |

---

## 文件结构

```
skills-专业版V3.0/
├── README.md              # 本文件（含技能状态表）
├── START_HERE.md          # 快速上手
├── STRUCTURE.md           # 目录与能力状态
├── LICENSE.txt            # 对外使用许可
├── verify_all.sh          # 一键验收
├── pack_external.sh       # 对外打 zip（排除 output/）
├── generate.sh            # 一键生成脚本
├── run_pytest.sh          # pytest 入口
├── conftest.py            # pytest 钩子
├── .env.example           # 环境变量示例
│
├── api-skills/            # API测试（分析→规划→执行→自愈）
├── UI-skills/             # UI 测试（分析→规划→执行→自愈）
├── testcase-skills/       # 用例设计（分析→规划→生成→评审）
├── testplan-skills/       # 测试方案四段流水线
├── test-plan/             # 快速单页方案/计划
├── testcase-data-generator/  # 用例驱动数据设计（AI 辅助）
├── data-factory/          # 数据工厂（声明式造数）
├── load-testing/          # 性能压测（k6/JMeter/Locust）
├── special-testing/       # Locust 冒烟、视觉回归、专项 roadmap
├── screenshot-skills/     # 全站截图
├── rag-engine/            # RAG知识库（可执行）
├── ci-gate/               # CI门禁（可执行）
├── bug-reporter/          # 缺陷报告
├── progress-reporter/     # pytest 进度汇总（output/reports/）
├── defect-analysis/       # 失败分析
├── mobile-skills/         # 移动端测试
├── requirement-modeling/  # 需求建模
├── intent-router/         # 意图路由
├── defect-sync/           # 缺陷同步（禅道/云效/自研）
│
├── templates/             # 24 个文件：19 个 codegen spec + 5 个用例/需求文档
├── codegen/               # 生成引擎
├── examples/              # 示例（PRD/用例/spec/缺陷/测试计划）
├── prompts/               # 常用话术
│
└── output/                # 生成产物（运行时产生；**勿打入交付 zip**）
```

---

## templates/ 目录说明

`templates/` 共 **24** 个 Markdown 文件，分两类：

| 类型 | 数量 | 用途 | 能否 `./generate.sh` |
|------|------|------|------------------------|
| **codegen spec** | **19** | 带 YAML frontmatter（`kind: api_pytest` 等），生成 pytest / Playwright / Locust | 支持 |
| **用例/需求文档** | **5** | 给 `@testcase-skills/生成` 等 Skill 阅读的 PRD / 用例样例 | 不支持（无 frontmatter，预期失败） |

**不参与 generate 的 5 个文档**（排除列表见 `codegen/excluded_doc_templates.txt`，`selftest_bundle.py` 自测同步读取）：

| 文件 | 说明 |
|------|------|
| `需求文档.md` | 演示用 PRD 样例 |
| `测试用例-需求文档.md` | 与 PRD 配套的用例文档样例 |
| `testcase_generation.md` | 用例生成操作指南（给 AI 看，不是 spec） |
| `testcase_template.md` | 用例生成任务单模板 |
| `testcase_from_bug.md` | 从缺陷反推用例的 AI 输入模板 |

对 **19 个 spec** 批量自测：`python3 codegen/selftest_bundle.py`（已自动跳过上述 5 个）。

---

## 环境要求

| 用途 | 依赖 | 命令 |
|------|------|------|
| 基础功能 | Python 3.8+ | `pip install PyYAML` |
| API测试 | pytest + requests | `pip install pytest requests` |
| UI 测试 | pytest-playwright | `pip install pytest-playwright && playwright install chromium` |
| 性能测试 | locust | `pip install locust` |
| RAG知识库 | 无（FAISS 内置） | 无需额外依赖 |
| CI门禁 | 无 | 无需额外依赖 |

---

## 验证方法

### 一键验收（推荐）

```bash
chmod +x verify_all.sh generate.sh run_pytest.sh
./verify_all.sh              # codegen + RAG + CI + collect-only
./verify_all.sh --with-api   # 有 seckill_finance_system 时再跑 API 冒烟
```

Docker 部署后端时请先：

```bash
export TEST_BASE_URL=http://your-server:5001
export TEST_USERNAME=admin TEST_PASSWORD=admin123
curl -X POST "$TEST_BASE_URL/api/test/init" -H "Content-Type: application/json" -d '{}'
```

### 1. 生成脚本验证

```bash
chmod +x generate.sh
./generate.sh templates/api_smoke.md
cd output && python3 -m pytest api_smoke.py --collect-only -q
# 应看到: N tests collected（无报错即可；条数随 templates/api_smoke.md 扩展，以终端为准）
```

### 2. RAG 引擎验证

```bash
cd rag-engine/scripts
python3 service.py
# 应看到: RAG 服务测试通过
```

### 3. CI 门禁验证

```bash
cd ci-gate/scripts
python3 ci_gate.py --env prod
# 应看到: 通过 或 不通过（根据指标）
```

### 4. 缺陷同步验证

```bash
cd defect-sync/scripts
python3 defect_sync.py push ../output/bugs/ --platform custom --dry-run --confirm
```

### 5. 进度报告验证

```bash
PROGRESS_REPORT=1 DEFECT_DRAFTS=0 ./run_pytest.sh output/api_smoke.py -q --tb=no
# 终端末尾应见 [progress-report]；产物: output/reports/progress.md / progress.json
```

---

## 使用示例

### API测试

```text
@api-skills/执行/SKILL.md

帮我测 POST /api/login，admin/admin123，错误密码要 401
```

### 用例生成

```text
@testcase-skills/生成/SKILL.md
@templates/需求文档.md

生成测试用例，输出 output/login_testcases.md
```

生成 Skill **默认 Step 0a 会先 RAG 检索**（`testcase-skills/生成/scripts/rag_prefetch.py`），再按 PRD + 覆盖矩阵写点。

### 数据注入

```text
@data-factory/执行/SKILL.md

帮我生成 100 个用户和 500 个订单的测试数据
```

### 压测脚本

```text
@load-testing/执行/SKILL.md

帮我生成 k6 压测脚本（默认引擎），阶梯并发 10→100，持续 10 分钟
BASE_URL=http://your-server:5001，对齐 seckill openapi
```

Locust 冒烟：`./generate.sh templates/perf_test.md`

### 压测报告（含截图 → HTML）

```text
@load-testing/报告/SKILL.md

（粘贴 JMeter 聚合报告截图）
请分析瓶颈并输出 HTML 报告到 output/perf_report.html
```

---

## 统计数据

| 指标 | 数量 |
|------|------|
| 技能目录 | 21 个 |
| Markdown 文件 | 133 个 (375.8 KB) |
| Python 脚本 | 15 个 (150.4 KB) |
| 目录结构 | 72 个 |
| 内置模板 | 24 个（19 spec + 5 文档） |
| 示例文件 | 6 个 |

---

## 对外打包说明

交付 zip 前建议：

1. **不要打包** `output/`、`__pycache__/`、`.pytest_cache/`、`.heal_cache/`、`jmeter.log`（见 `.gitignore`；`pack_external.sh` 已自动排除）
2. 在干净目录执行 `./verify_all.sh`，确认 **失败: 0**
3. 可选：有演示后端时追加 `./verify_all.sh --with-api`
4. 配套 **`skills3.0使用手册/`**（包外手册）+ 包内 `README.md` / `START_HERE.md`
5. 演示后端 `seckill_finance_system`（进销存）**联系交付方获取**，非本 zip 内容
6. 一键打 zip：`chmod +x pack_external.sh && ./pack_external.sh`（先跑 `verify_all.sh`，再排除 `output/` 与缓存；产出 `../skills-V3.0-external-YYYYMMDD.zip`）

---

## 适合谁？

- 想提升测试效率的测试工程师
- 想用 AI 改造测试流程的 SDET
- 需要企业级测试框架的团队
- 想学习现代测试方法的开发者

---

## 版本历史

| 版本 | 日期 | 更新内容 |
|------|------|----------|
| **skills V3.0** | 2026-06 | 对外正式版：21 技能目录、defect-sync、`verify_all.sh`、openapi 对齐（seckill_query_tests 等）、RAG / CI 门禁 / 自愈 / 8 维用例矩阵 |

> 对外交付统一品牌 **skills V3.0**；更早内部迭代不再单独列版本号。

---

## 许可证

本包采用**商业授权**，完整条款见根目录 **`LICENSE.txt`**（含使用范围、禁止再分发、演示后端获取方式等）。未经授权不得转售或公开源码仓库。

---

## 反馈与支持

- **演示后端（进销存）**：`seckill_finance_system` 不在本 zip 内，**联系交付方获取**。
- 技能包使用问题、授权与更新：欢迎提交 Issue 或联系交付方。
