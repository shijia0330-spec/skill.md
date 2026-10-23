---
kind: api_pytest
base_url: http://your-server:5000
setup: test_init
cases:
  - id: TC-LOGIN-DDT
    method: POST
    path: /api/auth/login
    no_auth: true
    json_body:
      username: ""
      password: ""
batch:
  concurrency: 1
  fail_fast: false
  cases:
    - TC-LOGIN-DDT
  data_source:
    type: csv
    path: templates/data/login_matrix.csv
---

# 登录接口 — CSV 数据驱动（batch）

同一 case 模板 + CSV **4 行**，在 `test_batch_execute` 内循环发 4 次请求（委托 `api_lib.run_batch`）。

| CSV 列 | 合并目标 |
|--------|----------|
| `username`、`password` | `json_body` |
| `expected_status` | case 顶层 `expect_status` |
| `case_id` | 仅报告/metadata，不进请求体 |

```bash
./generate.sh templates/api_login_ddt.md
./run_pytest.sh output/api_login_ddt.py -v -k batch
```
