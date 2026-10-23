---
name: ui-md-conversion
description: >-
  Filters UI-automatable cases from large Markdown testcase docs using optional
  screenshot manifest and ui_cases_by_image.json enrichment, outputs candidate
  JSON/CSV, and guides conversion to ui_automation JSON → spec → pytest. Use when
  user has *_testcases.md with screenshots, md_ui_filter, input bundle, or batch
  Markdown-to-Playwright conversion.
---

# Markdown 用例 → UI 自动化转化

**版本**：2026-06 · **规则** 1.1

从 **几千条 Markdown 功能用例** + **截图三件套** 筛出 **可执行 UI 子集**，再接到 `UI-skills/执行` 出 pytest。

---

## 能力边界

| 做 | 不做 |
|----|------|
| 解析 `*_testcases.md` + manifest + specs JSON 联合筛选 | 9000 条 1:1 全自动转 pytest 且全绿 |
| 交叉验证动作/筛选项与页面 spec 是否一致 | 替代 `testcase-skills/生成` 写功能用例 |
| 输出候选清单（含 `ui_elements`、`screenshot_path`） | 筛选阶段对每张 PNG 跑视觉模型 |
| 指导 `ui_automation` → spec → pytest | 接口自动化（走 `api-skills`） |

---

## 标准输入包（三件套）

详见 `references/input_bundle.md`。

```text
{项目}_testcases.md          ← 必需
manifest.json                ← 强烈推荐（截图索引）
{项目}_ui_cases_by_image.json ← 强烈推荐（按钮/筛选项/列）；有 URL 时由 DOM 扫描替代/增强
screenshots/pages/*.png      ← 强烈推荐（存在性校验）
output/dom_scan/{page}.json  ← 有 URL 时强烈推荐（scan_page_dom.py）
```

**完整上游（推荐）**：

```text
有 URL:  scan_page_dom → 01_元素识别 → testcase-skills/生成 → testcase-skills/UI精简 → UI-skills/转化 → 执行
无 URL:  screenshot-skills/全站截图 → testcase-skills/生成 → testcase-skills/UI精简 → UI-skills/转化 → 执行
```

> **禁止**跳过 UI 精简：勿将 `*_testcases.md`（完整版）直接喂给 `md_cases_to_ui_spec.py`。见 `@testcase-skills/UI精简/SKILL.md`。

---

## 标准流水线（Step 0～8）

```
三件套齐备 → md_ui_filter 筛选 → 评审 → 按页元素库 → ui_automation JSON
    → spec → pytest → 执行 → 失败分流
```

| Step | 动作 | 产出 / 命令 |
|------|------|-------------|
| **0** | 核对输入包 + 环境 | `TEST_BASE_URL`、`storage_state`；见 `references/input_bundle.md` |
| **1** | **三件套筛选** | 见下方命令 |
| **2** | **评审** | 过 A/B；处理 `stale_action`；合并 C 档列展示 |
| **3** | **按页元素库** | `UI-skills/分析/01_元素识别.md` + 候选里的 `screenshot_path` |
| **4** | **候选 → ui_automation** | `references/conversion_patterns.md`；引用 `ui_elements` |
| **5** | **JSON → spec** | `python3 codegen/testcase_to_ui_spec.py -i ... -o templates/xxx.md` |
| **5′** | **一键（推荐）** | `python3 codegen/md_cases_to_ui_spec.py -i xxx_testcases.md -o templates/xxx_ui.md` |
| **6** | **生成脚本** | `python3 codegen/run_spec.py templates/xxx.md -o output/test_xxx.py` |
| **7** | **执行** | `powershell -File run_pytest_ui.ps1 output/test_xxx.py -v` |
| **8** | **失败** | `@UI-skills/自我修复` 或 `@bug-reporter` |

---

## 一键流水线（功能用例 → spec）

功能用例 Markdown 写完后，**无需手写 spec**：

```powershell
# 输入须为 UI 精简版（*_ui_cases.md），非完整 *_testcases.md
python3 codegen/md_cases_to_ui_spec.py `
  -i output/seckill_ui_cases.md `
  -o templates/ui_smoke_one_page.md `
  --module 秒杀 --tier A,B --priority P0,P1
