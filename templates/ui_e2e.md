---
kind: ui_pytest_playwright
base_url: http://127.0.0.1:5173  # seckill_finance_system Web
viewport:
  width: 1280
  height: 720
steps:
  - action: goto
    path: /login
  - action: fill
    l1_label: "用户名"
    value: "admin"
  - action: fill
    l1_label: "密码"
    value: "admin123"
  - action: click
    l1_role: button
    l1_name: "登录"
  - action: goto
    path: /products
  - action: click
    l1_role: button
    l1_name: "新增"
  - action: fill
    l1_label: "商品名称"
    value: "e2e_测试商品"
  - action: fill
    l1_label: "售价"
    value: "99.00"
  - action: click
    l1_role: button
    l1_name: "保存"
  - action: goto
    path: /stock
expect:
  - type: visible_text
    text: "库存"
    exact: false
---

# UI 端到端流程测试

跨页面完整流程：登录 → 新增商品 → 查看库存列表。

这种测试最接近真实用户操作，但也最脆弱——页面一改版就得改。

**经验之谈**: E2E 测试别写太多，挑最核心的 2-3 条业务流程就够了。
