---
name: testplan-analyzer
description: Merges rudimentary PRD with development tech docs into structured test scope, risks, and gaps. Output feeds testplan-skills scheme and plan skills. Use when PRD is incomplete or tech design must drive test strategy.
---

# 需求与技术文档分析

把 **简陋 PRD** 和 **开发技术文档** 合成一份结构化分析：测什么、技术依赖啥、缺啥信息。输出给 **方案** 和 **计划** 用，**不写具体用例**。

平台若支持检索，先按 **`00_知识增强约定.md`** 捞一轮项目文档再往下写。

---

## 1. 啥时候开这个技能

**多半要用**：

- PRD 只有功能列表、没有验收标准；  
- 有架构图、接口设计、部署说明，需要和 PRD 对齐；  
- 多团队并行，方案和计划需要统一语言（模块、优先级、依赖）。

**可以跳过**：

- PRD + 技术文档都已结构化，且用户直接 `@testplan-skills/方案/SKILL.md` 并贴全材料。

---

## 2. 常规干法（六步）

### Step A — 抠输入

确认手头有什么：

| 材料 | 最低要求 |
|------|----------|
| PRD | 功能/模块名、业务目标、哪怕只有 bullet |
| 技术文档 | 架构、接口、数据模型、中间件、部署环境 任一项 |
| **任务表**（平台项目） | `*企微*.xlsx` 或等价：里程碑 + 测试任务行 |
| 约束 | 版本号、上线窗口、人力（可选） |

缺 PRD → 从技术文档 + **任务表**反推业务场景，标「待产品确认」。  
缺任务表 → 从 PRD/技术列里程碑假设，标 T-xx 对齐排期。

### Step B — RAG / 项目文档检索

逻辑复杂、接口相关、历史故障有用、信息明显不够 → **先跑 skills 包内 RAG**：

```bash
python3 rag-engine/scripts/rag_prefetch.py 需求文档.md --out output/rag_context_plan.md
```

分析/方案输出时 `@output/rag_context_plan.md`；无命中标 `RAG: 无命中`。  
外部 Wiki/Confluence 检索见 `00_知识增强约定.md`。

### Step C — 双轨/三轨合并

按 `references/prd_tech_doc_merge.md` 做 **PRD 业务轨** + **技术文档实现轨** 对照表。  
有 Excel 任务表时，加 **任务轨**：`references/enterprise_platform_inputs.md`（来源列：Excel/PRD/技术/测试扩展）。

### Step D — 缺口扫描

按 `references/gap_detection_checklist.md` 逐项打勾；缺项写入 `open_questions`，编号 `T-01`、`T-02`…

### Step E — 风险评分与核心流程

- 按 `references/示例业务_risk_scoring.md` 给 In-Scope 模块打分 → 写入 `risks`。  
- 若有端到端路径，列 `core_flows`（见 `references/core_flows.md`）。

### Step F — 结构化输出

落成 YAML（见 §4），供 **方案** / **计划** 直接引用。

---

## 3. 建议别漏的维度

- **业务**：主流程、角色、状态、规则（PRD 有则写，无则标待确认）。  
- **技术**：服务边界、API、DB/缓存、消息、第三方、部署拓扑。  
- **风险**：钱/库存/权限/并发/一致性 等热区。  
- **非功能**：性能、安全、可用性——PRD 没写但技术文档或合规要求的，在分析里点名。

---

## 4. 输出模板（给方案 / 计划）

```yaml
analysis:
  project: "秒杀财务进销存 v1.1"
  version: "v1.1"
  searched: false
  search_summary: ""

  prd_summary:
    modules: ["认证", "商品", "秒杀", "下单"]
    business_goals: ["支持 admin 配置", "developer 限时下单防超卖"]
    missing_from_prd: ["限购规则细节", "活动状态切换时机"]

  tech_summary:
    stack: ["Flask", "MySQL", "Redis", "JWT"]
    services: ["_api :5000"]
    key_apis: ["POST /auth/login", "POST //orders"]
    dependencies: ["Redis 预热库存", "MySQL 订单持久化"]
    missing_from_tech: ["并发上限 SLA", "Redis 故障降级策略"]

  merge_matrix:
    - prd_item: "developer 下单"
      tech_mapping: "POST //orders + Redis decr"
      test_focus: "P0 主路径 + 防超卖"
      gap: null
    - prd_item: "每人限购 N 件"
      tech_mapping: "（技术文档未说明实现）"
      test_focus: "边界与并发"
      gap: "T-01 限购 N 的值与计数维度"

  risks:
    - module: "下单 + Redis"
      reason: "超卖、并发、库存一致性"
      priority: "P0"
    - module: "JWT 角色"
      reason: "admin/developer 越权"
      priority: "P0"

  scope_hint:
    in_scope: ["认证冒烟", "配置→预热→下单"]
    out_scope: ["采购/销售报表（本轮未改）"]

  open_questions:
    - id: "T-01"
      question: "每人限购件数 N？按用户还是按 IP？"
      owner: "产品"
    - id: "T-02"
      question: "Redis 不可用时是否允许降级到 DB 锁？"
      owner: "开发"

  focus_for_scheme: "策略侧重功能+Redis 一致性；性能只做抽样"
  focus_for_plan: "W2 依赖 Redis 环境；W3 主路径需联调"

  task_table_summary:  # 平台项目可选
    source: ""
    milestones: []
    test_tasks: []
    metrics_from_excel: []
    gaps_vs_test_design: []

  core_flows:  # 平台/E2E 建议写 F1～Fn
    - id: F1
      name: ""
      steps: []
```

完整示例见 `references/示例业务_analysis_output.md`。

---

## 5. 出口闸门

- PRD 与技术文档 **皆无** → 禁止进入方案编写；先列材料清单。  
- `in_scope` 为空 → 禁止进入方案编写。  
- `open_questions` 含 P0 级业务规则且未标 owner → 方案中必须进「待澄清清单」，不得编造验收标准。

---

## 6. 协作接口

| 技能 | 交互 |
|------|------|
| 方案 | 接收 `analysis` YAML → 输出测试方案 |
| 计划 | 接收 `analysis` + 方案摘要 → 输出测试计划 |
| testcase-skills/分析 | 若后续要写用例，可复用本分析的场景部分 |
| testcase-skills/生成 | 方案/计划评审通过后，用 PRD + 技术文档生成用例 |

---

## 参考文档

| 文件 | 用途 |
|------|------|
| `references/prd_tech_doc_merge.md` | PRD 与技术文档双轨合并表 |
| `references/gap_detection_checklist.md` | 简陋 PRD / 缺技术文档时的缺口清单 |
| `references/示例业务_analysis_output.md` | 财务完整分析示例 |
| `references/示例业务_risk_scoring.md` | 模块风险评分 → 策略深度 |
| `references/core_flows.md` | 核心流程树 → 范围/里程碑 |
| `references/enterprise_platform_inputs.md` | Excel 任务表 + 多层平台三轨合并 |

演示输入：

- PRD：`examples/你的PRD.md`  
- 技术文档：`examples/tech_mini_.md`  
- 完整分析示例：`references/示例业务_analysis_output.md`
