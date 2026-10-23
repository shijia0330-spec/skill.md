---
name: testcase-generator
description: 从 PRD/OpenAPI 生成专业测试点。默认 Step 0a RAG 检索 + 通用覆盖矩阵、用例编号、评审表、待澄清清单。
---

# 测试用例生成（专业版）

从需求文档生成 **可判定 PASS/FAIL** 的测试点。本包仅此一种交付规格，按下列规则完整执行。

## 快速使用

```text
@testcase-skills/生成/SKILL.md
@需求文档.md
（可选）@openapi.yaml
生成测试用例，输出 output/模块名_testcases.md
```

**默认流程会先 RAG 再写用例**（Step 0a）。AI 须执行：

```bash
cd skills-专业版V3.0
python3 testcase-skills/生成/scripts/rag_prefetch.py templates/需求文档.md \
  --out output/rag_context_模块名.md
```

将输出的「知识库检索摘要」并入生成上下文；无命中时继续生成并在文档信息标注 `RAG: 无命中`。

---

## 核心原则

### 1. 测试点 ≠ 功能描述

见 `references/test_point_validation.md`。落笔前三问：验证行为？能 PASS/FAIL？有明确预期？

### 2. 层级适中

见 `references/hierarchy_patterns.md`（2/3/4 级）。

### 3. 检查点格式

见 `references/checkpoint_format.md`。不用「前置/操作/预期」标签。

### 4. PRD 与通用矩阵

| 来源 | 规则 |
|------|------|
| **PRD 明确写的** | 必须覆盖 |
| **通用矩阵触发的** | 必须有点 **或** `T-xx（待澄清）` 占位 |
| **PRD 未写且未触发矩阵** | 不编造功能 |

不臆测业务；不清楚写待澄清，见 `references/delivery_standard.md`。

### 5. 覆盖维度

正向、反向、边界、状态/时间、权限；另扫 `references/universal_coverage_matrix.md`。

---

## 工作流程

### Step 0a：RAG 知识检索（必做，先于一切分析）

在读 PRD 写点之前，**必须先**从 `rag-engine` 知识库检索团队历史经验。细则见 `references/rag_knowledge.md`。

1. **构造检索词**：模块名、PRD 标题、接口名、业务名词（与 `00_知识增强约定.md` 一致）。
2. **执行检索**（二选一，优先脚本）：
   ```bash
   python3 testcase-skills/生成/scripts/rag_prefetch.py <需求.md> --top-k 5 \
     --out output/rag_context_<模块>.md
   ```
   或：`cd rag-engine/scripts && python3 rag_search.py "<检索词>" --top-k 5`
3. **吸收规则**：
   - 检索到的 `[case]` / `[bug]` / `[best_practice]` 可补充测试点，**须在检查点或追溯表注明来源**（如「RAG-鉴权设计」）。
   - 与 PRD **冲突** → 不擅自采纳，写入待澄清清单。
   - **无命中** → 不阻塞；文档信息写 `RAG: 无命中`，纯 PRD + 矩阵继续。
4. **产出**：一段「知识库检索摘要」（见 Step 5 模板），供 Step 4 写点时参考。

---

### Step 0b：需求预分析（原始 PRD 必做）

已结构化 `func_list.md` 可跳过至 Step 1。

1. **结构**：保持 PRD 标题层级 → `references/structure_preservation.md`
2. **核心流程**：树形 10～15 步 → `references/core_flows.md`
3. **功能点**：`- 条件` + `预期：` → `references/requirement_patterns.md`
4. **阈值清单**：提取所有比较符/次数/时间 → 供 Step 4 边界与矩阵 E 维
5. **预分析自检**：PRD 节全覆盖、术语一致

有 **详细设计 docx** 时：加载 `references/seckill_detailed_design_inputs.md`，提取 §4 接口与 §3 业务流程，与 UI 用例分章输出（编号 301+ 段）。  
有 **秒杀财务详细设计 docx / 评审 md** 时：加载 `examples/tech_mini_seckill.md`，**Step 0 必扫清单逐行覆盖**；禁止仅 API+控制台模板展开而跳过章节。

有 OpenAPI 时：记录端点列表，供 Step 4 加载 `references/api_contract_supplement.md`。

有 **UI/API 自动化用例** 需求时：先读 `references/automation_generation_gate.md`，再按需加载 `references/automation_*.md` 系列（见闸门内索引表）。

---

### Step 1：分析需求

判断：核心流程有无、复杂度（2/3/4 级）、模块划分、矩阵哪些维度将触发。

---

### Step 2：核心流程测试

有核心流程则优先生成 → `references/core_flow_testing.md`
`### 流程N：` + 与 func_list 一致的树形结构；编号 `F-01`…

---

### Step 3：确定层级

| 类型 | 结构 |
|------|------|
| 简单 | H2 → H3 |
| 标准 | H2 → H3 → H4 |
| 复杂 | H2 → H3 → H4 → H5 |

---

### Step 4：生成详细测试点

对每个功能/场景：

1. 从 PRD 功能点写检查点（验证点句式）
2. **边界值**：PRD 阈值 → trio（`references/boundary_value_testing.md`）
3. **时间/状态**：→ `references/time_and_state.md`
4. **通用覆盖矩阵**：
   - 加载 `references/universal_coverage_matrix.md`
   - 对每个触发的维度 A～G 写检查点或 `T-xx 待澄清`
   - 有 OpenAPI 则叠加 H 维 `references/api_contract_supplement.md`
   - 需要安全/性能包则加载 `references/appendix_security.md` / `references/appendix_performance.md`
