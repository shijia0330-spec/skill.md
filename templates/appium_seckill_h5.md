---
kind: appium_pytest
appium_server: http://127.0.0.1:4723
# H5 前端（手机/emulator 须能访问宿主机 LAN IP，勿用 127.0.0.1）
base_url: http://192.168.1.100:5173
# 铺底 API（test_init），可与 H5 不同端口
api_base_url: http://192.168.1.100:5001
driver_scope: class
layer: H
priority: P0
business: 秒杀H5-Chrome
selector_registry: output/mobile_selector_registry.json
setup:
  kind: test_init
  path: /api/test/init
# 模式 A（默认）：Android Chrome 直测 H5，无需自定义 APK
capabilities:
  platformName: Android
  automationName: UiAutomator2
  deviceName: emulator-5554
  browserName: Chrome
  goog:chromeOptions:
    androidPackage: com.android.chrome
    args:
      - --disable-popup-blocking
  appium:noReset: true
  appium:autoGrantPermissions: true
flows:
  - name: Chrome登录到秒杀列表
    layer: H
    priority: P0
    steps:
      - action: open_url
        url: ${TEST_BASE_URL}/login
      - action: fill
        registry_key: seckill.login.username
        by: css
        value: input[name="username"]
        input: admin
      - action: fill
        registry_key: seckill.login.password
        by: css
        value: input[name="password"]
        input: admin123
      - action: click
        registry_key: seckill.login.submit
        by: css
        value: button[type="submit"]
      - action: wait_timeout_ms
        ms: 1500
      - action: open_url
        url: ${TEST_BASE_URL}/seckill
      - action: scroll
        direction: down
        percent: 0.5
    expect:
      - type: text_in_page_source
        text: 秒杀
---

# 秒杀 H5 — Android Chrome（声明式 → pytest + Appium）

**适用**：秒杀前端 Vite `:5173` + 后端 API `:5001`；**无原生 APK 时**用 Chrome 直开 H5。

## 两种模式

| 模式 | capabilities 要点 | 何时用 |
|------|-------------------|--------|
| **A Chrome（默认）** | `browserName: Chrome` | 无壳、最快验证 H5 |
| **B WebView 壳** | `appPackage` + `appActivity`，步骤加 `switch_context: WEBVIEW` | 已有混合 App |

### 模式 B 示例（按需替换包名）

```yaml
capabilities:
  platformName: Android
  automationName: UiAutomator2
  deviceName: emulator-5554
  appPackage: com.yourcompany.seckill   # 按实际 APK 改
  appActivity: .MainActivity              # 或 .ui.SplashActivity
  appium:noReset: true
flows:
  - name: WebView登录秒杀
    steps:
      - action: permission_allow
      - action: switch_context
        name: WEBVIEW
      - action: open_url
        url: ${TEST_BASE_URL}/login
      # ... 同 Chrome 模式 fill/click ...
```

## 网络（必读）

| 环境 | 手机/emulator 应访问 | 错误示例 |
|------|----------------------|----------|
| H5 前端 `TEST_BASE_URL` | `http://<LAN IP>:5173` | `127.0.0.1:5173` |
| API 铺底 `TEST_API_BASE_URL` | `http://<LAN IP>:5001` | 仅 PC 本机可达 |

```bash
ip route get 1.1.1.1 | awk '{print $7; exit}'   # Linux 查 LAN IP
cp templates/.env.appium.example .env.appium      # 改 IP 后
./generate.sh templates/appium_seckill_h5.md --env appium
./run_appium.sh output/appium_seckill_h5.py
```

## 定位自愈

生成脚本 `_find()` 默认走 `MOBILE_SELF_HEAL=1`（`codegen/mobile_lib/locator_healer.py`）。  
失败产物：`output/appium_artifacts/*_source.xml` → 可离线跑：

```bash
python3 mobile-skills/执行/scripts/locator_healer.py -i output/appium_artifacts/xxx_source.xml \
  --by css --locator 'input[name="username"]'
```

## 依赖

```bash
pip install pytest Appium-Python-Client selenium
appium driver install uiautomator2
```
