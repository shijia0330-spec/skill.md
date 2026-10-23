---
kind: ui_pytest_playwright
base_url: http://your-server:5173
viewport:
  width: 1280
  height: 720
steps:
  - action: ensure_logged_in
    path: /
  - action: goto
    path: /products
  - action: wait_timeout_ms
    ms: 2000
expect:
  - type: visible_text
    text: "商品"
    exact: false
---

# UI 单页冒烟（秒杀财务 · 商品列表）

验证登录后 `/products` 页面可打开且出现「商品」相关文案。

```bash
# 先启动 seckill_finance_system（Docker: 5173 前端 / 5001 API）
export TEST_BASE_URL=http://your-server:5173
export TEST_USERNAME=admin
export TEST_PASSWORD=admin123
./generate.sh templates/ui_smoke_one_page.md
./run_pytest.sh output/ui_smoke_one_page.py -v
```

若文案不匹配，改 `expect.text` 为页面实际标题，或改用 `l1_role` + `l1_name` 断言导航栏。