```

产物链：`output/_pipeline/*_ui_candidates.json` → `*_ui_automation.json` → `templates/*.md`

评审后再：

```powershell
python3 codegen/run_spec.py templates/ui_e2e.md -o output/seckill_ui_from_cases.py
python3 -m pytest output/seckill_ui_from_cases.py -v --headed --collect-only
```

| 脚本 | 作用 |
|------|------|
| `codegen/md_ui_filter.py` | 筛 A/B 档候选 |
| `codegen/md_to_ui_automation.py` | 候选 → `ui_automation` JSON（规则引擎） |
| `codegen/md_cases_to_ui_spec.py` | 上述 + `testcase_to_ui_spec.py` 一键串联 |

复杂表单（多单选、联动）生成后仍需对照 DOM 微调；见 `references/conversion_patterns.md`。

---

### 三件套（推荐）

```bash
python3 codegen/md_ui_filter.py \
  -i templates/测试用例-需求文档.md \
  -o output/seckill_ui_candidates.json \
  --base-url http://your-server:5001 \
  --module "商品,库存" --summary
```

### 有截图三件套时

```bash
python3 codegen/md_ui_filter.py \
  -i templates/测试用例-需求文档.md \
  -o output/seckill_ui_candidates.json \
  --routes-file screenshot-skills/全站截图/templates/routes_seckill_core.txt \
  --tier A,B --priority P0,P1 --summary
```

### 仅 Markdown（降级）

```bash
python3 codegen/md_ui_filter.py \
  -i output/xxx_testcases.md \
  -o output/xxx_ui_candidates.json
```

### 常用参数

| 参数 | 说明 |
|------|------|
| `--tier A,B` | 只输出档位 |
| `--priority P0,P1` | 优先级过滤 |
| `--module "邮箱,短信"` | 菜单关键词 |
| `--limit 500` | 限制条数 |
| `--require-screenshot` | 仅保留 PNG 存在的用例 |
| `--summary` | 额外写 `_summary.md` |

---

## 三件套增强逻辑（筛选时自动）

| 信号 | 效果 |
|------|------|
| `manifest.kind=dialog` | `template_hint` → `dialog_crud` |
| `manifest.status≠ok` / 404 页 | 标 `page_unavailable`，档位 exclude |
| 用例点「搜索」且 spec 有 `filters` | +分，`filter_verified` |
| 用例点「X」且 spec.`actions` 含 X | +分，`action_verified` |
| 用例点「X」但 actions 无 X | −分，`stale_action`（疑似过期用例） |
| `列展示-*` 且 spec.`columns` 匹配 | 降档，`column_display_merge` |
| PNG 文件不存在 | `missing_screenshot`，−分 |

---

## 三级漏斗

| 档位 | 含义 | 首期建议 |
|------|------|----------|
| **A** | 高可执行且 `action_verified` 优先 | 转 pytest |
| **B** | 可模板化 | 参数化 |
| **C** | 列展示/样例行 | 合并或跳过 |
| **exclude** | 404 页、纯视觉、无 JS 错误 | 手工 |

三件套后经验比例：

```text
9000 条 → ~2500 文本候选 → ~1500 三件套校验后 A+B → ~300～500 首期 pytest
```

---

## 新文档接入检查单

```
- [ ] 四件套路径齐（见 input_bundle.md）
- [ ] Markdown 段头含 ### [图] xxx.png 与 > 路径：
- [ ] manifest.items[].file 与 Markdown 截图名一致
- [ ] specs JSON 的 image 字段与 PNG 文件名一致
- [ ] storage_state 或 TEST_USERNAME/PASSWORD 可用
- [ ] 跑三件套 md_ui_filter，看 stale_action 数量是否可接受
- [ ] 首期单模块 ≤10 页试点执行
```

---

## 子文档索引

| 文件 | 用途 |
|------|------|
| `references/input_bundle.md` | **三件套标准输入** |
| `references/filter_rules.md` | 文本 + 三件套打分规则 |
| `references/md_case_schema.md` | Markdown 结构约定 |
| `references/conversion_patterns.md` | 转 ui_automation 模板 |
| `references/output_formats.md` | JSON/CSV 字段 |
| **`testcase-skills/UI精简/SKILL.md`** | **完整用例 → *_ui_cases.md（本流水线上游）** |
| `screenshot-skills/全站截图/SKILL.md` | 产出 manifest + PNG |
| `UI-skills/执行/SKILL.md` | 生成与执行 |

---

## AI 编辑器快捷引用

```text
@UI-skills/转化/SKILL.md
@templates/测试用例-需求文档.md
@templates/需求文档.md
按 REST 商品/库存模块筛 UI 候选并出 stale_action 清单
```

```text
@UI-skills/转化/SKILL.md
@output/seckill_ui_candidates.json
把 A 档转为 ui_automation JSON，生成 templates/ui_login.md 并 pytest
```
