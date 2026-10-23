---
kind: perf_test
engine: k6
base_url: http://your-server:5001
concurrent: 10
duration: 60
ramp_up: 10
probe_path: /api/health
endpoints:
  - name: 健康检查
    method: GET
    path: /api/health
    weight: 3
    expect_status: 200
    max_response_ms: 500
  - name: 登录
    method: POST
    path: /api/auth/login
    weight: 1
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
    headers:
      Authorization: "Bearer ${token}"
    expect_status: 200
    max_response_ms: 800
---

# k6 性能测试（codegen）

```bash
./generate.sh templates/perf_test_k6.md
k6 run -e BASE_URL=http://your-server:5001 -e TEST_USERNAME=admin -e TEST_PASSWORD=admin123 output/perf_test_k6.js
```
