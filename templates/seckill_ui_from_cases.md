---
kind: ui_pytest_playwright
flows:
- expect:
  - type: alert_visible
    text: 请输入
    exact: false
  steps:
  - action: goto
    path: /login
    wait_until: networkidle
  - action: fill
    value: admin
    l1_placeholder: 用户名
  - action: click
    l1_role: button
    l1_name_regex: 登\s*录
  name: 登录页加载-表单可交互
- expect:
  - type: alert_visible
    text: 请输入
    exact: false
  steps:
  - action: goto
    path: /login
    wait_until: networkidle
  - action: fill
    value: admin
    l1_placeholder: 用户名
  - action: fill
    value: ''
    l1_placeholder: 密码
  - action: click
    l1_role: button
    l1_name_regex: 登\s*录
  name: 密码为空校验
- expect:
  - type: visible_text
    text: 商品
    exact: false
  steps:
  - action: goto
    path: /login
    wait_until: networkidle
  - action: fill
    value: admin
    l1_placeholder: 用户名
  - action: fill
    value: admin123
    l1_placeholder: 密码
  - action: click
    l1_role: button
    l1_name_regex: 登\s*录
  - action: ensure_logged_in
    path: /products
    wait_until: networkidle
    timeout_ms: 60000
  name: 正确凭证登录进入商品列表
- expect:
  - type: visible_text
    text: 还没有账号
    exact: false
  steps:
  - action: goto
    path: /login
    wait_until: networkidle
  - action: fill
    value: admin
    l1_placeholder: 用户名
  - action: fill
    value: __ENV__:TEST_WRONG_PASSWORD
    l1_placeholder: 密码
  - action: click
    l1_role: button
    l1_name_regex: 登\s*录
  name: 错误密码登录失败提示
- expect:
  - type: alert_visible
    text: 请输入
    exact: false
  steps:
  - action: goto
    path: /login
    wait_until: networkidle
  - action: fill
    value: ''
    l1_placeholder: 用户名
  - action: click
    l1_role: button
    l1_name_regex: 登\s*录
  name: 用户名为空校验
- expect:
  - type: alert_visible
    text: 请输入
    exact: false
  steps:
  - action: goto
    path: /register
    wait_until: networkidle
  - action: fill
    value: ''
    l1_placeholder: 用户名
  - action: click
    l1_role: button
    l1_name_regex: 注\s*册
  name: 注册页打开-表单可交互
- expect:
  - type: visible_text
    text: 商品
    exact: false
  steps:
  - action: ensure_logged_in
    path: /products
    wait_until: networkidle
    timeout_ms: 60000
  name: 已登录打开商品列表页
- expect:
  - type: visible_text
    text: 商品
    exact: false
  steps:
  - action: ensure_logged_in
    path: /products
    wait_until: networkidle
    timeout_ms: 60000
  name: 商品列表可见表头或商品文案
setup:
  kind: test_init
  path: /api/test/init
viewport:
  width: 1440
  height: 900
batch:
  fail_fast: false
  login_once: true
  flows:
  - 登录页加载-表单可交互
  - 密码为空校验
  - 正确凭证登录进入商品列表
  - 错误密码登录失败提示
  - 用户名为空校验
  - 注册页打开-表单可交互
  - 已登录打开商品列表页
  - 商品列表可见表头或商品文案
base_url: http://127.0.0.1:5173
---
# 从功能用例生成的 UI spec · seckill_ui_from_cases

> 由 `md_cases_to_ui_spec.py` 于 2026-07-02 00:31 UTC 自动生成
> 源用例：`seckill_ui_cases.md` · UI-SECKILL-01, UI-SECKILL-05, UI-SECKILL-02, UI-SECKILL-03, UI-SECKILL-04, UI-SECKILL-08, UI-SECKILL-06, UI-SECKILL-07

**账号**：`admin / admin123`（秒杀财务系统）

**测试数据铺底**：`POST /api/test/init`（API 默认 `http://your-server:5001`）

| 变量 | 说明 |
|------|------|
| `SECKILL_SEARCH_NAME` | 商品列表搜索 |
| `SECKILL_DUPLICATE_USERNAME` | 重复注册（默认 admin） |

**环境变量**（PowerShell 示例）：

```powershell
$env:TEST_BASE_URL = "http://your-server:5173"
$env:TEST_USERNAME = "admin"
$env:TEST_PASSWORD = "admin123"
$ts = Get-Date -Format 'yyyyMMddHHmmss'
$env:TEST_UNIQUE_ID = "skills-demo-$ts"
$env:SECKILL_PRODUCT_NAME = "秒杀演示商品"
$env:UI_STORAGE_STATE = "output/.auth/ui_storage.json"
```

**生成与执行**：

```powershell
python codegen/run_spec.py templates/seckill_ui_from_cases.md -o output/seckill_ui_from_cases.py
python -m pytest output/seckill_ui_from_cases.py -v --headed -s
```

报告：`output/allure-report-ui/standalone.html`

