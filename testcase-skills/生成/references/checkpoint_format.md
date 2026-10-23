# 检查点书写格式

> 示例业务：**秒杀财务系统**（`seckill_finance_system`）。

## 原则

用 **自然、可执行** 的中文描述验证点，不使用「前置条件：」「操作：」「预期：」标签。

## 简单场景（单条 bullet）

```markdown
#### 匿名可浏览在售商品列表
- 未登录调用 GET /api/products，返回 200，body 为数组且仅含 status=active 的商品
```

一条内融合：情境 + 操作 + 预期。

## 复杂场景（多条 bullet）

```markdown
#### 管理员创建商品并设置秒杀库存
- admin 已登录，POST /api/products 提交 name、price、seckill_stock=10
- 响应 201，商品状态为在售
- 调用 prepare-stock 后，GET /api/seckill/status/{activity_id}/{product_id} 可见 Redis 库存与配置一致（环境具备时）
```

## 标题（####）要求

- [OK] `#### 价格为负数时拒绝保存`
- [OK] `#### 未登录访问商品详情`
- [FAIL] `#### 测试1`
- [FAIL] `#### 用户输入合法用户名并且系统验证通过`（过长）

## 具体化

| [FAIL] 模糊 | [OK] 具体 |
|--------|--------|
| 输入非法数据 | POST 注册 body 中 password 为 `12345`（5 位），响应 400 且提示密码长度不足 |
| 输入超长名称 | 商品 name 为 51 个字符（若上限 50），拒绝或前端无法继续输入 |
| 下单成功 | POST 秒杀接口返回 200/201，响应含 order_id，且 GET 该订单详情 status 为 pending |

## 接口类补充

若需求偏 API，检查点可写：

- 请求方法、路径、关键 body 字段（如 `activity_id`、`product_id`）
- 状态码与响应字段断言（与 `openapi.yaml`、401/403/404 约定一致）

## 禁止

- 只复述需求原文而无触发条件
- 「系统支持 XXX」式功能宣传句
- 无法判定 PASS/FAIL 的笼统描述
