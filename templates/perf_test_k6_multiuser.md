---
kind: perf_test
engine: k6
base_url: http://your-server:5001
concurrent: 50
duration: 60
ramp_up: 10
data_source:
  file: output/users.csv
  variables: [username, password]
  ignore_first_line: true
  recycle: false
endpoints:
  - name: 登录
    method: POST
    path: /api/auth/login
    json_body:
      username: "${username}"
      password: "${password}"
    save_token: true
    token_json_path: "$.token"
    expect_status: 200
  - name: 商品列表
    method: GET
    path: /api/products
    weight: 5
    expect_status: 200
    max_response_ms: 800
  - name: 用户信息
    method: GET
    path: /api/auth/profile
    weight: 2
    headers:
      Authorization: "Bearer ${token}"
    expect_status: 200
    max_response_ms: 800
---

# k6 多用户压测（codegen · CSV）

衔接 `templates/data_factory.md` 导出的 `output/users.csv`。

```bash
# 1. 造数
python3 codegen/run_spec.py templates/data_factory.md -o output/data_factory.py
cd output && python3 data_factory.py && cd ..

# 2. 生成 k6 脚本（每 VU 固定一行账号，独立登录）
./generate.sh templates/perf_test_k6_multiuser.md
# → output/perf_test_k6_multiuser.js

# 3. 执行（concurrent 建议 = users.csv 数据行数）
k6 run -e BASE_URL=http://127.0.0.1:5001 output/perf_test_k6_multiuser.js

# 4. 清理
cd output && python3 data_factory.py --cleanup
```

单用户冒烟请用 `templates/perf_test_k6.md` 或 `load-testing/references/k6-template.js`。
