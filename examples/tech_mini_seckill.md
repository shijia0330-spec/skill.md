# 秒杀财务系统 · 技术文档（演示输入）

> 供 `testplan-skills/分析` 与方案/计划流水线使用；与 `examples/prd_mini_seckill_auth.md` 配对。

## 1. 架构概览

- **后端**：Flask + SQLAlchemy + Redis
- **认证**：JWT Bearer，`POST /api/auth/login`
- **核心模块**：商品、秒杀活动、订单、财务凭证

## 2. 关键 API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/login` | 登录，返回 `token` |
| GET | `/api/products` | 商品列表（匿名） |
| POST | `/api/products` | 创建商品（admin） |
| POST | `/api/seckill/{activity_id}/{product_id}` | 秒杀下单 |
| POST | `/api/test/init` | 测试环境铺底 |

## 3. 数据与中间件

- **MySQL**：用户、商品、订单、财务表
- **Redis**：秒杀库存 `_stock`、防超卖
- **角色**：`admin` / `customer`

## 4. 部署

| 环境 | 地址 |
|------|------|
| 本地 | `http://your-server:5000` |
| Docker | `http://your-server:5001` |

## 5. 非功能（测试关注）

- 秒杀接口 P99 响应 < 500ms（压测目标，待确认）
- 登录失败 401；无权限 403
- 库存为 0 时下单应拒绝

## 6. 待澄清（T-xx）

| 编号 | 问题 | Owner |
|------|------|-------|
| T-01 | 秒杀活动预热窗口是否纳入本轮 | 产品 |
| T-02 | 财务凭证自动生成触发条件 | 开发 |
