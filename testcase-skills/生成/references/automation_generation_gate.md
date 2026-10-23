# 自动化用例 · 生成闸门

> **适用范围**：功能用例已评审，准备产出 **API pytest / UI Playwright** 可消费的测试点。  
> **默认示例**：秒杀财务系统。  
> **入口**：`testcase-skills/生成/SKILL.md` Step 0b 完成后加载本系列。

## 交付前检查

- [ ] 用例编号与 `examples/output_seckill_auth_testcases.md` 风格一致
- [ ] P0 覆盖登录 + 注册 + Profile（或当前模块等价主路径）
- [ ] 评审表「名称」含页面路径（Web 类，见 `delivery_standard.md` §4.2.1）
- [ ] 待澄清 T-xx 已汇总
- [ ] **UI 线**：已走 `testcase-skills/UI精简`，未直接把 `*_testcases.md` 喂给 `md_cases_to_ui_spec`
- [ ] **API 线**：有 OpenAPI 时已叠加 H 维（`api_contract_supplement.md`）

## 本系列文档

| 文件 | 用途 |
|------|------|
| `automation_input_sources.md` | 需求输入源 |
| `automation_core_flows.md` | 核心流程树 |
| `automation_minimum_inventory.md` | 最低用例清单 |
| `automation_executable_granularity.md` | 可执行细粒度 |
| `automation_testcase_output_format.md` | 交付格式 |
| `automation_case_id_registry.md` | 编号注册表 |
| `automation_structure_preservation.md` | 模块结构与前缀 |
| `automation_coverage_matrix.md` | 自动化覆盖矩阵 |
| `automation_examples.md` | 写法样例 |
