---
kind: ui_pytest_playwright
base_url: http://your-server:5000  # seckill_finance_system
viewport:
  width: 1280
  height: 720
flows:
  - name: 正常登录
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
    expect:
      - type: url_regex
        pattern: "/(dashboard|home)$"
  - name: 密码错误
    steps:
      - action: goto
        path: /login
      - action: fill
        l1_label: "用户名"
        value: "admin"
      - action: fill
        l1_label: "密码"
        value: "wrong_password"
      - action: click
        l1_role: button
        l1_name: "登录"
    expect:
      - type: visible_text
        text: "密码错误"
        exact: false
  - name: 用户名为空
    steps:
      - action: goto
        path: /login
      - action: fill
        l1_label: "密码"
        value: "admin123"
      - action: click
        l1_role: button
        l1_name: "登录"
    expect:
      - type: visible_text
        text: "用户名"
        exact: false
---

# UI 登录场景测试

包含三个场景：正常登录、密码错误、用户名为空。

每个场景独立执行，互不影响。
