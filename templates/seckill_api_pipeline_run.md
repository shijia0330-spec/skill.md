---
kind: api_pytest
cases:
- json_body:
    username: __ENV__:TEST_USERNAME
    password: __ENV__:TEST_PASSWORD
  id: TC-POST--api-auth-login
  expect_status: 200
  path: /api/auth/login
  no_auth: true
  method: POST
  name: POST /api/auth/login 主路径
- json_body:
    password: admin123
  id: TC-POST--api-auth-login-X-422-invalid-body
  expect_status: 422
  path: /api/auth/login
  no_auth: true
  method: POST
  name: 非法请求体 POST /api/auth/login → 422
- json_body:
    username: example
    password: example
  id: TC-POST--api-auth-register
  expect_status: 201
  path: /api/auth/register
  no_auth: true
  method: POST
  name: POST /api/auth/register 主路径
- json_body:
    password: example
  id: TC-POST--api-auth-register-X-422-invalid-body
  expect_status: 422
  path: /api/auth/register
  no_auth: true
  method: POST
  name: 非法请求体 POST /api/auth/register → 422
- json_body: {}
  id: TC-POST--api-auth-register-X-400-empty-body
  expect_status: 400
  path: /api/auth/register
  no_auth: true
  method: POST
  name: 空/缺字段请求体 POST /api/auth/register → 400
- json_body:
    username: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
    password: example
  id: TC-POST--api-auth-register-E-username-len-49
  expect_status: 201
  path: /api/auth/register
  no_auth: true
  method: POST
  name: 边界 username 长度 49（maxLength-1） · POST /api/auth/register
- json_body:
    username: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
    password: example
  id: TC-POST--api-auth-register-E-username-len-50
  expect_status: 201
  path: /api/auth/register
  no_auth: true
  method: POST
  name: 边界 username 长度 50（maxLength） · POST /api/auth/register
- json_body:
    username: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
    password: example
  id: TC-POST--api-auth-register-E-username-len-51
  expect_status: 422
  path: /api/auth/register
  no_auth: true
  method: POST
  name: 边界 username 长度 51（maxLength+1） · POST /api/auth/register
- json_body:
    username: ''
    password: example
  id: TC-POST--api-auth-register-E-username-below-minlen-1
  expect_status: 422
  path: /api/auth/register
  no_auth: true
  method: POST
  name: 边界 username 低于 minLength 1 · POST /api/auth/register
- json_body:
    username: a
    password: example
  id: TC-POST--api-auth-register-E-username-minlen-1
  expect_status: 201
  path: /api/auth/register
  no_auth: true
  method: POST
  name: 边界 username 长度 minLength 1 · POST /api/auth/register
- json_body:
    username: example
    password: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
  id: TC-POST--api-auth-register-E-password-len-127
  expect_status: 201
  path: /api/auth/register
  no_auth: true
  method: POST
  name: 边界 password 长度 127（maxLength-1） · POST /api/auth/register
- json_body:
    username: example
    password: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
  id: TC-POST--api-auth-register-E-password-len-128
  expect_status: 201
  path: /api/auth/register
  no_auth: true
  method: POST
  name: 边界 password 长度 128（maxLength） · POST /api/auth/register
- json_body:
    username: example
    password: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
  id: TC-POST--api-auth-register-E-password-len-129
  expect_status: 422
  path: /api/auth/register
  no_auth: true
  method: POST
  name: 边界 password 长度 129（maxLength+1） · POST /api/auth/register
- json_body:
    username: example
    password: aaaaa
  id: TC-POST--api-auth-register-E-password-below-minlen-6
  expect_status: 422
  path: /api/auth/register
  no_auth: true
  method: POST
  name: 边界 password 低于 minLength 6 · POST /api/auth/register
- json_body:
    username: example
    password: aaaaaa
  id: TC-POST--api-auth-register-E-password-minlen-6
  expect_status: 201
  path: /api/auth/register
  no_auth: true
  method: POST
  name: 边界 password 长度 minLength 6 · POST /api/auth/register
- json_body:
    username: example
    password: example
    email: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
  id: TC-POST--api-auth-register-E-email-len-99
  expect_status: 201
  path: /api/auth/register
  no_auth: true
  method: POST
  name: 边界 email 长度 99（maxLength-1） · POST /api/auth/register
- json_body:
    username: example
    password: example
    email: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
  id: TC-POST--api-auth-register-E-email-len-100
  expect_status: 201
  path: /api/auth/register
  no_auth: true
  method: POST
  name: 边界 email 长度 100（maxLength） · POST /api/auth/register
- json_body:
    username: example
    password: example
    email: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
  id: TC-POST--api-auth-register-E-email-len-101
  expect_status: 422
  path: /api/auth/register
  no_auth: true
  method: POST
  name: 边界 email 长度 101（maxLength+1） · POST /api/auth/register
- id: TC-GET--api-auth-profile
  expect_status: 200
  path: /api/auth/profile
  method: GET
  name: GET /api/auth/profile 主路径
- id: TC-GET--api-auth-profile-X-401-no-auth
  expect_status: 401
  path: /api/auth/profile
  no_auth: true
  method: GET
  name: 未鉴权访问 GET /api/auth/profile → 401
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
# 秒杀财务 API（流水线演示）

由 `codegen/testcase_to_api_spec.py` 从用例 JSON 生成。 下一步: `./generate.sh` 指向本文件。
