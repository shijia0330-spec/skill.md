---
name: mobile-analysis
description: 移动端页面分析 — 从 page source / uiautomator dump 提取可交互元素，输出定位候选 JSON。
---

# 移动端分析

对标 `UI-skills/分析/00_DOM扫描.md`，用于 **Appium 定位器设计**。

## 输入

| 方式 | 说明 |
|------|------|
| **A. adb dump** | `adb shell uiautomator dump` → 拉取 XML |
| **B. Appium session** | 运行中 `driver.page_source` |
| **C. 截图 + 人工** | 辅助，不替代结构 dump |

## 工作流

### Step 1：获取 page source

```bash
# 原生 Android
adb shell uiautomator dump /sdcard/window_dump.xml
adb pull /sdcard/window_dump.xml output/mobile_dump.xml

# 或 Appium 脚本失败后自动保存（codegen 已生成）
# output/appium_artifacts/<用例名>_source.xml
```

### Step 2：扫描为 JSON

```bash
python3 mobile-skills/执行/scripts/scan_page_source.py \
  -i output/mobile_dump.xml \
  -o output/mobile_elements.json
```

产出字段示例：

```json
{
  "elements": [
    {
      "tag": "android.widget.Button",
      "text": "登录",
      "content_desc": "login_button",
      "resource_id": "com.example:id/login_btn",
      "clickable": true,
      "suggested_by": "accessibility_id",
      "suggested_locator": "login_button"
    }
  ]
}
```

### Step 3：写入 spec

优先采用 `suggested_by` + `suggested_locator` 填入 `templates/appium_*.md` 的 `steps`。

## WebView

1. `switch_context` → `WEBVIEW`  
2. 再 dump / `page_source`（H5 为 HTML，可用 `css` / `xpath`）  
3. 秒杀 H5 见 `templates/appium_seckill_h5.md`

## 输出

`mobile_元素分析_<页面>_<日期>.json` + 定位优先级说明（accessibility_id > resource-id > 短 xpath）。
