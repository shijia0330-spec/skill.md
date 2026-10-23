# OpenAPI 标准流水线（默认路径）

**Swagger/OpenAPI 导入 ≠ 完整接口测试。** 本包默认走「契约 → 用例表 → 评审 → spec → pytest」。

---

## 两条模式

| 模式 | 何时用 | 命令 |
|------|--------|------|
| **标准（默认）** | 秒杀财务进销存 P0 准出、权限/负例 | 本文件 Step 1～6 |
| **冒烟** | Day-1 连通性、collect-only | `references/openapi_smoke_mode.md` |

intent-router：用户说「Swagger/OpenAPI/接口自动化」→ **本流水线**；说「冒烟导入/直出 pytest」→ 冒烟模式。

---

## Step 1：OpenAPI → cases 草稿

```bash
python3 codegen/openapi_to_cases.py \
  -i path/to/openapi.yaml \
  -o output/seckill_cases_draft.json \
  --base-url http://127.0.0.1:5001 \
  --auth-profile templates/auth_profiles/generic_rest.yaml
```

产出：带 `layer`（H/E/X）、`priority`、`automation` 的 JSON，含：
- H 主路径 + `expect_json_subset` 弱断言（来自 response schema）
- **E 契约边界**（schema 含 `minLength`/`maxLength`/`minimum`/`maximum`/`enum` 时自动展开 trio）
- X 负例骨架（401/403/422/400，仅当 OpenAPI responses 声明了对应码）

**跳过 X/E 扩展（仅 H 主路径）**：

```bash
python3 codegen/openapi_to_cases.py -i path/to/openapi.yaml -o output/cases.json --no-negatives
# 或 --mode smoke；仅跳过 E 层：加 --no-boundaries
```

---

## E 层边界导入须知

| 现象 | 原因 | 评审时必须做 |
|------|------|--------------|
| **未生成 E** | schema 未写约束，或 responses 无 422/400（失败边界需声明校验码） | 从 PRD/功能用例补边界 |
| **假红** | 服务端比 OpenAPI 宽松（超长仍 200） | 改期望或标 `skip` |
| **漏场景** | 规则只在 PRD（如用户名重复） | Step 2 从功能用例补 X/E |

> OpenAPI **没写** `maxLength` 等约束时，E 层不会凭空生成——须用功能用例/PRD 补全（见 Step 2）。

---

## X 负例导入须知（假红 / 假绿风险）

OpenAPI 自动生成的 X 层用例是**契约模板**，不是业务准出用例：

| 现象 | 原因 | 评审时必须做 |
|------|------|--------------|
| **假红** | 示例 body 仍合法，服务端返回 200 而非 422 | 改成必失败字段（缺必填、类型错误、越界值） |
| **假绿** | 只断言 status，未校验 error body 结构 | 补 `expect_json_subset` / `json_path` |
| **漏场景** | OpenAPI 未声明 403/401 | 人工补角色/组织越权 case |
| **误触发** | 401 case 仍带有效 Token | 确认 `no_auth: true` 或去掉 Authorization |

> **原则**：导入的 X case 默认标记 `automation.review_required: true`（若有）；Step 2 评审前**不要**直接 `./generate.sh` 上 CI 准出。

**codegen 已落地（2026-07）**：

- OpenAPI 自动生成的 **X/E 层**（校验失败、边界）带 `review_required: true`
- 生成的 pytest **默认 skip** 这些用例；设 `REVIEW_REQUIRED_RUN=1` 后才执行
- OpenAPI 同时声明 **422 + 400** 时，`expect_status: [422, 400]`，避免 Flask 等实现差异假红

```bash
# 默认：只跑 H 层 + 401/403 等 P0，X/E 草稿 skip
./generate.sh templates/seckill_api.md --report

# 评审后全量跑 X/E
REVIEW_REQUIRED_RUN=1 ./run_pytest.sh output/seckill_api.py -v
```

---

## 状态码漂移（422 vs 400）决策树

OpenAPI 写 422、服务实际回 400（或反过来）时，按优先级选一条：

| 优先级 | 动作 | 何时用 |
|--------|------|--------|
| **1** | 修 OpenAPI / 修服务，对齐单一码 | 团队以契约为准、或准出前必须统一 |
| **2** | cases 里改 `expect_status` 或 `accept_status: [400, 422]` | 短期容忍双栈差异 |
| **3** | 标 `skip: true` 或保留 `review_required` | 场景待产品确认 |

**导入自动行为**：responses 同时有 422 与 400 → 生成 `expect_status: [422, 400]`。  
**仅 H 层准出**：`--smoke-only` 或依赖默认 skip（不设 `REVIEW_REQUIRED_RUN`）。

**spec 手写多码示例**：

```yaml
cases:
  - id: TC-REG-X-INVALID
    method: POST
    path: /api/auth/register
    json_body: { password: "x" }
    expect_status: [422, 400]   # 或 accept_status: [422, 400]
    review_required: true
```

---

## Step 2：分析 + 补全（AI / 人工）

对照 PRD / `秒杀财务_测试计划.md`：

- 删无关端点、补 **角色/组织越权** X 用例
- **OpenAPI 未声明的边界**（用户名重复、描述超长但无 maxLength）从功能用例 P0/P1 补进 JSON
- 修正 `login_path`、token 字段、示例数据
- 多步流程改为 `automation.kind: scenario` 或 spec 里 `scenarios[]`

---

## Step 3：评审

- P0 必须含 H + 关键 X（401/403）
- 强依赖步骤不得拆成多个独立 case（用 `scenarios[]`）

---

## Step 4：cases JSON → spec

```bash
python3 codegen/testcase_to_api_spec.py \
  -i output/seckill_cases_draft.json \
  -o templates/seckill_api.md \
  --title "秒杀财务进销存 API"
```

---

## Step 5～6：生成与执行

```bash
./generate.sh templates/seckill_api.md
cd output && TEST_BASE_URL=... TEST_USERNAME=... TEST_PASSWORD=... python3 -m pytest seckill_api.py -v
```

失败自动写 `output/bugs/` 草稿。

---

## 与 testcase-skills 的关系

- **功能测试点**（页面、业务规则长文）→ `testcase-skills`
- **接口自动化用例**（H/E/X/P/S、method/path/assert）→ 本流水线 + `api-skills/01_测试用例生成.md`

二者可并行：功能用例评审结论反哺 Step 2 补全 automation 块。细则见 **`references/boundary_and_prd_supplement.md`**。

---

## 业务模块 内置示例

契约与草稿在 **`output/`**：

```bash
python3 codegen/openapi_to_cases.py \
  -i examples/mini_openapi_boundaries.json \
  -o output/seckill_cases_draft.json \
  --base-url http://your-server:5001 \
  --auth-profile templates/auth_profiles/generic_rest.yaml
```

Step 2 对照 `examples/prd_mini_seckill_auth.md` 补 PRD 未覆盖的边界。
