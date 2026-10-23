# md_ui_filter 输出格式

---

## 1. JSON 顶层

```json
{
  "source": "output/秒杀财务Web_testcases.md",
  "inputs": {
    "markdown": "...",
    "manifest": "...",
    "specs_json": "...",
    "screenshots_dir": "..."
  },
  "generated_at": "2026-06-09T12:00:00+00:00",
  "stats": {
    "total": 7484,
    "tier_a": 1800,
    "enrichment_used": true,
    "screenshot_verified": 6200,
    "action_verified": 2100,
    "stale_action": 340,
    "page_unavailable": 45
  },
  "candidates": []
}
```

---

## 2. candidates[] 单条字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `case_id` | string | 如 `VC-004-MAIL-L04` |
| `title` | string | 用例标题 |
| `priority` | string | P0/P1/P2 |
| `tier` | string | A / B / C / exclude |
| `score` | int | 0～100（含三件套调整后） |
| `screenshot` | string | 关联 PNG 文件名 |
| `screenshot_path` | string | 绝对路径（若 `--screenshots-dir`） |
| `screenshot_exists` | bool | PNG 是否存在 |
| `page_kind` | string | manifest：`page`/`dialog`/`panel` |
| `capture_status` | string | manifest：`ok`/`failed` |
| `menu_path` | string | 菜单链 |
| `page_path` | string | URL path |
| `page_url` | string | 完整 URL |
| `steps` | string[] | 检查点原文 |
| `tags` | string[] | 见 filter_rules.md |
| `template_hint` | string | 转化模板建议 |
| `ui_elements` | object | 来自 specs JSON 的摘要 |
| `enriched` | bool | 是否经过三件套增强 |
| `automation_ready` | bool | tier 为 A 或 B |

### ui_elements 形状

```json
{
  "page_type": "list",
  "filters": ["邮箱", "用户名"],
  "actions": ["新增邮箱账号", "批量删除"],
  "columns": ["编号", "邮箱"],
  "fields_required": ["邮箱", "用户名"],
  "row_actions": ["修改", "删除"]
}
```

---

## 3. CSV 列

`case_id,title,priority,tier,score,screenshot,screenshot_exists,page_kind,page_path,menu_path,template_hint,tags`

---

## 4. _summary.md

含：三件套是否启用、交叉验证统计、Top 页面、首期建议。
