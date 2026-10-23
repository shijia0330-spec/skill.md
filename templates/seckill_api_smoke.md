---
kind: api_pytest
# 与 templates/api_smoke.md 对齐：仅秒杀财务系统「商品查询 + 新增」最小面
base_url: http://your-server:5000
auth:
  type: bearer_login
  login_path: /api/auth/login
  username_field: username
  password_field: password
  username_env: TEST_USERNAME
  password_env: TEST_PASSWORD
cases:
  - id: TC-SECKILL-PROD-LIST-001
    method: GET
    path: /api/products
    no_auth: true
    expect_status: 200
  - id: TC-SECKILL-PROD-CREATE-001
    method: POST
    path: /api/products
    json_body:
      name: "秒杀技能冒烟-自动创建商品"
      description: "templates/seckill_api_smoke.md"
      price: 9.99
      stock: 10
    expect_status: 201
---

# 秒杀财务系统 API 冒烟（商品）

业务系统需自备：在**你的项目根目录**启动服务（示例为含 `GET/POST /api/products` 的秒杀/财务 demo），再设置 `TEST_BASE_URL` 指向该服务。

- **商品查询**：`GET /api/products`（匿名可访问，返回 `active` 商品 JSON 数组）。
- **新增商品**：`POST /api/products`（请求体 JSON，至少 `name` + `price`；需**管理员** Bearer Token）。

```bash
export TEST_USERNAME=admin
export TEST_PASSWORD=admin123
```
