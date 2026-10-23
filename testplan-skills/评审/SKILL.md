---
name: testplan-reviewer
description: Reviews test scheme and test plan documents for completeness, consistency with PRD and tech docs, and executability before case design or execution. Use before milestone kickoff or release.
---

# 方案与计划评审 — 动手前最后一道门

**测试方案** 和 **测试计划** 定稿前（或里程碑启动前），过一道评审：与 PRD/技术文档对齐、查漏、看能不能真排期执行。不替代 `testcase-skills/评审`（那是用例评审）。

---

## 1. 啥时候评审

- 方案/计划首版完成，准备排 W1  
- PRD 或技术文档变更后  
- 发布窗口前需要签字留痕  
- 闻到异味：范围说不清、里程碑没退出准则、准出写「差不多」

单人半日活可 informal；多团队并行建议正式评审。

---

## 2. 评审什么

| 维度 | 关注 | 常见问题 |
|------|------|----------|
| **完整性** | 方案 §1～9、计划 §1～10 齐 | 缺准出、缺交付物 |
| **一致性** | 方案 ↔ 计划 ↔ PRD ↔ 技术文档 | 计划测下单、方案 Out-of-Scope |
| **可执行性** | 里程碑、环境、人力 | W2 要 Redis 但没运维 |
| **可观测性** | 准入准出、退出准则 | 「测试完成」无量化 |
| **风险** | T-xx、依赖 | 阻塞项无 Owner |

---

## 3. 三步复核

### Step 1 — 材料齐套

- [ ] 分析 YAML 或等价摘要  
- [ ] `*_testscheme.md`  
- [ ] `*_testplan.md`  
- [ ] PRD + 技术文档（或已知 T-xx）

### Step 2 — 对照清单

一页清单：`references/示例业务_scheme_plan_review.md`（通用项 + 示例）。

重点：

1. 方案 §3.2 每个 In-Scope 模块有策略  
2. 计划 §3.2 每个 P0 模块有 Wn  
3. 最后 Wn 退出准则 ⊇ 方案 §7  
4. T-xx 在方案附录 + 计划 §9 双出现（或计划引用方案附录 A，避免双维护过期）
5. §E2 自动化准出与 `generate_sh_alignment.md` 一致  
6. §F 方案质量维（`scheme_quality_checklist`）已复核  
7. **平台项目**：§E3 多层平台专项已复核

### Step 3 — 输出评审结论

用下方模板；**Critical** 项不清零不建议定稿。

---

## 4. 评审输出模板

```markdown
# 方案与计划评审记录

| 项目 | 财务 v1.1 |
| 方案版本 | v0.1 |
| 计划版本 | v0.1 |
| 评审日期 | YYYY-MM-DD |

## 结论
- [ ] 通过，可进入 W1 / 用例编写
- [ ] 有条件通过（条件：……）
- [ ] 不通过，需修订

## 问题清单

| # | 级别 | 文档 | 位置 | 问题 | 建议 |
|---|------|------|------|------|------|
| 1 | Critical | 方案 | §7 | 准出不可观测 | 改为 P0=0 |
| 2 | Major | 计划 | §3 | W3 在 W2 预热前 | 对调 |

## 待澄清跟踪
| T-xx | 状态 | 对准出的影响 |

## 签字
| 角色 | 姓名 | 日期 |
|------|------|------|
| 测试 | | |
| 开发 | | |
| 产品 | | |
```

---

## 5. 问题分级

| 级别 | 定义 | 处理 |
|------|------|------|
| **Critical** | 范围冲突、无准出、里程碑逆依赖 | 必须改 |
| **Major** | 缺交付物、职责空白、T-xx 无 Owner | 定稿前改 |
| **Minor** | 措辞、格式 | 可跟踪 |

---

## 6. 与 testcase-skills 的衔接

| 阶段 | 评审 Skill |
|------|------------|
| 方案+计划 | **本 Skill** |
| 测试用例 | `testcase-skills/评审` |
| 发布前 | 两者签字均建议具备 |

方案计划通过后：`@testcase-skills/生成/SKILL.md` 生成用例。

---

## 7. 限制

本 Skill **不**评审用例步骤细节；**不**替代性能压测方案的专业评审（若独立立项）。

---

## 参考文档

| 文件 | 用途 |
|------|------|
| `references/示例业务_scheme_plan_review.md` | 评审打勾清单 |
