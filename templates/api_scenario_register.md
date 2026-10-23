---
kind: api_pytest
base_url: http://your-server:5000
timeout_default: 30
cases: []
scenarios:
  - name: register_then_profile
    steps:
      - method: POST
        path: /api/auth/register
        no_auth: true
        json_body:
          username: "scenario_{{timestamp}}"
          password: "password123"
          email: "scenario_{{timestamp}}@example.com"
        expect_status: 201
        capture:
          access_token: token
      - method: GET
        path: /api/auth/profile
        no_auth: true
        headers:
          Authorization: "Bearer {access_token}"
        expect_status: 200
---

# 多步场景：注册 → 带 Token 查 profile

- `capture`：把响应 JSON 写入上下文，供后续 `{变量名}` 替换
- 第二步使用注册返回的 `token` 访问 `/api/auth/profile`（**非** `/api/users/{id}`）

```bash
./generate.sh templates/api_scenario_register.md
./run_pytest.sh output/api_scenario_register.py -v
```
