---
name: testcase-analyzer
description: 将含糊需求拆成可测场景、边界与规则清单；复杂需求可先 RAG。输出供 testcase-skills/生成 使用。
---

# 需求分析

将用户含糊的一句话或 PRD 拆成：**可测场景、边界、规则清单**；平台若支持检索，先按 **`00_知识增强约定.md`** 捞一轮项目文档再往下写。

**与用例生成的关系**：本 Skill 对应 **Step 0b（需求预分析）**；**RAG 检索已在 `testcase-skills/生成` Step 0a 默认执行**。若已 `@testcase-skills/生成/SKILL.md` 并贴全 PRD，可在生成环节内完成预分析，本 Skill 可跳过。

---

## 1. 啥时候开这个技能

**多半要用**：只有功能名、规则复杂、要对接口、要看历史用例。  

**可以跳过**：需求写得很死（前置、步骤、期望都齐），或只有一个极简无分支操作；或直接进入「生成」Skill 做 Step 0。

---

## 2. 常规干法（四步）

1. **抠输入**：模块名、测全量还是局部、能不能提炼检索词。  
2. **要不要搜库**：逻辑复杂、接口相关、历史数据有用、信息明显不够 → 建议搜。  
3. **怎么搜**（生成 Skill Step 0a 同款，须优先执行）：

```bash
python3 testcase-skills/生成/scripts/rag_prefetch.py <需求.md> --top-k 10 \
  --out output/rag_context_<模块>.md
```

或直接指定检索词：`python3 testcase-skills/生成/scripts/rag_prefetch.py --query "订单支付 验收标准" --top-k 10`

4. **落成结构化结果**：场景列表、边界点、规则列表；不知道的就列 `open_questions`。

**结构保持**：分析输出须能映射回 PRD 标题，见 `testcase-skills/生成/references/structure_preservation.md`。

**核心流程**：若 PRD 含端到端旅程，先列核心流程树，见 `../生成/references/core_flows.md`。

---

## 3. 建议别漏的维度

- **数据**：空、超长、特殊字符、格式错、业务黑名单。  
- **状态**：能转哪些状态、非法跳转拦不拦。  
- **串联**：谁依赖谁返回的字段；异步、回调、第三方挂了咋办。  
- **非功能**：团队若关心性能、安全、兼容，在这里点名，别全塞进功能步骤里。

---

## 4. 输出里建议带啥

- 搜没搜库、搜到啥级别摘要。  
- 场景 / 边界 / 规则，各自标一下类型。  
- 给 **生成** 环节的一句话焦点。

---

## 5. 搜不到咋办

换关键词、加大 `top_k`、换模式；还不行就问用户要文档；用户也没有就写假设并在评审单上标红。

---

## 6. 举几个口头例子

- 只甩一句「订单支付」→ 先搜工作流和金额规则，再列场景。  
- 「登录接口」→ 搜接口定义和鉴权方式，把参数级边界列出来。  
- 需求本身已贴全 → 可直接结构化，省检索。

## 7. 输出模板（给 **生成** 环节的输入）

```yaml
analysis:
  feature: "订单支付"
  searched: true
  search_summary: "从知识库检索到 8 条相关规则"
  scenarios:
    - name: "正常支付"
      type: "happy_path"
      priority: "P0"
    - name: "余额不足"
      type: "boundary"
      priority: "P1"
  boundaries:
    - "金额为 0 时支付是否成功"
    - "并发支付同一订单"
  open_questions:
    - "支付超时时间是多少？"
  focus_for_generator: "重点是余额不足和超时场景，正常流程走一遍即可"
  preserve_prd_headings: true   # 生成时必须保持 PRD 标题层级
```

---

## 流水线位置

```text
PRD / 需求文档
  →（可选）testcase-skills/规划
  → testcase-skills/分析（本 Skill · Step 0b）
  → testcase-skills/生成（Step 0a RAG 已在生成内默认执行）
  → testcase-skills/评审
  → UI精简 / OpenAPI 自动化 / 手工
```

| 环节 | Skill | 本 Skill 产出 |
|------|-------|----------------|
| 规划 | `testcase-skills/规划` | 测哪些模块 |
| **分析** | **本 Skill** | 场景/边界/规则 YAML 或 md 摘要 |
| 生成 | `testcase-skills/生成` | `output/*_testcases.md` |
| 评审 | `testcase-skills/评审` | 评审结论 |

**何时跳过本 Skill**：PRD 已结构化且 `@testcase-skills/生成` 一次贴全；或只有 OpenAPI 走 `api-skills` 流水线、无功能长文。

---

## 分析完成自检

交付给 **生成** 前勾选：

- [ ] 已执行 RAG（或文档信息将标「无命中」）
- [ ] 场景列表覆盖 PRD 主路径 + 关键异常
- [ ] 边界/规则与 PRD 阈值一致，未知项进 `open_questions`
- [ ] 输出可映射回 PRD 标题（`structure_preservation.md`）
- [ ] 含核心流程时已有流程树或引用 `core_flows.md`
- [ ] `focus_for_generator` 已写（生成环节优先写什么）

---

## 参考文档

| 文件 | 用途 |
|------|------|
| `references/seckill_finance_scenario_table.md` | 场景分析固定表头 |
| `../生成/references/structure_preservation.md` | PRD 标题层级 |
| `../生成/references/core_flows.md` | 核心流程树 |

演示输入：`examples/prd_mini_seckill_auth.md`
