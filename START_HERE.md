# 快速上手（秒杀财务系统示例）

本包演示业务系统：**电商秒杀与财务一体化系统**（`seckill_finance_system`，进销存演示项目）。

> **说明**：`seckill_finance_system` 需与 skills 包分开存放，**不在 zip 内**；**联系交付方获取**。无后端时仍可走「路径 A」生成用例，或走「路径 B」的 `pytest --collect-only` 验收生成链路。

## 环境地址

| 部署方式 | API 地址 |
|----------|----------|
| 本地 `python3 backend/run.py` | `http://your-server:5000` |
| Docker Compose（默认） | `http://your-server:5001` |

```bash
export TEST_BASE_URL=http://your-server:5001   # 按实际改
export TEST_USERNAME=admin
export TEST_PASSWORD=admin123
curl -X POST "$TEST_BASE_URL/api/test/init" -H "Content-Type: application/json" -d '{}'
```

---

## 路径 A：从 PRD 生成测试用例（AI 编辑器，无需后端）

```text
@testcase-skills/生成/SKILL.md
@examples/prd_mini_seckill_auth.md

按专业版规则生成测试用例，输出到 output/seckill_auth_testcases.md
```

对照黄金样例：`examples/output_seckill_auth_testcases.md`

**可选前置**：`@requirement-modeling/SKILL.md` → `@testcase-skills/评审/SKILL.md`

---

## 路径 A′：从 PRD + 技术文档生成测试方案与计划

1. `@testplan-skills/分析/SKILL.md` → 分析 YAML  
2. `@testplan-skills/方案/SKILL.md` → `output/项目_testscheme.md`  
3. `@testplan-skills/计划/SKILL.md` → `output/项目_testplan.md`  
4. `@testplan-skills/评审/SKILL.md` 评审  
5. 通过后走路径 A 生成用例  

（快速单页版：`@test-plan/SKILL.md`）

---

## 路径 B：不依赖 AI，跑 API 冒烟

```bash
# 本包根目录 skills-专业版V3.0
chmod +x generate.sh run_pytest.sh verify_all.sh
./generate.sh templates/api_smoke.md
cd output && python3 -m pytest api_smoke.py --collect-only -q   # 无后端：应看到 N tests collected（以终端为准）

# 有 seckill_finance_system 时再跑全量
export TEST_BASE_URL=http://your-server:5001
export TEST_USERNAME=admin
export TEST_PASSWORD=admin123
cd .. && ./run_pytest.sh output/api_smoke.py -v
```

秒杀专用模板：`templates/seckill_api_smoke.md`、`templates/seckill_api_auth.md`

---

## 路径 C：记缺陷 / 同步 / 看进度

| 目标 | 引用 |
|------|------|
| 写缺陷单 | `@bug-reporter/SKILL.md` |
| pytest 失败自动草稿 | `./run_pytest.sh output/api_smoke.py -v` → `output/bugs/` |
| 推送到禅道/云效 | `@defect-sync/SKILL.md` |
| 进度汇总、通过率、会话统计 | `@progress-reporter/SKILL.md`（pytest 结束自动写 `output/reports/progress.md`） |

---

## 路径 D：专项能力

| 目标 | 引用 | 说明 |
|------|------|------|
| **压测（默认）** | `@load-testing/执行/SKILL.md` | k6 / JMeter / Locust · HAR 一键 |
| 压测报告 | `@load-testing/报告/SKILL.md` | |
| HAR → 压测 | `run_perf_from_har.sh` 或 `run_perf_from_har.ps1` | spec → k6/JMeter → Token → 执行 |
| Locust 快速冒烟 | `@special-testing/SKILL.md` | `./generate.sh templates/perf_test.md`（**可执行**）；安全/UI审查见 Skill「规划中」章节 |
| 视觉回归 | `templates/visual_regression.md` | `./generate.sh` → pytest 截图对比（**可执行**，专项模板） |
| **声明式造数** | `@data-factory/执行/SKILL.md` | `kind: data_factory` |
| **用例驱动造数** | `@testcase-data-generator/SKILL.md` | 评审后 AI 写 SQL/shell/Python |
| OpenAPI 标准流水线 | `@api-skills/执行/references/openapi_pipeline.md` | cases → spec → pytest |
| 功能用例转 UI | `@testcase-skills/UI精简` → `@UI-skills/转化` | 大批量 Markdown 用例筛选 |
| 深度需求分析 | `@requirement-modeling/SKILL.md` | |
| Web UI 自动化 | `@UI-skills/执行/SKILL.md` | |
| 全站截图 | `@screenshot-skills/全站截图/SKILL.md` | |
| 正式测试方案+计划 | `@testplan-skills/方案/SKILL.md` | 四段流水线 |
| 快速测试方案 | `@test-plan/SKILL.md` | 单页出稿 |
| CI 门禁 | `@ci-gate/SKILL.md` | |
| RAG 知识检索 | `@rag-engine/SKILL.md` | |

不确定走哪条线：`@intent-router/SKILL.md`。

---

## 一键验收

```bash
./verify_all.sh              # 无后端：codegen + RAG + CI + collect-only
./verify_all.sh --with-api   # 有后端：再跑 api_smoke + seckill_api_auth
```

---

## 三条推荐流水线

```
粗需求 → @requirement-modeling → @testcase-skills/分析 → @testcase-skills/生成 → @testcase-skills/评审

PRD+技术文档 → @testplan-skills/* → @testcase-skills/生成

OpenAPI → openapi_to_cases → 评审 → spec → ./generate.sh → ./run_pytest.sh

功能用例 → @testcase-skills/UI精简 → @UI-skills/转化 → spec → pytest

造数+压测 → data_factory.md → users.csv(username,password) → jmeter_test.md / perf_test_k6_multiuser.md

App 移动端 → appium_e2e.md / appium_seckill_h5.md → ./generate.sh --env appium → ./run_appium.sh

HAR → 压测 → run_perf_from_har.ps1 -Har capture.har -Engine k6 -Smoke
```

更多话术见 **`prompts/常用话术.md`** · 分章手册见包外 **`skills3.0使用手册/`** · 目录与能力状态见 **`STRUCTURE.md`**（以本包 `START_HERE.md` 为准）。
