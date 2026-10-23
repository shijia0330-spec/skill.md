---
kind: ui_pytest_playwright
base_url: http://your-server:5000
viewport:
  width: 1280
  height: 720
steps:
  - action: goto
    path: /login
  - action: fill
    l1_label: 用户名
    value: admin
  - action: fill
    l1_label: 密码
    value: "123456"
  - action: click
    l1_role: button
    l1_name_regex: "登录|登陆"
expect:
  - type: url_regex
    pattern: ".*"
---

# 说明

- **须根据真实页面改** `l1_label` / `l1_name_regex`（与 UI-skills L1 一致）。
- 需已安装：`pip install pytest playwright && playwright install chromium`
- 生成并运行：

```bash
python3 run_spec.py examples/ui_login_skeleton.md -o /tmp/gen/test_ui_login.py
pytest /tmp/gen/test_ui_login.py --headed -v
```
