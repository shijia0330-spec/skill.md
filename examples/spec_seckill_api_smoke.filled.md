---
kind: api_pytest
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
      name: "技能包示例-秒杀演示商品"
      description: "examples/spec_seckill_api_smoke.filled.md"
      price: 19.9
      stock: 100
    expect_status: 201
---

# 已填好的 API 冒烟 spec（秒杀财务系统）

配套演示后端：**`seckill_finance_system`**（进销存，本 zip 不含）；**联系交付方获取**；默认 API `http://your-server:5000`（Docker 常见 `5001`）。

## 运行步骤

```bash
cd skills-专业版V3.0
# 另开终端：cd seckill_finance_system && python3 run.py
export TEST_USERNAME=admin
export TEST_PASSWORD=admin123
./generate.sh examples/spec_seckill_api_smoke.filled.md
./run_pytest.sh output/spec_seckill_api_smoke.py -v
```

## 用例说明

| ID | 接口 | 说明 |
|----|------|------|
| TC-SECKILL-PROD-LIST-001 | GET /api/products | 匿名拉在售商品列表 |
| TC-SECKILL-PROD-CREATE-001 | POST /api/products | 管理员创建商品（需 JWT） |

首次无 admin 时可：`curl -X POST http://your-server:5000/api/test/init -H "Content-Type: application/json" -d "{\"admin_password\":\"admin123\"}"`
