---
name: api-execution
description: API 测试统一入口：OpenAPI/自然语言/用例表 → 分层用例 → spec → pytest → 执行报告；失败走自愈或缺陷登记。Use when user provides Swagger, REST contract, or NL API test request.
---

# API 测试执行（统一入口）

**版本**：2026-07 · **规则** 1.1  

与 `testcase-skills/生成` 同级：**输入可以粗（一句话 / 一份契约），产出要细（用例表 → 可跑脚本 → 报告）**。本 Skill 只编排流程；细则在下文「子文档」里。

---

## 能力边界

| 做 | 不做 |
|----|------|
| 从 OpenAPI / 人话 / 用例表生成 **H/E/X/P/S** 分层接口用例 | 替代 `test-case-generator` 写 **功能测试点**（页面流程、业务规则长文） |
| 落成 `api_pytest` spec 并 `./generate.sh` 出 pytest | 自动创建 Jira/禅道工单（走 `bug-reporter` 出 Markdown） |
| 约定执行命令与报告字段 | 修服务端逻辑 bug（只能记缺陷或建议开发修） |

---

## 三种输入（可组合）

| 方式 | 用户给什么 | AI 第一步 |
|------|------------|--------------|
| **A. 契约（默认标准路径）** | `openapi.json` / `swagger.yaml` | **`references/openapi_pipeline.md`**：`openapi_to_cases.py` → 评审 → `testcase_to_api_spec.py` → spec |
| **A′. 契约（冒烟）** | 同上，但用户明确「直出/冒烟」 | **`references/openapi_smoke_mode.md`**：`--import-openapi --smoke-only` → spec → pytest |
| **B. 自然语言** | 「测 POST /api/auth/login…」 | 先补全 **base_url**、鉴权；产出 H/E/X `cases[]` 再 spec |
| **C. 已有用例** | 评审过的 cases JSON / 表 | 跳过分析 → `testcase_to_api_spec.py` → `./generate.sh` |

> **默认约定**：用户给 Swagger 且未说「冒烟」→ 走 **A 标准路径**，不要直接 `--import-openapi` 当准出。  
> **B 要写细**：至少产出 `cases[]`；多步用 `scenarios[]`（见 `02_测试脚本生成.md` §6）。

---

## 标准流水线（Step 0～7）— 默认

```
OpenAPI → cases 草稿 → 分析/补全 → 评审 → spec → pytest → 报告 → 失败分流
```

| Step | 动作 | 子文档 / 命令 |
|------|------|----------------|
| **0** | 澄清环境、`auth-profile`（REST API 见 `templates/auth_profiles/generic_rest.yaml`） | 问用户 |
| **1** | **OpenAPI → cases 草稿**（H + X + **E 边界**） | `python3 codegen/openapi_to_cases.py -i openapi.yaml -o output/cases_draft.json --auth-profile ...` |
| **2** | **规划/补全** | 对照 PRD/功能用例；**`references/boundary_and_prd_supplement.md`**（OpenAPI 没有的边界） |
| **3** | **评审** | P0 含 H + 关键 X（401/403）；E 层 `review_required` 须过一遍 |
| **4** | **Spec** | `python3 codegen/testcase_to_api_spec.py -i cases_draft.json -o templates/xxx.md` |
| **5** | **生成脚本** | `./generate.sh templates/xxx.md` |
| **6** | **执行** | 默认 `./generate.sh ... --report`（X/E 草稿 **skip**）；全量 `REVIEW_REQUIRED_RUN=1 pytest ...` |
| **7** | **失败** | `output/bugs/` 草稿 → 自愈 / `@bug-reporter` |

**冒烟捷径**（非准出）：见 `references/openapi_smoke_mode.md`。

---

## 快速命令

```bash
# 标准：OpenAPI → cases 草稿（含 E 层 schema 边界）
python3 codegen/openapi_to_cases.py -i openapi.yaml -o output/cases_draft.json \
  --base-url http://your-server:5001 --auth-profile templates/auth_profiles/generic_rest.yaml

# 不要 E 层：加 --no-boundaries；冒烟仅 H：--mode smoke
```

