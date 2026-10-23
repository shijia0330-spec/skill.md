---
kind: ui_pytest_playwright
base_url: http://127.0.0.1:5001
viewport:
  width: 1280
  height: 720
flows:
  - name: 多用户登录测试
    data_source: output/users.csv
    steps:
      - action: ensure_logged_in
        path: /login
      - action: goto
        path: /dashboard
    expect:
      - type: visible_text
        text: "仪表盘"
        exact: false
---
# UI 数据驱动测试（验证 flows + data_source）

使用 data_factory 生成的 output/users.csv 作为数据源，每个用户生成一条登录测试用例。

```bash
python3 codegen/run_spec.py templates/ui_user_ddt.md -o output/ui_user_ddt.py
pytest output/ui_user_ddt.py -v
```