5. **编号与优先级**：按 `references/delivery_standard.md` 赋 `L-/D-/C-/V-/P-` 与 P0～P3
6. **评审表名称（Description）**：Web / 有 UI 的模块，评审表「名称」须含 `{产品} > {页面} > {功能点}`，见 `delivery_standard.md` §4.2.1；H4 标题可短，评审表写全

### Step 5：输出（符合交付标准）

```markdown
# [模块名] 测试用例

## 文档信息
- 依据需求：
- 生成版本：规则 1.2.0（skills V3.0 · testcase-skills/生成）
- RAG 检索：有命中 N 条 / 无命中（检索词：…）
- 测试范围：
- 结构说明：
- 待澄清汇总：N 条

## 知识库检索摘要

（Step 0a 输出；无命中则写「RAG: 无命中」）

## 需求追溯表

| 需求段落 | 用例编号 | 说明 |

## 核心流程测试

### 流程1：…

## 详细功能点测试

## 用例评审表

| 编号 | 名称 | 优先级 | 类型 | 标签 |

## 通用覆盖矩阵自检

（复制矩阵打勾表，见 universal_coverage_matrix.md）

## 待澄清清单

| # | 问题 | 关联编号 |
```

默认路径：`skills-专业版V3.0/output/[模块名]_testcases.md`

---

### Step 6：自检并修复（必须改稿）

#### 检查 1：测试点格式

`references/test_point_validation.md` — 消灭「支持/需要通过」句式。

#### 检查 2：边界值

每个 PRD 阈值：-1 / 边界 / +1；时间窗三态。

#### 检查 3：PRD 覆盖

func_list 每功能点有对应用例编号。

#### 检查 4：核心流程结构

与 func_list 树一致。

#### 检查 5：通用覆盖矩阵

矩阵 A～I 打勾表填满；触发行无空白（须有点或 T-xx）。

#### 检查 6：交付标准

- 评审表完整
- 编号无重复
- P0 占比合理（≤20%）
- 待澄清已汇总

#### 检查 7：页面/菜单路径（Web / 有 UI）

- 评审表「名称」含 ` > ` 页面路径，或可与正文 `##`/`###` 层级一一对应
- 与 `UI精简/references/output_schema.md` 段头 `· 秒杀财务 > …` 可对齐
- 纯 API 模块可用 `秒杀财务 > API > …` 形式

**硬约束（必跑）**：

```bash
python3 testcase-skills/生成/scripts/step6_validator.py output/模块名_testcases.md
# 退出码：0=通过 | 1=P0 阻塞 | 2=P1 建议 | 3=P2 优化
# P0 必须改稿至通过；P1 建议修复后再评审
```

与 `testcase-skills/评审` 一致；评审 Skill 为发布前加强复核。

---

## 边界值速查

| 需求 | 必测 |
|------|------|
| X > N | N+1, N, N-1 |
| min～max | min-1,min,min+1,max-1,max,max+1 |
| N 次限制 | N-1, N, N+1 |

---

## 参考文档

| 文件 | 何时加载 |
|------|----------|
| **`references/rag_knowledge.md`** | Step 0a（必） |
| **`references/universal_coverage_matrix.md`** | Step 4、6（必） |
| **`references/delivery_standard.md`** | Step 5、6（必） |
| `references/test_point_validation.md` | 写每条检查点 |
| `references/core_flow_testing.md` | Step 2 |
| `references/time_and_state.md` | 时间/状态/次数 |
| `references/api_contract_supplement.md` | 有 OpenAPI |
| `references/appendix_security.md` | 安全包 |
| `references/appendix_performance.md` | 性能包 |
| `references/requirement_patterns.md` | Step 0 |
| `references/core_flows.md` | Step 0 |
| `references/seckill_detailed_design_inputs.md` | 秒杀财务详细设计 docx |
| `examples/tech_mini_seckill.md` | 秒杀财务详细设计 + 评审清单 |
| **`references/automation_generation_gate.md`** | UI/API 自动化用例入口（闸门 + 系列索引） |
| `references/automation_*.md` | 自动化用例细则（输入源/流程/格式/编号等 9 篇） |
| `references/structure_preservation.md` | Step 0 |
| `references/hierarchy_patterns.md` | Step 3 |
| `references/checkpoint_format.md` | Step 4 |
| `references/boundary_value_testing.md` | 数值边界 |
| `references/examples.md` | 样例 |

---

## 质量清单（交付前）

- [ ] Step 0a RAG 已执行（或有「无命中」说明）
- [ ] 矩阵自检表 + 评审表 + 待澄清清单齐全
- [ ] 测试点均可 PASS/FAIL
- [ ] PRD 追溯表完整
- [ ] 边界与矩阵触发行已覆盖
- [ ] 无 PRD 外的编造功能
- [ ] Web / 有 UI：评审表名称含页面路径（§4.2.1，含 ` > `）

---

## 流水线

| 环节 | Skill |
|------|-------|
| 规划 | `testcase-skills/规划` |
| 分析 | `testcase-skills/分析`（≈ Step 0b；RAG 已在 Step 0a） |
| **生成** | **本 Skill** → `*_testcases.md`（完整 · 评审/归档） |
| **UI 精简** | `testcase-skills/UI精简` → `*_ui_cases.md`（自动化输入） |
| 评审 | `testcase-skills/评审` |
| UI 转化 | `UI-skills/转化` → spec → pytest |

接口自动化：见 `api-skills/`、`generate.sh`（OpenAPI → pytest）。

## 已废弃

~~`testcase_generator.py`~~ — 勿用，统一使用本 Skill。
