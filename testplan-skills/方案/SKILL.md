---
name: test-scheme-writer
description: Produces test scheme documents (scope, strategy, methods, environment, entry/exit) from PRD and tech doc analysis. Use when a formal 测试方案 is needed before test planning or case design.
---

# 测试方案 — 测什么、怎么测

从 **分析输出** + PRD + 技术文档，生成正式的 **测试方案**（`*_testscheme.md`）。回答 **测什么、怎么测、用什么环境、什么时候算测完**；**不写逐步用例**。

---

## 快速使用

```text
@testplan-skills/分析/SKILL.md   （或已完成的 analysis YAML）
@testplan-skills/方案/SKILL.md
@简陋PRD.md
@技术设计.md
输出 output/财务_testscheme.md
```

---

## 1. 适用边界

**宜用**：

- 新模块/新版本上线前需要评审的测试方案；  
- PRD 简陋，需要靠技术文档补测试策略；  
- 多类型测试（功能/接口/性能/安全）需要统一口径。

**可跳过**：

- 极小改动且范围在工单写死，且不需要对外方案文档。

---

## 2. 七步工作流

### Step 1 — 读分析 & 材料

- 若有 `testplan-skills/分析` 的 YAML，直接引用。  
- 若无，在本 Skill 内做轻量合并（见分析 Skill Step C～D），不重复长篇分析。

### Step 2 — 范围定稿

- In-Scope / Out-of-Scope（来自 `analysis.scope_hint`，可微调）。  
- 与 PRD 标题或模块列表对齐；**平台项目**与 Excel 测试任务对照，见 `references/scheme_template.md` §2。  
- 追溯表加 **来源** 列；测试扩展项（如秒杀 P99 阈值）须标「测试扩展」。

### Step 2b — 平台扩展（秒杀模块（认证/商品/秒杀/财务） 或多里程碑时）

加载 `references/platform_scheme_extensions.md`：

- §1.4 用例资产 vs 分期执行 + P3/P4 豁免  
- §2.4 核心流程 F1～Fn  
- §4.2～4.4 专项（RAG/Golden、性能、网关、DPA、有限 HA）  
- §7 分阶段准出（M1 非阻塞 + M4 硬性）  
- 附录 A.1 澄清会、附录 H Excel 追溯  

切片参照：`references/platform_slices.md`。

### Step 3 — 测试策略

- 按 `references/test_strategy_matrix.md` 为每个模块选测试 **类型** 与 **深度**。  
- 标明：功能 / 接口 / 集成 / 回归 / 性能 / 安全 / 兼容性 是否做、做到哪一档。  
- 有 OpenAPI 时：加载 `references/openapi_scope.md`，更新 §2.3 与 §3.2。  
- PRD/技术触发 NFR 时：加载 `appendix_nfr_security.md`、`appendix_nfr_performance.md` 写附录摘要。

### Step 4 — 方法与工具

- 手工 / Postman / pytest / 压测工具 — 与 monorepo 的 `api-skills`、`generate.sh` 对齐。  
- 见 `references/environment_and_tools.md`、`references/generate_sh_alignment.md`（准出 ↔ 模板 ↔ 命令）。

### Step 5 — 环境与数据

- 环境拓扑（dev/test/staging）、依赖（MySQL、Redis…）、测试数据策略（造数/脱敏/回滚）。

### Step 6 — 准入 / 准出

- 按 `references/entry_exit_criteria.md` 写 **可观测** 标准；禁止「差不多测完」。  
- `T-xx` 未澄清项：准出标准中对应条目标「待 T-xx 确认后生效」；澄清会结论写 **附录 A.1**（`t_clarification_workflow.md`）。  
- **平台/大用例库**：§7 分 M1 与 M4 两套准出 + M1 非阻塞项（`staged_exit_criteria.md`）。

### Step 7 — 风险与自检

- 风险表 + 缓解；模板 §9 **方案自检** + `references/scheme_quality_checklist.md` **质量自检（§10）**。

---

## 3. 输出路径

默认：`skills-专业版V2.0/output/[模块名]_testscheme.md`

正文结构：**必须**遵循 `references/scheme_template.md`。

---

## 4. 示例切片

- 节选：`references/示例业务_scheme_example.md`  
- **黄金样例（纠偏用）**：`examples/项目_testscheme.md`

---

## 5. 出口闸门

| 条件 | 动作 |
|------|------|
| In-Scope 为空 | 禁止交付 |
| 无测试策略节（各模块至少一行） | 禁止交付 |
| 无准出标准 | 禁止交付 |
| 阻塞性 T-xx ≥3 且无文首警告 | 禁止交付 |

---

## 6. 协作接口

| 技能 | 交互 |
|------|------|
| 分析 | 输入 `analysis` YAML |
| 计划 | 输出方案摘要（范围、策略、里程碑建议）供排期 |
| 评审 | 方案评审通过后，计划 Skill 可开工 |
| testcase-skills/生成 | 方案定稿后，可进入用例编写 |

---

## 参考文档

| 文件 | 用途 |
|------|------|
| `references/scheme_template.md` | 测试方案正文模板（必用） |
| `references/test_strategy_matrix.md` | 模块 × 测试类型决策 |
| `references/entry_exit_criteria.md` | 准入准出写法 |
| `references/environment_and_tools.md` | 环境、工具、数据 |
| `references/示例业务_scheme_example.md` | 财务节选 |
| `references/openapi_scope.md` | OpenAPI → 方案范围与接口深度 |
| `references/appendix_nfr_security.md` | 安全 NFR 策略附录 |
| `references/appendix_nfr_performance.md` | 性能 NFR 策略附录 |
| `references/generate_sh_alignment.md` | 准出 ↔ generate.sh ↔ pytest |
| `references/scheme_quality_checklist.md` | 方案质量扩展自检 |
| `references/platform_scheme_extensions.md` | 平台型 §1.4/§4/§7/附录 |
| `references/staged_exit_criteria.md` | M1/M4 分层准出 |
| `references/t_clarification_workflow.md` | T-xx + 附录 A.1 |
| `references/platform_slices.md` | 秒杀财务模块切片 |
| `../../examples/项目_testscheme.md` | 黄金样例 |
