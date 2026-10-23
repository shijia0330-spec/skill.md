# skills 专业版 V3.0 — 目录结构

本包为**对外交付主产品**（V3.0）：Markdown spec → 生成 pytest → 执行；配套 Skill 文档供 AI 编辑器使用。配套演示后端 `seckill_finance_system`（进销存）**不在 zip 内**，**联系交付方获取**。

## 根目录

| 路径 | 说明 |
|------|------|
| `README.md` / `START_HERE.md` | 总览与快速上手 |
| `STRUCTURE.md` | 目录结构与能力状态 |
| `verify_all.sh` | 一键验收脚本 |
| `generate.sh` / `generate.ps1` / `run_pytest.sh` / `run_pytest_ui.sh` / `run_pytest_ui.ps1` | 生成与 pytest 入口 |
| `run_perf_from_har.sh` / `run_perf_from_har.ps1` | HAR 压测一键流水线 |
| `conftest.py` | pytest 钩子（进度、根因、缺陷草稿、UI 截图、RAG 回灌） |
| `nl_ui_client.py` | 自然语言一句话 UI 执行 |
| `scripts/` | AllureReport.ps1、allure_serve.py、install_allure.ps1 |
| `.env.example` | 环境变量示例 |
| `prompts/` | 常用 AI 话术 |
| `examples/` | PRD / OpenAPI / 用例 / spec 黄金样例 |
| `templates/` | 声明式 spec 模板 + `auth_profiles/` |
| `codegen/` | Markdown → pytest 生成引擎（**API/UI 委托 `api_lib` / `ui_lib`**） |
| `output/` | 统一产出（脚本、报告、缺陷、压测结果） |

## Skill 目录（V3.0）

| 目录 | 用途 | 状态 |
|------|------|------|
| `api-skills/` | API 分析、规划、执行、自愈；**OpenAPI 标准流水线** | 可执行 + AI 辅助 |
| `UI-skills/` | Playwright UI、定位自愈、**转化**、NL 一句话 | 可执行；L2.5/L3 **规划中** |
| `mobile-skills/` | Appium 移动端 | 需联调 |
| `testcase-skills/` | 用例规划、分析、生成、评审、**UI精简** | AI 辅助；step6 **可执行** |
| `testplan-skills/` | 测试方案与计划（**分析→方案→计划→评审**） | AI 辅助 |
| `test-plan/` | 测试方案与计划（单 SKILL，快速出稿） | AI 辅助 |
| `data-factory/` | **声明式造数**（MySQL/CSV）+ pytest setup 铺底 | 可执行；环境重置 **规划中** |
| `testcase-data-generator/` | **用例驱动**数据设计（评审后 SQL/shell/Python） | AI 辅助 |
| `load-testing/` | k6 / JMeter / Locust codegen + 报告四阶段 | 可执行；报告 **AI 辅助** |
| `special-testing/` | Locust 冒烟；`visual_regression.md` 专项模板 | 压测/视觉回归 **可执行**；安全/UI审查 **规划中** |
| `requirement-modeling/` | 需求建模 | AI 辅助 |
| `rag-engine/` | RAG 知识库 | 可执行 |
| `ci-gate/` | CI 门禁 | 可执行 |
| `defect-sync/` | 缺陷同步禅道/云效/自研 | 可执行（dry-run）；推送 **需联调** |
| `bug-reporter/` | 缺陷报告约定 + **指纹去重** | 可执行 |
| `defect-analysis/` | 失败根因分析 | 可执行 |
| `intent-router/` | 意图路由（`mapping.yaml` revision 12+） | 可执行 |
| `progress-reporter/` | pytest 进度汇总 → `output/reports/` | 可执行 |
| `screenshot-skills/` | 全站截图 | 需联调 |

## 四块集成（接口 / UI / 造数 / 压测）

```
codegen/run_spec.py  ←── templates/*.md
        ↓
   output/*.py | data_factory.py | users.csv | *.jmx | *.js
        ↓
run_pytest.sh / run_pytest_ui.ps1 / k6 / JMeter
        ↓
conftest → output/reports/ + output/bugs/ + output/ui_artifacts/
```

| 衔接点 | 说明 |
|--------|------|
| OpenAPI 标准路径 | `openapi_to_cases.py` → 评审 → `testcase_to_api_spec.py` → spec |
| OpenAPI 冒烟 | `./generate.sh --import-openapi ... --smoke-only` |
| 造数 → JMeter | `data_factory.md` → `output/users.csv` → `jmeter_test.md` |
| data_source 路径 | 统一写 **`output/users.csv`**（相对包根，由 data_factory 导出） |
| 用例 → UI 自动化 | `UI精简` → `UI-skills/转化` → `md_cases_to_ui_spec.py` |
| 用例 → App 自动化 | `UI精简` → `mobile-skills/转化` → `md_cases_to_appium_spec.py` |
| 意图路由 | `intent-router/mapping.yaml` |

## 典型工作流

```
templates/*.md 或 OpenAPI → cases → spec
        ↓
   ./generate.sh spec.md
        ↓
   output/*.py
        ↓
   ./run_pytest.sh output/xxx.py -v
```

pytest 结束后自动产出：`output/reports/progress.md`、`failure_analysis.json`、`output/bugs/BUG-*.md`。

## 演示后端与环境

> **获取方式**：`seckill_finance_system`（进销存/秒杀财务示例）不在技能包 zip 内，**联系交付方获取**。

| 场景 | base_url |
|------|----------|
| 本地 `python3 run.py` | `http://your-server:5000` |
| Docker Compose（默认映射） | `http://your-server:5001` |

```bash
export TEST_BASE_URL=http://your-server:5001
export TEST_USERNAME=admin
export TEST_PASSWORD=admin123
curl -X POST "$TEST_BASE_URL/api/test/init" -H "Content-Type: application/json" -d '{}'
```

## 可选依赖

| 能力 | 依赖 |
|------|------|
| API 测试 | `pytest`, `requests`, `PyYAML` |
| UI 测试 | `pytest-playwright`, 浏览器 |
| 性能 | `locust` / k6 / JMeter |
| App | Appium + `Appium-Python-Client` |
