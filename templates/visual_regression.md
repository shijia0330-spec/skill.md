---
kind: visual_regression
base_url: http://your-server:5000  # seckill_finance_system
viewport:
  width: 1280
  height: 720
threshold: 0.2
max_diff_pixels: 100
pages:
  - name: 首页
    path: /
    wait_ms: 2000
  - name: 登录后仪表盘
    path: /dashboard
    wait_ms: 2500
    actions:
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
      - action: wait_timeout_ms
        ms: 800
---

# UI 视觉回归（Playwright 截图基线对比）

对关键页面做截图并与基线 PNG 对比；像素差异超过 `threshold` / `max_diff_pixels` 则失败。

**用法**

```bash
./generate.sh templates/visual_regression.md
cd output && pytest visual_regression.py --update-snapshots -v   # 首次：生成基线
cd output && pytest visual_regression.py -v                      # 后续：对比基线
```

**frontmatter 说明**（与 `codegen/run_spec.py` 一致）

- `pages[]`: 每个页面 `name`（截图名）、`path`（相对 `base_url`）、`wait_ms`（截图前等待毫秒）。
- `actions[]`（可选）: 截图**前**执行；支持 `fill` / `click` / `wait_timeout_ms` / `goto`，字段与 UI 模板里 `l1_label`、`l1_role`、`l1_name` 等一致。

首次务必带 `--update-snapshots` 生成基线，再在 CI 或本地去掉该参数做回归。
