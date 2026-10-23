---
kind: api_pytest
# seckill_finance_system 认证冒烟（对齐 openapi.yaml）
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
  - id: TC-AUTH-001
    method: GET
    path: /api/auth/profile
    expect_status: 200
  - id: TC-AUTH-002
    method: POST
    path: /api/auth/login
    no_auth: true
    json_body:
      username: "admin"
      password: "wrong_password"
    expect_status: 401
  - id: TC-AUTH-003
    method: POST
    path: /api/auth/register
    no_auth: true
    json_body:
      username: "seckill_reg_{{timestamp}}"
      password: "password123"
      email: "seckill_{{timestamp}}@example.com"
    expect_status: 201
  - id: TC-AUTH-004
    method: POST
    path: /api/auth/register
    no_auth: true
    json_body:
      username: "admin"
      password: "password123"
      email: "dup@example.com"
    expect_status: 400
  - id: TC-AUTH-005
    method: GET
    path: /api/auth/profile
    no_auth: true
    expect_status: 401
---

# 秒杀系统认证测试

验证注册、登录、Token 与权限控制（路径以 `backend/openapi.yaml` 为准）。

- TC-AUTH-001: 管理员 token 有效，GET profile → 200
- TC-AUTH-002: 错误密码 → 401
- TC-AUTH-003: 新用户注册 → 201
- TC-AUTH-004: 重复用户名 → 400
- TC-AUTH-005: 未授权访问 profile → 401

**注意**：先启动 `seckill_finance_system`；`TEST_PASSWORD` 默认 `admin123`（与 `POST /api/test/init` 一致）。Docker 映射端口时用 `TEST_BASE_URL=http://your-server:5001`。
