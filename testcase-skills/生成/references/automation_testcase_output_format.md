# 自动化用例 · 交付格式

> 面向 **API/UI 自动化流水线** 的功能用例 Markdown 结构（与 `delivery_standard.md` 一致，强调可转化字段）。

## 标准结构

```markdown
# 秒杀财务系统 · {模块} 测试用例

## 文档信息
- RAG 检索：…
- 测试范围：…

## 知识库检索摘要

## 需求追溯表

## 核心流程测试

## 详细功能点测试

## 用例评审表
| 编号 | 名称 | 优先级 | 类型 | 标签 |
（Web 类「名称」须含 `秒杀财务 > 页面 > 功能`，§4.2.1）

## 通用覆盖矩阵自检

## 待澄清清单
```

## 评审表标签（自动化）

| 标签 | 含义 |
|------|------|
| `api_auto` | 可进 cases JSON / api_pytest spec |
| `ui_auto` | 须 UI精简后转化 |
| `manual` | 仅人工 |

## 金样

- API 功能用例：`examples/output_seckill_auth_testcases.md`
- PRD：`examples/prd_mini_seckill_auth.md`
- UI 精简：`testcase-skills/UI精简/SKILL.md` → `output/seckill_ui_cases.md`

## 下游转化

```
*_testcases.md →（UI精简）→ *_ui_cases.md → md_cases_to_ui_spec → pytest
              → openapi_to_cases / 手工 JSON → generate.sh → pytest
```
