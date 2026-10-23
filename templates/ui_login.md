---
kind: ui_pytest_playwright
base_url: http://your-server:5173  # 秒杀财务 Web 前端
viewport:
  width: 1280
  height: 720
# storage_state: output/.auth/login.json  # 可选：注入 cookie 跳过登录
# 可选：从选择器注册表引用定位器（跨文件共享）
# page_objects:
#   - name: loginPage
#     path: /login
#     registry_key: loginPage  # 从 output/selectors.json 加载
#     elements:
#       - name: username
#         registry_key: placeholder:Username  # 注册表优先
#       - name: password
#         registry_key: placeholder:Password
steps:
  - action: ensure_logged_in
    path: /login
    # username: admin        # 可写死，或留空走环境变量 TEST_USERNAME
    # password: admin123     # 可写死，或留空走环境变量 TEST_PASSWORD
    # 默认自动检测中英文登录页（用户名/Username、密码/Password）
    # 非标准登录页时自定义字段名：
    # username_field: Email
    # password_field: Password
    # login_button_text: Sign in
    # 登录后额外操作（选公司/2FA/角色选择/同意协议等），没有则删除此块
    # post_login_steps:
    #   - action: wait_for_text
    #     text: "选择企业"
    #   - action: click
    #     l1_role: button
    #     l1_name: 演示公司
    #   - action: wait_for_url
    #     pattern: "**/dashboard"
  - action: goto
    path: /dashboard
expect:
  - type: visible_text
    text: "仪表盘"
    exact: false
---

# UI 登录流程测试（双保险模式）

标准登录场景：`ensure_logged_in` 双保险（storage_state + 表单登录）→ 进入仪表盘。

## 双保险逻辑

1. storage_state 文件存在 → Playwright context 直接注入 cookie，多数情况跳过登录表单
2. ensure_logged_in 等待 SPA 路由稳定 → 检测登录页 URL 或登录表单 → 填表登录

## 表单定位

用户名/密码走 `fill_with_heal`，四级降级链：

| 级别 | 策略 | 说明 |
|------|------|------|
| L1 | label / placeholder | Playwright 原生 API |
| L2 | DOM 推断 | id/name/placeholder/aria-label 模糊匹配 |
| L3 | input type 扫描 | `input[type="text"]` / `input[type="password"]` |
| L4 | 多语言 fallback | 用户名→Username→user→Email |

## 登录按钮

优先 `click_with_heal`，失败再走多语言降级链（登录/Login/Sign in）。

## 登录成功判定

URL 不再含 `/login`、`/signin`、`/auth/login` 等登录页路径。

## 多语言支持

默认自动检测中文（用户名/密码）和英文（Username/Password）登录页。非标准登录页时通过 `username_field`/`password_field`/`login_button_text` 自定义。

## 登录后额外操作

如果系统登录后需要选公司、2FA 验证、同意协议等，在 `ensure_logged_in` 下加 `post_login_steps` 列表。

## 选择器注册表（可选）

先用 `scan_page_dom.py` 扫描页面，再用 `selector_registry.py` 导入注册表：

```bash
python3 UI-skills/分析/scripts/scan_page_dom.py --url http://your-server:8080/login
python3 UI-skills/分析/scripts/selector_registry.py import output/dom-scan/dom_login.json
```

然后在 spec 的 `page_objects` 中引用 `registry_key`，定位器从 `output/selectors.json` 自动加载，跨测试文件共享。

## Allure 报告

```bash
pip install allure-pytest allure-playwright
pytest output/ui_login.py -v --alluredir=allure-results
allure serve allure-results
```

失败时自动截图并附加到报告。

## 环境变量

- `TEST_BASE_URL` — 前端地址（优先级高于 spec 中的 base_url）
- `TEST_USERNAME` / `TEST_PASSWORD` — 登录账号密码
- `UI_LOCATOR_TIMEOUT_MS` — 策略链总超时（默认 15000ms）

## 数据驱动测试（data_source）

使用 `flows` + `data_source` 让 UI 测试从 CSV 读取多组账号数据：

```yaml
flows:
  - name: 多用户登录测试
    data_source: output/users.csv  # data_factory csv_export 输出
    steps:
      - action: ensure_logged_in
        path: /login
        # username/password 留空，自动从 CSV 读取
      - action: goto
        path: /dashboard
    expect:
      - type: visible_text
        text: "仪表盘"
        exact: false
```

**CSV 格式（data_factory 导出）：**

```csv
id,username,password_hash,email
1,user_001,pbkdf2:sha256:...,user001@test.com
2,user_002,pbkdf2:sha256:...,user002@test.com
```

**生成结果：** CSV 每行生成一条 pytest 用例，`ensure_logged_in` 自动从 CSV 的 `username`/`password` 列读取账号密码。

**与 data_factory 衔接：**

```bash
# 1. data_factory 造数 + 导出 CSV
python3 codegen/run_spec.py templates/data_factory.md -o output/data_factory.py
cd output && python3 data_factory.py
# 输出: output/users.csv（含 username, password_hash 等字段）

# 2. UI spec 引用该 CSV
cd ..
python3 codegen/run_spec.py templates/ui_login.md -o output/ui_login.py

# 3. 运行（自动 parametrize 展开）
pytest output/ui_login.py -v
```

**注意：** CSV 列名需与 `ensure_logged_in` 期望的变量名匹配：
- `username` → 用户名
- `password` 或 `password_hash` → 密码（如果列名是 `password_hash`，需配置 `password_field: password_hash`）
