---
kind: perf_test
engine: jmeter
base_url: http://your-server:5001
concurrent: 10
duration: 60
ramp_up: 10
endpoints:
  - name: 健康检查
    method: GET
    path: /api/health
    weight: 3
    expect_status: 200
    max_response_ms: 500
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
      Authorization: "Bearer ${PERF_ACCESS_TOKEN}"
    expect_status: 200
---

# JMeter 性能测试（单 Token / 无 CSV）

> 多用户 CSV 压测请用 **`templates/jmeter_test.md`**（衔接 data_factory 的 `output/users.csv`）。

```bash
./generate.sh templates/perf_test_jmeter.md
python3 codegen/run_jmeter_perf.py -t output/perf_test_jmeter.jmx
```
