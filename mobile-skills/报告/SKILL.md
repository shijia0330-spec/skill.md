---
name: mobile-report
description: 移动端/Appium 测试报告 — 汇总 pytest 结果、page_source、截图与 Allure，产出可评审的 Markdown/HTML。Appium 跑完后归档时使用。
---

# 移动端测试报告

Appium 流水线最后一步：**把真机/模拟器跑出来的结果变成能评审、能归档的报告**。

与 `load-testing/报告/SKILL.md` 对齐：本 Skill 负责**解读与出报告**，不负责写 spec 或 `./run_appium.sh` 执行。

---

## 输入

| 来源 | 路径 | 说明 |
|------|------|------|
| pytest 进度 | `output/reports/progress.md` / `progress.json` | `run_appium.sh` 默认开启 `PROGRESS_REPORT=1` |
| 失败缺陷草稿 | `output/bugs/BUG-*.md` | `DEFECT_DRAFTS=1` 时 conftest 自动写 |
| 运行时产物 | `output/appium_artifacts/` | 失败截图、`page_source` XML |
| Allure（可选） | `output/allure-results-appium/` | 若 pytest 带 `--alluredir` |

---

## 快速使用

### 路径 A：pytest 已跑完（推荐）

```text
@mobile-skills/报告/SKILL.md

Appium 刚跑完 output/appium_seckill_h5.py，有 2 条失败。
请读 progress.json + appium_artifacts 下 page_source，出 Markdown 报告：
失败根因、建议定位修复、是否产品缺陷。
```

### 路径 B：仅 collect / 冒烟通过

```bash
./generate.sh templates/appium_e2e.md --env appium
./run_appium.sh output/appium_e2e.py --collect-only -q
cat output/reports/progress.md
```

---

## 报告必备章节

1. **概要**：设备、Appium Server、base_url、用例数、通过率  
2. **失败清单**：nodeid、错误摘要、截图/XML 路径  
3. **定位建议**：对照 `mobile_elements.json` / `scan_page_source.py` 产出  
4. **结论**：通过 / 阻塞发布 / 需补测  

---

## 与自愈 / 缺陷衔接

| 场景 | 下一步 |
|------|--------|
| 定位器漂移 | `@mobile-skills/自我修复` + `locator_healer.py` |
| 产品缺陷 | `@bug-reporter` → `defect-sync` 推送 |
| WebView 上下文错 | 检查 flow 中 `switch_context: WEBVIEW` |

---

## 命令速查

```bash
# 执行（写 progress + 失败草稿 + artifacts）
./run_appium.sh output/appium_seckill_h5.py -v

# 失败时扫描 page_source
python3 mobile-skills/执行/scripts/scan_page_source.py \
  -i output/appium_artifacts/xxx_source.xml

# 离线 healer
python3 mobile-skills/执行/scripts/locator_healer.py \
  -i output/appium_artifacts/xxx_source.xml
```

---

## 不做

- 不替代 `mobile-skills/执行` 写 spec / 生成脚本  
- 不替代 `load-testing/报告` 解读 k6/JMeter 指标  
