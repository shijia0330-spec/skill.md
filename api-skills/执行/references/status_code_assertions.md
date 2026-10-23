# HTTP 状态码断言速查（秒杀财务 API）

编写 spec 或 pytest 时默认预期；与 `seckill_finance_system/app.py` 行为对齐。

| 场景 | 方法示例 | 预期 | 备注 |
|------|----------|------|------|
| 匿名读商品列表 | GET /api/products | 200 | `no_auth: true` |
| 管理员创建商品 | POST /api/products | 201 | 需 admin JWT |
| 非管理员创建 | POST /api/products | 403 | customer Token |
| 未登录创建 | POST /api/products | 401 | 无 Header |
| 登录成功 | POST /api/auth/login | 200 |  body 含 token |
| 密码错误 | POST /api/auth/login | 401 | |
| 注册成功 | POST /api/auth/register | 201 | |
| 重复用户名 | POST /api/auth/register | 400 | |
| 无 Token Profile | GET /api/auth/profile | 401 | |
| 资源不存在 | GET /api/products/999999 | 404 | |
| 秒杀旧接口 | GET /api/seckill/status/{product_id} | 400 | 提示用新路径 |
| 秒杀下单成功 | POST /api/seckill/{aid}/{pid} | 200/201 | 以实现为准 |
| 库存不足 | POST /api/seckill/... | 409/400 | **待澄清**，写 T-xx |

## 断言写法（spec）

```yaml
expect_status: 401
```

## 常见误用

- 把 403 写成 401（角色错 vs 未登录）
- 登录用例忘记 `save_token: true` 导致后续 401
