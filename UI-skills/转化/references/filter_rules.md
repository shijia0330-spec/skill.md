# UI 可执行性打分规则

供 `codegen/md_ui_filter.py` 与 Agent 复核。分 **文本规则** 与 **三件套增强** 两阶段。

---

## 1. 档位定义

| 档位 | 分数 | 转化策略 |
|------|------|----------|
| **A** | ≥ 60 | 本期转 `ui_automation` + pytest |
| **B** | 40～59 | 模板化后转 |
| **C** | 20～39 | 合并为页面级冒烟 |
| **exclude** | &lt; 20 或硬排除 | 不转自动化 |

`page_unavailable` 标签 → 强制 **exclude**。

---

## 2. 文本加分（第一阶段）

| 关键词 / 模式 | 加分 |
|---------------|------|
| 点击、点「 | +15 |
| 输入、填写 | +15 |
| 搜索、重置、收起、展开 | +12 |
| 对话框、弹窗、抽屉 | +15 |
| 提交、确认、取消 | +12 |
| 勾选、全选 | +10 |
| 必填、校验 | +12 |
| 编号前缀 C/V/X/U | +8 |

---

## 3. 文本减分 / 排除

| 关键词 | 处理 |
|--------|------|
| 截图对照 | −30 |
| 列展示- | −25 |
| 样例行- | −20 |
| 无 JS 错误、无白屏 | exclude |
| 无权限 | `needs_role`，−10 |

---

## 4. 三件套增强（第二阶段）

需传入 `--manifest` / `--specs-json` / `--screenshots-dir` 至少其一。

| 条件 | 调整 | 标签 |
|------|------|------|
| PNG 不存在 | −15 | `missing_screenshot` |
| manifest `status≠ok` 或 404 | 分数压至 ≤15，exclude | `page_unavailable` |
| manifest `kind=dialog/modal` | `template_hint=dialog_crud` | — |
| 用例含搜索/筛选 + spec 有 `filters` | +8 | `filter_verified` |
| 点「X」+ spec.`actions` 含 X | +8 | `action_verified` |
| 点「X」+ actions 有列表但无 X | −12 | `stale_action` |
| 列展示 + spec.`columns` 匹配 | 分数上限 35 | `column_display_merge` |
| 新增/修改 + spec 有 `fields_required` | `dialog_crud` | — |

---

## 5. 评审优先级

输出候选后，Agent/人工按此顺序处理：

1. **A + `action_verified`** → 直接进转化队列  
2. **A + `stale_action`** → 核对用例或更新 specs JSON  
3. **B + `filter_verified`** → 合并为参数化筛选用例  
4. **C + `column_display_merge`** → 每页 1 条 `test_table_headers`  
5. **`page_unavailable`** → 从自动化范围剔除  

---

## 6. 合并建议

同一截图段内：

- 多个 `列展示-*` → 1 条 `test_table_headers_visible`  
- `截图对照` + `URL 直达` → 1 条 `test_page_loads`  
- 多个 `筛选-*` → 1 条参数化 `list_filter_search`  
