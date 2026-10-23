---
kind: ui_pytest_playwright
base_url: http://127.0.0.1:5173  # seckill_finance_system Web
viewport:
  width: 1280
  height: 720
flows:
  - name: 新增商品表单
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
        value: "表单测试商品"
      - action: fill
        l1_label: "售价"
        value: "88.00"
      - action: click
        l1_role: button
        l1_name: "保存"
    expect:
      - type: visible_text
        text: "商品"
        exact: false
---

# UI 表单填写测试

模拟用户新增商品的完整流程：
1. 登录
2. 进入商品列表
3. 点击新增
4. 填写商品名称与售价
5. 保存并验证列表可见

**定位策略**: 数值字段用 `fill` + `l1_label`；保存按钮优先 role=button。
