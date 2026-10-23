# 自动化用例 · 需求输入源

> 写自动化向功能用例前，须 @ 引用下列输入（秒杀财务为包内默认样例）。

| 输入 | 路径 | 用途 |
|------|------|------|
| PRD | `examples/prd_mini_seckill_auth.md` | 功能点与边界 |
| 技术设计 | `examples/tech_mini_seckill.md` | 环境、鉴权、铺底 |
| OpenAPI | `examples/mini_openapi_boundaries.json` | H 维 + codegen |
| 用例金样 | `examples/output_seckill_auth_testcases.md` | 编号/评审表风格 |
| UI 金样 | `testcase-skills/UI精简/SKILL.md` | UI-SECKILL 标准 8 条 |

## 推荐话术

```text
@testcase-skills/生成/SKILL.md
@examples/prd_mini_seckill_auth.md
@examples/mini_openapi_boundaries.json
按 automation_generation_gate 产出 output/seckill_auth_testcases.md，P0 须标 api_auto
```

## 产出路径

| 产物 | 路径 |
|------|------|
| 完整功能用例 | `output/seckill_*_testcases.md` |
| UI 精简 | `output/seckill_ui_cases.md` |
| API spec | `templates/seckill_api_*.md` |
