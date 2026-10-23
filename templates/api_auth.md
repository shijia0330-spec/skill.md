---
kind: api_pytest
# seckill_finance_system 认证 API（对齐 backend/openapi.yaml）
base_url: http://your-server:5000
auth:
  type: bearer_login
  login_path: /api/auth/login
  username_field: username
  password_field: password
  username_env: TEST_USERNAME
  password_env: TEST_PASSWORD
  token_json_path: token
cases:
  - id: TC-AUTH-101
    method: GET
    path: /api/auth/profile
    expect_status: 200
  - id: TC-AUTH-102
    method: POST
    path: /api/auth/register
    no_auth: true
    json_body:
      username: "api_auth_reg_{{timestamp}}"
      password: "password123"
      email: "api_auth_{{timestamp}}@example.com"
    expect_status: 201
  - id: TC-AUTH-103
    method: POST
    path: /api/auth/login
    no_auth: true
    json_body:
      username: "admin"
      password: "wrong_password"
    expect_status: 401
  - id: TC-AUTH-104
    method: POST
    path: /api/auth/register
    no_auth: true
    json_body:
      username: "admin"
      password: "password123"
      email: "dup_admin@example.com"
    expect_status: 400
  - id: TC-AUTH-105
    method: GET
    path: /api/auth/profile
    no_auth: true
    expect_status: 401
---

# API 认证测试（秒杀财务系统）

对齐 `seckill_finance_system` 的 `/api/auth/*` 路由（**非** `/api/users/*`）。

| 用例 | 说明 |
|------|------|
| TC-AUTH-101 | 管理员登录后获取 profile |
| TC-AUTH-102 | 新用户注册 |
| TC-AUTH-103 | 错误密码登录 → 401 |
| TC-AUTH-104 | 重复用户名注册 → 400 |
| TC-AUTH-105 | 未登录访问 profile → 401 |

**运行前**：

```bash
export TEST_USERNAME=admin
export TEST_PASSWORD=admin123
# Docker 部署时：export TEST_BASE_URL=http://your-server:5001
./generate.sh templates/api_auth.md
./run_pytest.sh output/api_auth.py -v
```

可先 `POST /api/test/init` 初始化 admin。
