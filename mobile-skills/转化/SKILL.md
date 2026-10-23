---
name: mobile-md-conversion
description: 将 UI 精简用例或步骤表转为 appium_pytest flows（规则映射 + 一键脚本，定位器需人工校准）。
---

# UI 精简用例 → Appium spec 转化

对标 `UI-skills/转化/SKILL.md`：**规则映射** + `codegen/md_cases_to_appium_spec.py` 一键流水线。适合 P0 主路径；**不承诺**几千条用例全自动转完且全绿。

## 一键流水线（推荐）

与 UI 转化共用前两步（筛选 + ui_automation JSON），第三步规则映射为 Appium steps：

```bash
# 输入须为含 Web/UI 步骤的功能用例（纯 API 用例请先走 UI-skills/转化 或 UI 精简）
python3 codegen/md_cases_to_appium_spec.py \
  -i output/seckill_ui_cases.md \
  -o templates/seckill_appium_from_cases.md \
  --module 秒杀 --tier A,B,C \
  --app-package com.example.app --app-activity .MainActivity

./generate.sh templates/seckill_appium_from_cases.md --env appium
./run_appium.sh output/seckill_appium_from_cases.py
```

| 步骤 | 脚本 | 产出 |
|------|------|------|
| 1 筛选 | `md_ui_filter.py` | `output/_pipeline/*_ui_candidates.json` |
| 2 UI 步骤 | `md_to_ui_automation.py` | `output/_pipeline/*_ui_automation.json` |
| 3 Appium 映射 | `testcase_to_appium_spec.py` | `templates/*_appium_from_cases.md` |

已有 `ui_automation.json` 时可跳过前两步：

```bash
python3 codegen/testcase_to_appium_spec.py \
  -i output/_pipeline/seckill_ui_automation.json \
  -o templates/seckill_appium_from_cases.md
```

## 输入

| 文件 | 必需 |
|------|------|
| `*_testcases.md` 或 UI 精简产出 | ✅ |
| `mobile_elements.json`（分析产出） | 推荐（校准 accessibility_id） |
| `capability_checklist.md` 已核对 | 推荐 |

## 动作映射表

| UI / 用例步骤 | appium step |
|---------------|-------------|
| 打开 URL / 进入页面 | `switch_context: WEBVIEW` + `open_url` |
| 点击「登录」 | `click` by `accessibility_id` |
| 输入用户名/密码 | `fill` + `input` |
| 等待 N 秒 | `wait_timeout_ms` |
| 滑动列表 | `scroll` direction down |
| 下拉刷新 | `swipe` 或 `scroll` |
| 允许定位/通知 | `permission_allow` |
| 返回 | `back` |
| 断言文案可见 | `expect: text_in_page_source` |

实现见 `codegen/ui_automation_to_appium.py`。

## 输出 spec 骨架

```yaml
kind: appium_pytest
base_url: http://192.168.x.x:5173
driver_scope: class
setup:
  kind: test_init
capabilities:
  platformName: Android
  automationName: UiAutomator2
  appPackage: ...
  appActivity: ...
flows:
  - name: TC-XXX-登录
    layer: H
    priority: P0
    steps: [...]
    expect: [...]
```

## 转化原则

1. **一条 UI 用例 → 一个 flow**（或合并同 setup 的 smoke）  
2. **WebView 步骤前**加 `switch_context: WEBVIEW`（脚本自动插入）  
3. **权限弹窗**在 `ensure_logged_in` 类步骤前加 `permission_allow`  
4. 定位器从 `mobile_elements.json` 的 `suggested_locator` **人工复制校准**，勿盲信自动生成的 accessibility_id  
5. 生成：`./generate.sh templates/my_appium.md --env appium` → `./run_appium.sh output/my_appium.py`

## 不做

- 不保证复杂 SPA / 原生控件 100% 自动映射正确  
- 不替代 `testcase-skills/生成` 写功能用例  
- 不替代 `mobile-skills/分析` 的 page_source 扫描与元素注册
