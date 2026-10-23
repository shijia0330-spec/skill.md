---
kind: appium_pytest
appium_server: http://your-server:4723
capabilities:
  platformName: Android
  automationName: UiAutomator2
  deviceName: emulator-5554
  appPackage: com.example.demo
  appActivity: .ui.login.LoginActivity
steps:
  - action: click
    by: id
    value: com.example.demo:id/btn_guest
  - action: wait_timeout_ms
    ms: 500
expect:
  - type: element_visible
    by: xpath
    value: //*[@text='首页']
---

# 最小骨架：仅作 generate 校验示例，定位请按实际控件改
