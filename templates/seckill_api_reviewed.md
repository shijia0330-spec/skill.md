---
kind: api_pytest
cases:
- json_body:
    username: __ENV__:TEST_USERNAME
    password: __ENV__:TEST_PASSWORD
  method: POST
  expect_status: 200
  path: /api/auth/login
  no_auth: true
  id: TC-AUTH-L01
  name: L-01 正确凭证登录返回 JWT
- json_body:
    username: __ENV__:TEST_USERNAME
    password: wrong-password
  method: POST
  expect_status: 401
  path: /api/auth/login
  no_auth: true
  id: TC-AUTH-V04
  name: V-04 错误密码登录失败
- json_body:
    password: admin123
  method: POST
  expect_status: 400
  path: /api/auth/login
  no_auth: true
  id: TC-AUTH-X-LOGIN-MISSING-USER
  name: 缺用户名登录 → 400
- json_body:
    username: skills_reg_{{timestamp}}
    password: password123
    email: skills_{{timestamp}}@example.com
  method: POST
  expect_status: 201
  path: /api/auth/register
  no_auth: true
  id: TC-AUTH-C01
  name: C-01 新用户注册成功
- json_body:
    username: admin
    password: password123
    email: dup@example.com
  method: POST
  expect_status: 400
  path: /api/auth/register
  no_auth: true
  id: TC-AUTH-V03
  name: V-03 重复用户名注册失败
- json_body: {}
  method: POST
  expect_status: 400
  path: /api/auth/register
  no_auth: true
  id: TC-AUTH-X-REG-EMPTY
  name: 空 body 注册 → 400
- json_body:
    username: only_username_no_pwd
  method: POST
  expect_status: 400
  path: /api/auth/register
  no_auth: true
  id: TC-AUTH-X-REG-NO-PASSWORD
  name: 缺密码注册 → 400
- method: GET
  expect_status: 200
  path: /api/auth/profile
  id: TC-AUTH-D01
  name: D-01 有效 Token 查询 Profile
- method: GET
  expect_status: 401
  path: /api/auth/profile
  no_auth: true
  id: TC-AUTH-D02
  name: D-02 未授权访问 Profile → 401
auth:
  type: bearer_login
  login_path: /api/auth/login
  username_field: username
  password_field: password
  username_env: TEST_USERNAME
  password_env: TEST_PASSWORD
  token_json_paths:
  - access_token
  - token
  - data.access_token
  - data.token
base_url: http://127.0.0.1:5001
---
# 秒杀财务 API（评审后）

由 `codegen/testcase_to_api_spec.py` 从用例 JSON 生成。 下一步: `./generate.sh` 指向本文件。
