---
kind: api_pytest
base_url: http://your-server:5000
setup: none
cases:
  - id: TC-CHAIN-001
    method: POST
    path: /api/auth/register
    no_auth: true
    json_body:
      username: "chain_{{timestamp}}"
      password: "password123"
      email: "chain_{{timestamp}}@example.com"
    expect_status: 201
    extract_vars:
      access_token: token
  - id: TC-CHAIN-002
    depends_on: [TC-CHAIN-001]
    method: GET
    path: /api/auth/profile
    no_auth: true
    headers:
      Authorization: "Bearer ${access_token}"
    expect_status: 200
  - id: TC-CHAIN-003
    depends_on: [TC-CHAIN-002]
    method: GET
    path: /api/products
    no_auth: true
    expect_status: 200
---

# 跨 case 变量池 + depends_on 演示

- **TC-CHAIN-001**：`extract_vars` 把 `token` 写入 session 变量池
- **TC-CHAIN-002**：`${access_token}` 引用；若 001 失败则 **pytest.skip**
- **TC-CHAIN-003**：依赖 002 通过才跑（演示失败跳过链）

```bash
./generate.sh templates/api_chain_vars.md
./run_pytest.sh output/api_chain_vars.py -v
```
