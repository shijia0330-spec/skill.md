# 测试用例生成 — 秒杀财务 · 用户认证（示例任务单）

> **说明**：本文件是「如何用用例生成器」的操作指南，**不是** `generate.sh` 的 spec。  
> 业务演示：`seckill_finance_system`（`http://your-server:5000`）。

---

## 需求描述（节选）

- 用户通过 **username + password** 注册/登录，JWT 有效期 24 小时。
- 默认角色 `customer`；`admin` 可管理商品与秒杀活动。
- 注册：用户名唯一；密码至少 6 位；email 可选。
- 错误密码登录返回 401。

完整 PRD：`seckill_finance_system/需求文档.md` §2.1，或 `@examples/prd_mini_seckill_auth.md`。

## 生成方式

```text
@testcase-skills/生成/SKILL.md
@examples/prd_mini_seckill_auth.md

请按 Step 0～6 生成测试用例，输出到 output/seckill_auth_testcases.md
```

## 预期产出特征

- 标题层级与 PRD §2.1 一致
- 含重复用户名、密码长度边界、无 Token 访问 Profile
- 用例编号与评审表符合 `testcase-skills/生成/references/delivery_standard.md`

## 废弃说明

~~`python3 testcase_generator.py ...`~~ 已移除，请勿使用。
