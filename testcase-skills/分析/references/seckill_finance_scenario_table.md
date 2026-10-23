# 秒杀财务系统 · 场景分析输出表

分析 Skill 结束时产出以下结构，供 `testcase-skills/生成` Step 1 使用。

## 认证模块示例

### scenarios

| ID | 场景 | 前置 | 预期摘要 | 优先级 |
|----|------|------|----------|--------|
| S1 | 新用户注册成功 | 无 | 201 + customer | P0 |
| S2 | 重复用户名 | 已有 user_a | 400 | P0 |
| S3 | admin 登录 | 测试库有 admin | 200 + JWT | P0 |
| S4 | 错误密码 | 任意用户 | 401 | P0 |
| S5 | 无 Token 查 Profile | 未登录 | 401 | P0 |

### boundaries

| 字段 | 边界值 | 测点 |
|------|--------|------|
| password 长度 | 5 / 6 / 7 | V-02 |
| username 长度 | 0 / 1 / 50 / 51 | （待澄清上限） |

### rules

- 用户名唯一（DB 约束）
- 密码哈希存储，响应不含明文
- JWT 24h（过期不测除非 PRD 要求）

### open_questions

见 `requirement-modeling/references/seckill_finance_open_questions.md` Q1～Q2。
