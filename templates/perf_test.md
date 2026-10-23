---
kind: perf_test
engine: locust
# 秒杀财务：base_url 指向 seckill_finance_system，压测 GET /api/products 或 POST 秒杀下单
# Locust 快速冒烟专用（日常压测默认 k6，见 templates/perf_test_k6.md 与 @load-testing/执行/SKILL.md）
base_url: http://your-server:5000
concurrent: 10
duration: 60
ramp_up: 10
endpoints:
  - name: 商品列表
    method: GET
    path: /api/products
    weight: 5
    expect_status: 200
    max_response_ms: 500
  - name: 健康检查
    method: GET
    path: /api/health
    weight: 2
    no_auth: true
    expect_status: 200
    max_response_ms: 300
  - name: 登录
    method: POST
    path: /api/auth/login
    weight: 3
    json_body:
      username: admin
      password: admin123
    expect_status: 200
    max_response_ms: 500
---

# 性能测试模板
# 用法: ./generate.sh templates/perf_test.md
# 运行: cd output && locust -f perf_test.py --headless -u 10 -r 2 -t 30s
# 或 Web UI: locust -f perf_test.py → 浏览器打开 http://your-server:8089
