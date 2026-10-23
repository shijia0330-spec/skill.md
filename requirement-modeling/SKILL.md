---
name: requirement-modeling
description: Decomposes requirements before test design; clarifies what to test, exclusions, and starting points from PRDs or vague asks. Use before writing cases.
---

# 需求建模 Skill

## 用途

拿到需求文档别急着写用例。先让 AI 帮你把需求拆解清楚，知道测什么、不测什么、从哪开始。

## 使用方式

### 方式一：AI 辅助建模

在 AI 编辑器 Chat 中：

```
@requirement-modeling/SKILL.md

这是产品需求文档（粘贴内容或 @ 文件）：
---
@examples/prd_mini_seckill_auth.md
（或 seckill_finance_system/需求文档.md §2.1 用户认证）
---

帮我拆解测试需求，列出测试范围和优先级。演示系统：秒杀财务一体化。
```

AI 会输出（结构示例）：

```markdown
# 需求拆解结果

## 业务模块
1. 用户认证 → 注册 / 登录 / Profile
2. （本轮不测）商品管理、秒杀下单

## 测试范围

### 功能测试（P0）
- 注册：合法 username+password、重复用户名拒绝
- 登录：admin/customer 成功拿 JWT；错误密码 401
- Profile：带 Token 200；无 Token 401

### 边界测试（P1）
- 密码长度 5 / 6 / 7 位
- username 空、超长（若 PRD 有上限）

### 不测的范围
- 秒杀下单、Redis 预热（下迭代）
- 采购/销售/财务报表

## 测试顺序建议
1. 登录冒烟（admin，依赖 `POST /api/test/init`）
2. 注册与 Profile
3. 权限：customer 不得 POST /api/products
```

### 方式二：从需求生成用例骨架

AI 建模完成后，直接生成用例骨架：

```
基于上面的需求拆解，生成测试用例 spec 文件。
kind 用 api_pytest 或 ui_pytest_playwright，base_url 用 http://your-server:5000（seckill_finance_system）。
```

## 需求解析规则

AI 按以下规则解析需求：

### 实体提取

从需求文本中提取：

| 实体类型 | 说明 | 示例 |
|---------|------|------|
| 功能点 | 用户能做什么 | 注册账号、登录拿 JWT、查 Profile |
| 约束条件 | 功能限制 | 最大 5MB、2-20 字符 |
| 业务规则 | 功能逻辑 | 修改后需重新登录 |
| 前置条件 | 执行前提 | 已登录用户 |
| 后置条件 | 执行结果 | 资料更新、需重新登录 |

### 优先级判定

| 优先级 | 判定标准 |
|--------|---------|
| P0 | 核心功能、用户高频操作、无绕过方案 |
| P1 | 重要功能、边界场景、异常流程 |
| P2 | 次要功能、兼容性、体验优化 |
| P3 | UI 细节、文案、低优先级体验问题 |

### 测试边界

明确标注：

- **测什么**：需求中明确提到的功能
- **不测什么**：需求中明确排除的、其他模块的功能
- **待确认**：需求中模糊的、需要和产品确认的点

## 输出格式

### 需求建模报告

```markdown
# 需求建模报告

## 需求概述
[一句话概括需求]

## 业务领域模型
[实体关系图或文字描述]

## 测试范围
- 功能模块：...
- 测试类型：功能、边界、异常、兼容...
- 优先级分布：P0: X 个, P1: X 个, P2: X 个

## 测试用例骨架
[自动生成 spec 文件或用例列表]

## 待确认事项
1. ...
2. ...
```

## 注意事项

1. **需求不明确时先确认**：AI 会标出模糊点，先找产品确认再写用例
2. **不要过度拆解**：简单需求不需要复杂建模，直接写用例更快
3. **持续更新**：需求变更时，重新跑一遍建模，更新用例范围
4. **和用例生成衔接**：建模完成后，直接把结果喂给 testcase-skills 生成用例

---

## 参考文档

| 文件 | 用途 |
|------|------|
| `references/seckill_finance_scope_in_out.md` | In/Out 范围清单 |
| `references/seckill_finance_open_questions.md` | 待澄清问题表 → 生成阶段 T-xx |

演示 PRD：`examples/prd_mini_seckill_auth.md` · 快速上手：`START_HERE.md`
