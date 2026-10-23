# 自动化用例 · 可执行细粒度

> 每条将转入自动化的检查点，须满足 **单步可映射** 到 spec case 或 UI 步骤。

## 功能用例（API）

每条 `####` 检查点建议含：

| 要素 | 说明 |
|------|------|
| 前置 | 账号、铺底、Token（可写环境变量名） |
| 步骤 | 方法 + 路径 + 关键 body 字段 |
| 预期 | HTTP 状态 + 关键 JSON 字段（可 PASS/FAIL） |

**禁止**：「系统应正常工作」等不可断言描述。

## UI 精简用例

须使用 `step_vocabulary.md` 白名单句式；一句一动作。

## 对接

| 类型 | 下游 |
|------|------|
| API | `api-skills/执行` · `codegen/run_spec.py` |
| UI | `UI-skills/转化` · `md_cases_to_ui_spec.py` |

示例：`examples/output_seckill_auth_testcases.md`
