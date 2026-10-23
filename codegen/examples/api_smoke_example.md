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
  token_json_path: token
cases:
  - id: TC-API-001
    method: GET
    path: /api/products
    expect_status: 200
  - id: TC-API-002
    method: GET
    path: /api/auth/profile
    expect_status: 200
---

# 说明

- 运行前设置环境变量：`TEST_USERNAME`、`TEST_PASSWORD`（与目标系统一致）。
- 可覆盖基址：`TEST_BASE_URL`。
- 生成命令：

```bash
cd skills-专业版V3.0/codegen
pip install -r requirements.txt
python3 run_spec.py examples/api_smoke_example.md -o /tmp/gen/test_api_smoke.py
pytest /tmp/gen/test_api_smoke.py -v
```
