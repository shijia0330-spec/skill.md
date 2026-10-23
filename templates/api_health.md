---
kind: api_pytest
# 秒杀财务系统无专用 /health；用匿名商品列表探测服务存活
base_url: http://your-server:5000
setup: none
cases:
  - id: TC-SECKILL-HEALTH-001
    method: GET
    path: /api/products
    no_auth: true
    expect_status: 200
---

# API 存活探测（秒杀财务系统）

`GET /api/products` 无需登录，200 即表示 Flask 与数据库基本可用。

```bash
# seckill_finance_system 先启动：python3 run.py
./generate.sh templates/api_health.md
python3 -m pytest output/api_health.py -v
```

若需同时验证 OpenAPI 文档可达，可自行加一条 `GET /openapi.yaml` expect_status: 200。
