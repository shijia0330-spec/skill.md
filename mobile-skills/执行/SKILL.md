---
name: mobile-exec
description: Runs Appium 2.x + pytest mobile flows from specs and codegen (e.g. kind appium_pytest). Use after mobile planning is fixed for implementation and execution.
---

# 移动端自动化 — 写脚本与跑起来

在**范围已定**（见 `mobile-skills/规划`）的前提下，用代码驱动真机或模拟器完成安装、启动、操作、断言。

**默认栈**：**Appium 2.x + Python + pytest**。声明式入口：**`kind: appium_pytest`** → **`./generate.sh`** → **`./run_appium.sh`**。

**索引**：`mobile-skills/索引.md`

---

## 1. 快速开始

```bash
cp templates/.env.appium.example .env.appium   # 改 LAN IP、设备 serial
appium &                                        # Appium 2
./generate.sh templates/appium_e2e.md --env appium
./run_appium.sh output/appium_e2e.py
```

秒杀 WebView：`templates/appium_seckill_h5.md`（**base_url 用宿主机 LAN IP，勿 127.0.0.1**）

---

## 2. 声明式 Spec 要点

```yaml
kind: appium_pytest
appium_server: http://127.0.0.1:4723
base_url: http://192.168.1.100:5001    # 铺底 + H5；手机可达地址
driver_scope: class                     # 默认 class，多 flow 共享 session
layer: H
priority: P0
setup:
  kind: test_init                       # session POST /api/test/init
capabilities:
  platformName: Android
  automationName: UiAutomator2
  appPackage: com.example.app
  appActivity: .MainActivity
flows:
  - name: 登录
    steps:
      - action: permission_allow
      - action: click
        by: accessibility_id
        value: login_button
```

### 支持的 step

| action | 说明 |
|--------|------|
| `click` / `fill` | 定位 + 操作（WebView 可用 `by: css`） |
| `wait_timeout_ms` | 固定等待 |
| `switch_context` | `NATIVE_APP` 或 `WEBVIEW`（部分匹配） |
| `open_url` | H5 导航，支持 `${TEST_BASE_URL}` |
| `swipe` | start_x/y, end_x/y, duration_ms |
| `scroll` | direction: down/up/left/right |
| `tap` | x, y |
| `permission_allow` / `permission_deny` | 系统权限弹窗 |
| `back` / `hide_keyboard` | 返回 / 收键盘 |

codegen **自动生成**：`driver` fixture（scope 可配）、**失败截图 + page_source**、**Allure 标记**、**test_init 铺底**。

---

## 3. driver_scope

| 值 | 适用 |
|----|------|
| `class`（默认） | 同文件多 flow，只启停 App 一次 |
| `function` | 每条用例完全隔离，慢但干净 |

---

## 4. 混合 App / WebView

```yaml
- action: switch_context
  name: WEBVIEW
- action: open_url
  url: ${TEST_BASE_URL}/login
- action: fill
  by: css
  value: input[name="username"]
  input: admin
```

切回原生：`switch_context` + `NATIVE_APP`

---

## 5. 手势（W3C / mobile: 命令）

声明式用 `swipe` / `scroll` / `tap` 即可；手写脚本示例：

```python
# 推荐：mobile 扩展（Appium 2）
driver.execute_script("mobile: swipeGesture", {
    "left": 100, "top": 500, "width": 200, "height": 400,
    "direction": "up", "percent": 0.75,
})
driver.execute_script("mobile: clickGesture", {"x": 500, "y": 1200})
```

> 勿用已废弃的 `TouchAction`（Appium 2/3）。

---

## 6. 权限弹窗

```yaml
- action: permission_allow
  button_text: 允许
```

或 spec 里 `appium:autoGrantPermissions: true`（Android 6+ 部分权限）

---

## 7. 测试数据（铺底）

与 API/UI 一致：

```yaml
setup:
  kind: test_init
  path: /api/test/init
# 或
setup:
  kind: data_factory
  script: output/data_factory.py
```

跳过：`setup: none` 或环境变量 `TEST_SETUP=none`

**H5 URL 与铺底 API 均须手机可达** — 见 `capability_checklist.md`。

---

## 8. 报告与产物

- 失败自动写入 `output/appium_artifacts/<用例>_fail.png` 与 `_source.xml`（codegen 内置）
- Allure：`layer` / `priority` / `business` 写入 `@pytest.mark.allure_*`
- 分析 dump：`mobile-skills/执行/scripts/scan_page_source.py`

---

## 参考

| 文件 | 用途 |
|------|------|
| `references/capability_checklist.md` | 执行前检查 |
| `../templates/appium_e2e.md` | 原生冒烟 |
| `../templates/appium_seckill_h5.md` | 秒杀 WebView |
| `../run_appium.sh` | 健康检查 + pytest |
| `mobile-skills/分析` | page source → JSON |
| `mobile-skills/转化` | UI 用例 → flows |

Web 主场景：`UI-skills/执行`
