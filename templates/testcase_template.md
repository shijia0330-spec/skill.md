# 测试用例生成 — <模块名>

> **说明**：任务单模板，**不是** `generate.sh` 的 spec。生成用例请 `@testcase-skills/生成/SKILL.md`。

---

## 需求描述

（粘贴 PRD 全文或链接到 `templates/需求文档.md`）

## 生成方式

**使用 testcase-skills/生成（勿用已废弃的 testcase_generator.py）**

1. `@testcase-skills/生成/SKILL.md`
2. `@` 本需求文档
3. 输出至：`output/<模块名>_testcases.md`

Agent 执行 Step 0～6：预分析 → 生成测试点 → 自检并修复。

## 输出要求

- 保持 PRD 标题层级（见 `references/structure_preservation.md`）
- 测试点为验证点，非功能复述
- 边界值：阈值 -1 / 阈值 / 阈值 +1
- 若有核心流程：单独章节且树形结构与预分析一致

## 参考样板

- 用例风格：`templates/测试用例-需求文档.md`
- 样例：`testcase-skills/生成/references/examples.md`