# 评审后 → spec → pytest（X/E 默认 skip，见 openapi_pipeline.md §状态码漂移）
python3 codegen/testcase_to_api_spec.py -i output/cases_draft.json -o templates/imported_api.md
./generate.sh templates/imported_api.md --report
REVIEW_REQUIRED_RUN=1 ./run_pytest.sh output/imported_api.py -v   # 评审后跑 X/E

# 冒烟（仅 H 主路径，import_mode: smoke）
./generate.sh --import-openapi openapi.yaml --smoke-only \
  --auth-profile templates/auth_profiles/generic_rest.yaml -o output/imported_smoke.md
./generate.sh output/imported_smoke.md
```

---

## 自然语言示例（AI 应答结构）

用户：「帮我测 REST API 商品列表 GET /api/products，并测 POST /api/products 创建商品返回 201。」

AI 应产出（节选）：

1. **用例表**（Markdown 或 JSON `cases[]`）  
   - `API-001` H：GET `/api/products` → 200，含 name/status 字段  
   - `API-002` H：POST `/api/products`（admin）→ 201，返回 product id  
2. **spec 片段**（YAML frontmatter + `cases`）  
3. **生成与执行命令**（见上）  
4. 若失败：**附请求/响应摘录** 再 `@bug-reporter`

---

## 子文档索引

| 文件 | 用途 |
|------|------|
| `01_测试用例生成.md` | 用例分层与字段 |
| `02_测试脚本生成.md` | pytest、cases vs scenarios |
| `03_API_Generator_SKILL.md` | 多栈仓库先认栈 |
| `04_执行与报告约定.md` | 报告、CI、红灯分流 |
| `../分析/*` | 契约与人话解析 |
| `../规划/SKILL.md` | 测试计划与样本 |
| `../自我修复/SKILL.md` | 脚本自愈 |
| `references/openapi_pipeline.md` | **默认** OpenAPI → cases → spec 流水线 |
| `references/boundary_and_prd_supplement.md` | **E 层自动规则 + PRD 补全 + 秒杀财务 REST 示例** |
| `references/openapi_smoke_mode.md` | Swagger 直出冒烟（import_mode: smoke） |
| `references/status_code_assertions.md` | REST API HTTP 状态码速查 |
| `references/ci_gate.md` | CI 门禁与准出 |
| `references/coverage_analysis.md` | 接口覆盖率分析 |
| `references/variable_pool.md` | 变量池字段详解 |
| `references/interactive_report.md` | 交互式 HTML 报告 |

上级导航：`../索引.md`

演示 spec：`examples/spec_seckill_api_smoke.filled.md` · 模板：`templates/api_smoke.md`  
OpenAPI 边界样例：`examples/mini_openapi_boundaries.json` · 补全指南：`references/boundary_and_prd_supplement.md`

---

## 变量池与链式执行（codegen 已落地）

> 实现见 `codegen/run_spec.py` 与 `02_测试脚本生成.md` §7。

### 变量提取与引用

上游 `extract_vars`（或 scenarios 内 `capture`）从响应写入变量池；下游 URL/Header/Body 用 **`${变量名}`** 引用：

```json
{
  "id": "TC-001",
  "method": "POST",
  "path": "/api/login",
  "extract_vars": { "token": "$.data.token" }
}
```

| 来源 | 说明 | 示例 |
|------|------|------|
| 环境变量 | 系统级 | `${base_url}`、`${db_host}` |
| extract_vars | 上游提取 | `${token}`、`${order_id}` |
| 手动定义 | 用户指定 | `${test_user}` |

### 链式执行与失败跳过

```
① POST /login   → 200, 提取 token
② POST /orders  → 201, 依赖 token；提取 order_id
③ GET /orders/${order_id} → 200
```

某步失败时 **`depends_on` 下游自动 skip**，避免一串无意义红色：

```
① POST /login → 401 ❌
② POST /orders → ⏭️ SKIP（依赖①的 token）
```

### 断言类型

| 类型 | 示例 |
|------|------|
| 状态码 | `expect_status: 200` |
| JSON 字段 | `$.data.status == "paid"` |
| 响应时间 | `response_time < 500ms` |
| Header | `Content-Type == application/json` |

状态码速查：`references/status_code_assertions.md`。

---

## AI 编辑器快捷引用

```text
@api-exec/SKILL.md
@openapi.yaml
按 Step 0～7 执行，先输出用例表再生成 spec 和 pytest 命令
```
