---
kind: appium_pytest
appium_server: http://127.0.0.1:4723
base_url: http://your-server:5001
selector_registry: output/mobile_selector_registry.json
driver_scope: class
layer: H
priority: P0
setup:
  kind: test_init
capabilities:
  platformName: Android
  automationName: UiAutomator2
  deviceName: Android Emulator
  # 二选一：安装包路径，或已安装应用的包名+入口 Activity
  app: /path/to/your.apk
  # appPackage: com.example.app
  # appActivity: .MainActivity
flows:
  - name: 登录到首页
    steps:
      - action: wait_timeout_ms
        ms: 1500
      - action: fill
        registry_key: login.username
        by: accessibility_id
        value: username_input
        input: admin
      - action: fill
        registry_key: login.password
        by: accessibility_id
        value: password_input
        input: "admin123"
      - action: click
        registry_key: login.submit
        by: accessibility_id
        value: login_button
        wait_sec: 20
      - action: hide_keyboard
      - action: wait_timeout_ms
        ms: 800
    expect:
      - type: element_visible
        registry_key: home.title
        by: accessibility_id
        value: home_title
        wait_sec: 25
---

# App 端到端（声明式 → pytest + Appium）

与 `templates/ui_e2e.md` 类似：在 frontmatter 里写 **`capabilities`** 和 **`steps` / `flows`**，`./generate.sh` 会生成可跑的 `appium_e2e.py`。

**前置**：本机或 CI 已启动 **Appium 2**；`adb devices` 能看到设备或模拟器；把上面 `capabilities.app`（或 `appPackage` + `appActivity`）改成你的真实值。

```bash
./generate.sh templates/appium_e2e.md
./run_appium.sh output/appium_e2e.py
```

**依赖**：`pip install pytest Appium-Python-Client selenium`

**常用 step**：`click` / `fill` / `wait_timeout_ms` / `switch_context` / `back` / `hide_keyboard` / `swipe` / `scroll` / `tap` / `permission_allow` / `permission_deny` / `open_url`

**driver_scope**：默认 `class`（多 flow 共享 App session）；单条隔离用 `function`

**铺底**：默认 `setup: test_init`（session 调 `POST /api/test/init`）；跳过：`setup: none` 或 `TEST_SETUP=none`

**环境变量**：复制 `templates/.env.appium.example` → `.env.appium`，`./generate.sh ... --env appium`
