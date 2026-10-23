# 缺陷单 BUG-2026-003（示例）

| 字段 | 值 |
|------|-----|
| 缺陷编号 | BUG-2026-003 |
| 标题 | 秒杀活动预热库存时 Redis 未连接导致 500，无友好提示 |
| 严重程度 | High |
| 缺陷类型 | 功能 |
| 所属模块 | 秒杀 · 库存预热 |
| 当前状态 | Draft |
| 优先级 | P1 |

## 发现信息

- 发现时间：2026-05-17 14:30
- 发现人：自动化回归
- 发现方式：API 测试
- 关联用例：TC-SECKILL-PREPARE-001（`POST /api/seckill/activities/{id}/prepare-stock`）

## 环境

- 系统：seckill_finance_system @ `http://your-server:5000`
- 分支/版本：本地 demo
- Redis：未启动（`redis-server` 未运行）
- 账号：admin / admin123

## 复现步骤

1. 管理员登录，创建秒杀活动并关联商品（秒杀库存 > 0）。
2. 停止 Redis 或指向错误端口。
3. 调用 `POST /api/seckill/activities/1/prepare-stock`。

## 实际结果

- HTTP 500，响应为通用 Internal Server Error。
- 服务端日志含 Redis connection refused。

## 预期结果

- 应返回 503 或 400，JSON 中明确提示「缓存服务不可用，无法预热库存」。
- 不应将堆栈信息直接暴露给 API 调用方。

## 证据

- 请求：`POST /api/seckill/activities/1/prepare-stock`，Header 含 Bearer Token。
- 响应片段：`{"error": "Internal Server Error"}`

## 分流建议

- [ ] 环境（先启动 Redis：`redis-server` 或 Docker）
- [x] 产品待确认（失败时的错误码与文案）
- [ ] 脚本自愈

## 影响范围

管理员无法在测试环境完成秒杀预热；阻塞后续 `POST /api/seckill/{activity_id}/{product_id}` 下单联调。
