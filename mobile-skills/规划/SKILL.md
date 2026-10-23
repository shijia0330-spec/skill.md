---
name: mobile-planning
description: Plans Appium mobile automation scope, devices, versions, in/out-of-scope paths before coding. Use for native or hybrid app E2E planning.
---

# 移动端自动化 — 先定范围再写脚本

要做 **原生 / 混合 App**（或壳内 H5）的自动化，但还没定测哪几条、用什么机、怎么算通过时，先用这份把**可执行边界**写清楚；执行阶段再按 `mobile-skills/执行` 落代码。

默认工具链：**Appium 2.x + Python + pytest**（团队若统一 Maestro、Detox 等，在计划里写死一项即可，别混着说）。

---

## 1. 计划里一般写清啥

**范围**  
哪些端（Android / iOS 或其一）、哪些版本、哪几条主路径要自动化；明确**不做的**。

```yaml
scope:
  platforms:
    - android          # API 29+ (Android 10+)
    - ios              # iOS 15+ (需 Xcode 环境)
  in_scope:
    - 用户注册/登录
    - 商品浏览/搜索
    - 加入购物车/下单
  not_in_scope:
    - 支付真扣款（走 API 验证）
    - 第三方登录（微信/Apple）
    - 生产环境
```

**设备**  
真机还是模拟器、最低系统版本、屏幕分辨率是否要覆盖。

```yaml
devices:
  android:
    - emulator: "Pixel 6 API 33"     # 主测
    - real_device: "Samsung S23"     # 回归前过一遍
  ios:
    - simulator: "iPhone 14 iOS 16"  # 主测
    - real_device: "iPhone 13"       # 回归前过一遍
```

**包体**  
从哪拿 APK/IPA（CI 产物、测试包链接）；是否要每次干净安装；升级覆盖要不要测。

```bash
# 从 CI 下载最新构建
curl -o app.apk "https://ci.example.com/job/latest/app-release.apk"

# 安装到设备
adb install -r app.apk
```

**定位策略**  
优先可测性好的：**accessibility id / content-desc / testID**；少依赖长 XPath 和纯坐标。

```python
#  好的定位
driver.find_element(AppiumBy.ACCESSIBILITY_ID, "login_button")

#  次选：resource-id
driver.find_element(AppiumBy.ID, "com.example.app:id/login_btn")

#  避免：纯 XPath
driver.find_element(AppiumBy.XPATH, "//android.widget.Button[3]")

#  避免：纯坐标
# TouchAction(driver).tap(x=100, y=200).perform()
```

WebView 里页面按 H5 那套，但要写清是否切 `context`。

**断言**  
看什么算过：控件文案、页面标识、接口落库（若走联合校验要说清）。

```python
# 好的断言
assert driver.find_element(AppiumBy.ID, "welcome_text").text == "欢迎回来"

# 好的断言：等元素出现再判断
WebDriverWait(driver, 10).until(
    EC.text_to_be_present_in_element((AppiumBy.ID, "status"), "登录成功")
)
```

**数据与环境**  
测试账号、推送/定位/相册等权限弹窗谁点、脏数据怎么清。

**与包内 data_factory / test_init 对齐：**

```yaml
setup:
  kind: test_init
  path: /api/test/init
base_url: http://192.168.x.x:5001
```

- H5（5173）与铺底 API（5001）均须 **宿主机 LAN IP**，勿 `127.0.0.1`
- 跳过铺底：`setup: none`

## 2. 规划产出模板

写完计划后，输出一份可执行的 YAML：

```yaml
# mobile_test_plan.yaml
project: "电商App V3"
platforms: ["android", "ios"]
toolchain: "Appium 2.x + Python + pytest"

modules:
  - name: "登录注册"
    pages: ["LoginPage", "RegisterPage"]
    cases:
      - "新用户注册→自动登录"
      - "已注册用户密码登录"
      - "短信验证码登录"
      - "退出登录"
    priority: "P0"
    devices: ["android_emulator"]
  
  - name: "商品"
    pages: ["HomePage", "SearchPage", "ProductDetailPage"]
    cases:
      - "首页推荐加载"
      - "关键词搜索"
      - "商品详情展示"
      - "加入购物车"
    priority: "P0"
    devices: ["android_emulator", "ios_simulator"]

not_in_scope:
  - "支付回调"
  - "推送通知"
  - "性能压测"
```

---

## 3. 和「浏览器 E2E」的差别（避免混谈）

| 维度 | 浏览器 Playwright | 手机 App |
|------|-------------------|----------|
| 驱动对象 | 网页 | 系统 + 应用进程 |
| 常见坑 | 选择器飘 | 权限弹窗、软键盘挡输入、后台被杀 |
| 稳定性保障 | testid / role | accessibility id、开发埋 testID |
| 启动速度 | 快（1-2 秒） | 慢（15-30 秒，含 driver 初始化） |
| 并行难度 | 低（无状态） | 高（需多设备矩阵） |

---

## 4. 输出给谁

执行侧生成的用例、PageObject、流水线配置，都应能追溯到本计划里的范围与优先级。

---

## 5. 底线

- 计划阶段别承诺「全机型矩阵 nightly 全绿」；先小范围跑稳，再扩端扩版本
- 移动端自动化天然比 Web 脆弱，计划里要预留 20% 的时间用于维护
- iOS 真机自动化需要开发者证书和 provisioning profile——计划阶段就要确认谁提供
