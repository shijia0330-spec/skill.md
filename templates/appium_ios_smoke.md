---
kind: appium_pytest
appium_server: http://127.0.0.1:4723
base_url: http://192.168.1.100:5173
api_base_url: http://192.168.1.100:5001
driver_scope: class
layer: H
priority: P1
business: iOS-Safari-H5冒烟
selector_registry: output/mobile_selector_registry.json
setup:
  kind: test_init
  path: /api/test/init
capabilities:
  platformName: iOS
  automationName: XCUITest
  deviceName: iPhone 15
  browserName: Safari
  appium:noReset: true
flows:
  - name: Safari打开登录页
    layer: H
    priority: P1
    steps:
      - action: open_url
        url: ${TEST_BASE_URL}/login
      - action: wait_timeout_ms
        ms: 2000
      - action: click
        registry_key: ios.login.submit
        by: ios_predicate
        value: 'label == "登录"'
        wait_mode: clickable
    expect:
      - type: text_in_page_source
        text: login
---

# iOS Safari H5 冒烟（stub）

**适用**：Mac + Xcode Simulator + Appium XCUITest；Safari 直开 H5，无需 IPA。

> 真机/WebView 壳：补 `bundleId` / `app` 并按 [capability_checklist](../mobile-skills/执行/references/capability_checklist.md) 核对。

```bash
./generate.sh templates/appium_ios_smoke.md --env appium
./run_appium.sh output/appium_ios_smoke.py
```
