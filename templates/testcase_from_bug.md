# 从缺陷反推回归用例（AI 输入模板）

> 将 `examples/bug_sample_seckill_redis.md` 或 `output/bugs/*.md` 填进下方占位符，再 `@testcase-skills/生成/SKILL.md` 本文件。

## 缺陷摘要

| 项 | 内容 |
|----|------|
| 编号 | BUG-2026-003 |
| 模块 | 秒杀 · 库存预热 |
| 接口 | POST /api/seckill/activities/{activity_id}/prepare-stock |
| 现象 | Redis 未启动时返回 500 |
| 期望 | 明确错误码 + 「缓存不可用」类提示 |

## 请生成的回归测试点（3 条以内）

1. **环境正常**：Redis 可用时预热返回成功（写清 HTTP 与库存写入 Redis 的预期）。
2. **环境异常**：Redis 不可用时返回约定错误码，且响应无堆栈泄露。
3. **权限**：非 admin 调用预热被拒绝（401/403）。

## 输出要求

- 编号前缀用 `R-`（回归）
- 每条检查点可 PASS/FAIL
- 输出路径建议：`output/seckill_prepare_stock_regression.md`
