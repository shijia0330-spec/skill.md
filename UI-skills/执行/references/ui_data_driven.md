---
name: ui-data-driven
description: UI 数据驱动 — flow 级 parametrize + 步骤变量 + capture，同一套 steps 多组数据展开多条 pytest。
---

# UI 数据驱动

> **codegen 已落地**（`codegen/run_spec.py`、`codegen/ui_lib/runner.py`）：`flows[].parametrize`、`{var}` 占位、`capture` 写回上下文、`__ENV__:VAR` 读环境变量。示例见 `templates/ui_login_parametrize.md`、`templates/from_ui_cases_demo.md`。

同一页面流程测多组输入/期望时，**steps 写一份，parametrize 里 N 行展开 N 条 `@pytest.mark.parametrize` 用例**。

---

## 做 / 不做

| 做 | 不做 |
|----|------|
| flow 级 `parametrize`（内联 vars + 可选 per-row expect） | 外部 CSV/JSON `data_source`（API batch 专有，UI 暂未接入） |
| steps / expect 里 `{var}` 引用 vars | 跨 flow 全局变量池（UI 用 `capture` + 同 flow 内 ctx） |
| 敏感字段用 `__ENV__:TEST_PASSWORD` | 把每条负例拆成独立 py 文件 |

---

## 何时用 parametrize

| 场景 | 推荐 |
|------|------|
| 登录：正常 / 错密码 / 空用户名 | **一条 flow + parametrize** |
| 列表筛选：多组字段值 + 不同期望文案 | **parametrize**（见 `转化/references/conversion_patterns.md` §1） |
| 步骤结构不同（如 A 页创建、B 页编辑） | **拆成多个 flow** |
| 仅改账号密码、步骤完全相同 | **parametrize vars** 或 `__ENV__` |

---

## spec 结构

```yaml
kind: ui_pytest_playwright
base_url: http://your-server:5001
storage_state: output/.auth/ui_storage.json
flows:
  - name: 登录参数化
    parametrize:
      - id: 正常登录
        vars:
          username: admin
          password: "admin123"
        expect:
          - type: url_regex
            pattern: "/login"
      - id: 密码错误
        vars:
          username: admin
          password: wrong_password
        expect:
          - type: visible_text
            text: "密码"
            exact: false
    steps:
      - action: goto
        path: /login
      - action: fill
        l1_label: "用户名"
        value: "{username}"
      - action: fill
        l1_label: "密码"
        value: "{password}"
      - action: click
        l1_role: button
        l1_name: "登录"
```

### 字段说明

| 字段 | 说明 |
|------|------|
| `parametrize[].id` | pytest 用例 id（报告里可读） |
| `parametrize[].vars` | 本行数据，注入 `UIContext` / `_ctx` |
| `parametrize[].expect` | **可选**；有则覆盖 flow 级 `expect`，无则继承 flow 默认 |
| `steps[].value/path/l1_*` | 含 `{var}` 时自动走变量替换 |
| `expect[].text/pattern` | 同样支持 `{var}` |

---

## 变量来源

| 来源 | 语法 | 示例 |
|------|------|------|
| parametrize | `{username}` | 见上表 |
| 环境变量 | `__ENV__:TEST_USERNAME` | 密码不进 spec 明文 |
| capture（步骤内） | 写入 ctx，后续步骤引用 | 见下节 |

```yaml
# 敏感账号 — 与 seckill_api_auth 等模板一致
- action: fill
  l2_css: 'input[name="username"]'
  value: "__ENV__:TEST_USERNAME"
```

---

## 步骤内 capture（链式 UI）

同一条 flow 里，前步提取、后步引用（对齐 API 的 `extract_vars`，作用域限于当前 flow）：

```yaml
steps:
  - action: click
    l1_role: button
    l1_name: "创建"
  - action: capture
    capture:
      dialog_title: { from: locator_text, l1_role: heading, l1_name: "新建" }
  - action: fill
    l1_label: "{dialog_title}"
    value: "demo"
```

capture 支持：`url`、`title`、元素 `text` / `input_value` / `attribute`、URL `regex` 分组。

---

## 生成与执行

```bash
python3 codegen/run_spec.py templates/ui_login_parametrize.md -o output/test_ui_login_ddt.py
powershell -File run_pytest_ui.ps1 output/test_ui_login_ddt.py -v
```

生成物特征：测试函数 docstring 含「（数据驱动）」，`@pytest.mark.parametrize("case", ...)`。

从用例 JSON 合并时，`testcase_to_ui_spec.py` 会保留 flow 上的 `parametrize` 字段。

---

## 与 API 数据驱动对照

| 维度 | API | UI |
|------|-----|-----|
| 多组数据 | `data_source` CSV/JSON 或 cases 重复 | flow 内联 `parametrize[]` |
| 变量引用 | `${var}`、`{{var}}` | `{var}`、`__ENV__:VAR` |
| 链式传参 | `extract_vars` + 变量池 | `capture` + 同 flow `UIContext` |
| 模板 | `templates/api_login_ddt.md` | `templates/ui_login_parametrize.md` |

---

## Agent 规则

用户描述「登录测三种情况」「同一表单多组边界值」时：

1. **先**合并为一条 flow + `parametrize`（不要复制三份 steps）
2. 每组写清 `id`、`vars`、差异化 `expect`
3. 产出 spec 后走 `./generate.sh` 或 `run_spec.py`，勿手写重复 pytest
4. 负例文案断言用 `visible_text` / `alert_visible`（弹窗见 `conversion_patterns.md` §5）
