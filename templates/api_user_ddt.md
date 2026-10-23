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
    no_auth: true
    data_source: output/users.csv
    expect_status: 200
---
# API 数据驱动测试（验证 data_source 懒加载）

使用 data_factory 生成的 output/users.csv 作为数据源，每条用户记录生成一条查询用例。

```bash
python3 codegen/run_spec.py templates/api_user_ddt.md -o output/api_user_ddt.py
pytest output/api_user_ddt.py -v
```
