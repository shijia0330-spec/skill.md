---
name: test-plan-writer
description: Produces operational test plans with schedule, milestones, resources, and deliverables from scheme output and analysis. Use when 测试计划 document is needed for execution and sign-off.
---

# 测试计划 — 何时测、谁测、交什么

从 **分析输出** + **测试方案**（已定稿或草案），生成 **测试计划**（`*_testplan.md`）。回答 **什么时候测、谁负责、交什么产物、怎么报缺陷**；**不写用例步骤**。

---

## 快速使用

```text
@testplan-skills/方案/SKILL.md  （或 output/*_testscheme.md）
@testplan-skills/计划/SKILL.md
@analysis.yaml（可选）
输出 output/财务_testplan.md
```

---

## 1. 适用边界

**宜用**：

- 方案已有 In-Scope 与策略，需要排期与分工；  
- 多角色（测试/开发/运维）需要对齐里程碑；  
- 发布窗口明确或需要反推测试窗口。

**可跳过**：

- 单人半日验证且不需要计划文档。

**前置**：建议先有 **方案**；若仅有分析 YAML，计划可出 **草案**，里程碑标「待方案定稿后刷新」。

### 与 testcase-skills/规划 的分工

| 文档 | 何时用 |
|------|--------|
| `testcase-skills/规划` | 迭代内 **轻量** 范围+节奏（站会、口头对齐） |
| **本 Skill（计划）** | **正式** 测试计划：签字、审计、多角色里程碑 |
| `testplan-skills/方案` | 测什么、怎么测（策略文档） |

同一迭代可只出规划；**内部使用或发布评审** 应出本包 **方案+计划**。二者范围冲突时以 **方案** 为准。

---

## 2. 六步工作流

### Step 1 — 输入对齐

读取：分析 YAML、方案（至少 §2 范围、§3 策略、§7 准出）。  
提取：版本、In-Scope 模块、P0 模块、环境依赖、T-xx。

### Step 2 — 目标与范围引用

计划 §1～2 **引用** 方案，不重复长篇；只补充 **计划特有** 信息（上线日、测试窗口）。

### Step 3 — 里程碑与进度

按 `references/milestone_patterns.md` 将 P0 模块拆成 **周/冲刺** 表格。  
- /单模块：模式 A/B/C（W1～W4）。  
- **多层平台**：模式 D（M0 / M1-S1～S4 / M2 / M3 / M4），见 `platform_plan_extensions.md`。  
依赖关系：例如「M1-S2 REST 依赖 M1-S1 商品库存 API」。

### Step 4 — 资源与职责

按 `references/resource_role_matrix.md` 填 RACI 或简化职责表。

### Step 5 — 交付物与缺陷流程

交付物：方案、计划、**分层子计划**（平台）、用例、执行报告、Golden/专项数据、评审签字表。  
缺陷：严重级别、响应 SLA（未知写 T-xx 或澄清会结论）；无禅道时可写 Excel 模板（见 `platform_plan_extensions.md` §5）。

### Step 5b — 平台计划扩展

加载 `references/platform_plan_extensions.md`：§2.1 用例分期引用、§5.5 分层计划、§9.1 自动化路线图、三层同步会、人力表。

### Step 6 — 沟通与自检

周会/日报机制；文末 **计划自检表**（模板 §8）。

---

## 3. 输出路径

默认：`skills-专业版V2.0/output/[模块名]_testplan.md`

正文结构：**必须**遵循 `references/plan_template.md`。

---

## 4. 与方案的一致性

| 方案内容 | 计划必须一致 |
|----------|--------------|
| In/Out Scope | §2 引用一致 |
| P0 模块 | 里程碑前几周必须覆盖 |
| 准出标准 | 最后里程碑退出准则 ≥ 方案 §7 |
| T-xx | 计划风险/依赖节列出 |

不一致 → 计划文首加「⚠️ 与方案 v__ 存在差异：…」

---

## 5. 出口闸门

| 条件 | 动作 |
|------|------|
| 无里程碑表 | 禁止交付 |
| 无职责分配（至少测试负责人） | 禁止交付 |
| 无交付物清单 | 禁止交付 |
| 最后里程碑无退出准则 | 禁止交付 |

---

## 6. 协作接口

| 技能 | 交互 |
|------|------|
| 方案 | 输入范围、策略、准出 |
| 分析 | 补充 open_questions、环境依赖 |
| 评审 | 计划与方案一起评审 |
| testcase-skills/生成 | 里程碑 Wn 可映射用例批次 |
| testcase-skills/规划 | 轻量排期；正式计划用 **本 Skill**（见 §1 分工表） |

---

## 参考文档

| 文件 | 用途 |
|------|------|
| `references/plan_template.md` | 测试计划正文模板（必用） |
| `references/milestone_patterns.md` | 里程碑切法与依赖 |
| `references/resource_role_matrix.md` | 角色职责 |
| `references/示例业务_plan_example.md` | 财务节选 |
| `references/platform_plan_extensions.md` | 平台型计划扩展 |
| `../../examples/项目_testplan.md` | 黄金样例 |
