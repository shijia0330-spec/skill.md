# 测试方案质量自检 — 覆盖维度

方案 Skill **Step 7** 在模板 §9 基础上，按本表做 **扩展自检**（对标 testcase `universal_coverage_matrix` 的方案层等价物）。

---

## 使用方式

方案定稿前逐项打勾；触发行无策略 → 补 §3.2 或标 T-xx。

| 维 | 触发条件 | 方案中应有 | 黄金样例 |
|----|----------|------------|----------|
| **A** 范围 | 总有 | §2.1 每模块有优先级 | 项目_testscheme §2 |
| **B** 追溯 | PRD 有条目 | §2.3 PRD↔技术↔策略 | §2.3 |
| **C** 主路径 | 有端到端业务 | 分析 core_flows 或 §2.3 提及 | core_flows F1/F2 |
| **D** 异常/拒绝 | P0 模块 | §3.2 功能 L≥2 或 T-xx | 下单 4xx、Redis 不可用 |
| **E** 权限 | 有角色 | §3.2 安全 ✓ | admin/developer |
| **F** 中间件 | 技术文档有 Redis/MQ | §3.2 集成 ✓ | Redis 预热/扣减 |
| **G** 接口契约 | 有 OpenAPI/端点表 | openapi_scope 已加载 | §4 + 附录 D |
| **H** NFR 安全 | 对外/订单/PRD 要求 | appendix_nfr_security | 附录 B |
| **I** NFR 性能 | SLA 或类 | appendix_nfr_performance 或 ○ 抽样 | 附录 C |
| **J** 自动化 | 方案 §7 写自动化准出 | generate_sh_alignment 有命令 | 附录 D |
| **K** 准入准出 | 总有 | §6 §7 可勾选可观测 | §6～7 |
| **L** 待澄清 | 简陋 PRD | 附录 A T-xx 有 Owner | 附录 A |
| **M** 用例分期 | 资产 ≥500 或人力紧 | §1.4 入库 vs 执行 + P3/P4 豁免 | platform_scheme_extensions |
| **N** 分阶段准出 | 平台/多里程碑 | §7 M1 + M4；M1 非阻塞项 | staged_exit_criteria |
| **O** 任务追溯 | 有 Excel 任务表 | 附录 H 或 §2.3 来源列 | enterprise_platform_inputs |

---

## 文末自检表（复制到方案 §10）

```markdown
## 10. 方案质量自检

| 维 | 触发 | 覆盖 | 备注 |
|----|------|------|------|
| A 范围 | 是 | ☑ | |
| B 追溯 | 是 | ☑ | |
| C 主路径 | 是 | ☑ | F1/F2 |
| D 异常 | 是 | ☑ | |
| E 权限 | 是 | ☑ | |
| F 中间件 | 是 | ☑ | Redis |
| G OpenAPI | 部分 | ☑ | tech §3 |
| H 安全 NFR | 是 | ☑ | 附录 B |
| I 性能 NFR | 是 | ☑ | 50 并发抽样 |
| J 自动化 | 是 | ☑ | _api_smoke |
| K 准入准出 | 是 | ☑ | |
| L T-xx | 是 | ☑ | T-01～04 |
| M 用例分期 | 是/否 | ☑ | §1.4 |
| N 分阶段准出 | 是/否 | ☑ | M1/M4 |
| O 任务追溯 | 是/否 | ☑ | 附录 H |
```

---

## 出口闸门

- 触发行 ≥3 且「覆盖」为空 → **禁止定稿**  
- J 维触发（写了自动化准出）但无 `generate_sh_alignment` 命令 → **禁止定稿**

---

## 与 testcase 矩阵的关系

| testcase 生成 | testplan 方案 |
|---------------|---------------|
| 具体测试点编号 | 模块级策略 L0～L3 |
| 文末矩阵自检表 | 本文件 §10 |
| Step 4 边界 trio | 方案 §2.3 + T-xx |

用例生成后，评审时核对：方案 §3.2 每一 ✓ 在用例集中有对应批或 T-xx。
