---
kind: api_pytest
base_url: http://127.0.0.1:5001
auth:
  type: bearer_login
  login_path: /api/auth/login
  username_field: username
  password_field: password
  username_env: TEST_USERNAME
  password_env: TEST_PASSWORD
cases:
  - id: TC-USER-QUERY-DDT
    method: GET
    path: /api/users/${id}
    data_source: output/users.csv
    expect_status: 200
---
# API 数据驱动测试（验证 auth + data_source 鉴权路径）
