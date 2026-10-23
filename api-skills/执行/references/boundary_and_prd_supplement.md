# 边界用例：OpenAPI 自动生成 + PRD 补全

**版本**：2026-07  

接口边界采用 **双源策略**：契约里写了的交给 `openapi_to_cases.py`；PRD/功能用例里独有的在 Step 2 补进 `cases_draft.json`。

---

## 1. 自动生成矩阵（codegen）

| 层级 | 触发条件 | 工具行为 | 期望状态码 |
|------|----------|----------|------------|
| **H** | 每个 operation | 主路径 body/query 合法值 | 200/201 |
| **X** | responses 声明 401/403/422/400 | 未鉴权、缺必填、空 body | 对应 4xx |
| **E（body）** | POST/PUT/PATCH + schema 有 min/maxLength、minimum/maximum、enum | 限-1/限/限+1 trio | 成功码或 422/400 |
| **E（query）** | GET + query 参数 schema 有数值/长度/enum 约束 | 同上，写入 `query` | 成功码或 422/400 |

**不会自动生成**（须 Step 2 补）：

- 用户名重复、业务错误码
- schema 未写的长度/格式
- 角色/组织越权 403（OpenAPI 未声明）
- 连通性探测（URL 不可达仍 200）

命令：

```bash
python3 codegen/openapi_to_cases.py -i examples/mini_openapi_boundaries.json \
  -o output/seckill_cases_draft.json \
  --base-url http://your-server:5001 \
  --auth-profile templates/auth_profiles/generic_rest.yaml
```

---

## 2. Step 2：从功能用例补 PRD 边界

对照 `testcase-skills/生成` 产出的评审表，**只补** `boundary` / `validation` 标签且 **P0/P1** 的条目，**不要全量转 API**。

### 补全 checklist

1. 在 OpenAPI 补 `maxLength`/`minimum` 等 → **重跑 Step 1**（优先）
2. 无法写进 OpenAPI 的 → 在 `cases_draft.json` 的 `cases[]` 追加 `automation` 块
3. 每条失败边界：`expect_status` 明确、`review_required: true`
4. 与自动 E 层去重（同字段同值只留一条）
5. 需要 seed 数据的 → 先 `POST /api/test/init` 或 spec `setup: test_init`
6. **时间边界**（E-04/E-05/E-06 类）→ 见 **§2.1**，须 `setup` 造活动 + 链式变量，**禁止**单步 POST 无前置

### 2.1 时间边界 · PRD 补全（秒杀 E-04 典型）

功能用例若只写「当前时间 = start-1s」，Step 2 **必须**拆成链式 case 或 spec 多步；细则见 `testcase-skills/生成/references/time_and_state.md` §1.1。

| 用例 | admin 造数（setup） | 执行步 | expect_status |
|------|---------------------|--------|---------------|
| E-04 开始前 ~1s | 创建活动 `start=now()+2s`，`end=now()+3600s` | sleep(1) + POST 秒杀 | 400 或 422 |
| E-05 开始时刻 | 同上 + prepare-stock | sleep(2) + POST 秒杀 | 200 或 201 |
| E-06 已结束 | `start=now()-3600s`，`end=now()-2s` | sleep(2) + POST 秒杀 | 400 或 422 |

**spec 写法**：在 `cases_draft.json` 用 `vars` 传递 `activity_id`；时间边界 case 设 `review_required: true` 直至 CI 卡点稳定。

**JSON 链式示例（E-04 简化）**：

```json
{
  "name": "秒杀 · 未开始拒绝 · E-04",
  "layer": "E",
  "priority": "P1",
  "automation": {
    "id": "TC-SECKILL-E-04-upcoming-order",
    "setup": "data_factory",
    "setup_script": "output/seckill_time_boundary_upcoming.py",
    "method": "POST",
    "path": "/api/seckill/{activity_id}/{product_id}",
    "auth": "customer",
    "pre_steps": [
      {"action": "sleep", "seconds": 1},
      {"method": "GET", "path": "/api/seckill/activities/{activity_id}", "expect_json": {"status": "UPCOMING"}}
    ],
    "expect_status": 400,
    "expect_body_contains": "未开始",
    "review_required": true
  }
}
```

造数脚本职责：见 `scripts/seckill_time_boundary_lib.py` 与 `output/seckill_time_boundary_{upcoming,active,ended}.py`。一键回归：`./run_pytest.sh output/seckill_time_boundary.py -v`。

### JSON 追加格式（示例）

```json
{
  "name": "登录 · 密码错误 · POST /api/auth/login",
  "layer": "X",
  "priority": "P1",
  "automation": {
    "id": "TC-SECKILL-AUTH-X-wrong-pwd",
    "method": "POST",
    "path": "/api/auth/login",
    "no_auth": true,
    "expect_status": 401,
    "json_body": {
      "username": "admin",
      "password": "wrong-password"
    },
    "review_required": true
  }
}
```

---

## 3. 秒杀示例（包内 examples）

| 文件 | 用途 |
|------|------|
| `examples/mini_openapi_boundaries.json` | OpenAPI 练手契约 |
| `output/seckill_cases_draft.json` | Step 1 产出，含 H/E/X |
| `examples/prd_mini_seckill_auth.md` | Step 2 对照补全 |
| `templates/auth_profiles/generic_rest.yaml` | REST Bearer 鉴权 |

### 完整命令（PowerShell）

```powershell
cd <包根目录>/skills-专业版V3.0

python3 codegen/openapi_to_cases.py `
  -i examples/mini_openapi_boundaries.json `
  -o output/seckill_cases_draft.json `
  --base-url http://your-server:5001 `
  --auth-profile templates/auth_profiles/generic_rest.yaml

# Step 2：对照 examples/prd_mini_seckill_auth.md 编辑 draft JSON

python3 codegen/testcase_to_api_spec.py `
  -i output/seckill_cases_draft.json `
  -o templates/seckill_api_from_cases.md `
  --title "秒杀 API"

./generate.sh templates/seckill_api_from_cases.md

$env:TEST_BASE_URL = "http://your-server:5001"
$env:TEST_USERNAME = "admin"
$env:TEST_PASSWORD = "admin123"
./run_pytest.sh output/seckill_api_from_cases.py -v
```

---

## 4. 评审准出

| 检查项 | 标准 |
|--------|------|
| P0 接口 | 至少 H + 关键 X（401） |
| 有 schema 约束的字段 | 已有 E trio 或 PRD 补全说明 |
| `review_required: true` | 评审通过后再上 CI |
| 假红 | body/query 仍合法却期望 4xx → 改值或删 case |
| auth | draft 含 `auth` + `session_headers` |

---

## 5. 与 testcase-skills 分工

| 线 | 输入 | 产出 |
|----|------|------|
| testcase-skills | PRD / UI 截图 | 功能测试点、评审表 |
| api-skills（本文件 + openapi_pipeline） | OpenAPI + 可选 PRD 补全 | cases_draft → spec → pytest |

**不要**用 testcase-skills 替代 OpenAPI 主路径；**不要**把 400 条功能用例全转 API。
