---
kind: api_pytest
# 目标系统: seckill_finance_system（Docker 默认 http://your-server:5001，见 docker-compose.yml 5001:5000）
base_url: http://your-server:5001
setup: test_init
# teardown: refs_cleanup  # 测试后精确清理（配合 data_factory 使用）
auth:
  type: bearer_login
  login_path: /api/auth/login
  username_field: username
  password_field: password
  username_env: TEST_USERNAME
  password_env: TEST_PASSWORD
cases:
  - id: TC-SECKILL-PROD-LIST-001
    method: GET
    path: /api/products
    no_auth: true
    expect_status: 200
    expect_json_schema:
      type: array
      items:
        type: object
        properties:
          id:
            type: integer
          name:
            type: string
          price:
            type: number
        required: [id, name, price]
    expect_max_response_ms: 3000
  - id: TC-SECKILL-PROD-CREATE-001
    method: POST
    path: /api/products
    json_body:
      name: "技能冒烟-自动创建商品"
      description: "templates/api_smoke.md 声明式生成"
      price: 9.99
      stock: 10
    expect_status: 201
    expect_json_schema:
      type: object
      properties:
        id:
          type: integer
        name:
          type: string
      required: [id, name]
  # 数据驱动用例：从 data_factory 导出的 CSV 读取多组用户数据
  - id: TC-SECKILL-USER-LIST-001
    method: GET
    path: /api/users
    no_auth: true
    expect_status: 200
    data_source: output/users.csv  # data_factory csv_export 输出的 CSV
---

# API 冒烟（秒杀财务系统 · 商品）

本 spec 覆盖 **seckill_finance_system** 里与「商品」相关的两条接口（与 `app.py` 路由一致）：

| 用例 ID | 方法 | 路径 | 业务说明 | 鉴权 |
|---------|------|------|----------|------|
| TC-SECKILL-PROD-LIST-001 | GET | `/api/products` | 商品列表（查询在售 `active` 商品） | 无需登录（`no_auth: true`） |
| TC-SECKILL-PROD-CREATE-001 | POST | `/api/products` | 新增商品（`name`、`price` 必填；`stock` 等可选） | **管理员** JWT（`@admin_required`），走 `auth` 里登录后带 `Authorization: Bearer ***` |

## 运行

```bash
export TEST_USERNAME=admin
export TEST_PASSWORD=***
pytest output/api_smoke.py -v --alluredir=allure-results
allure serve allure-results
```

## 断言能力

### 基础断言

- `expect_status` — HTTP 状态码
- `expect_body_substrings` — 响应体包含指定文本（数组，支持多条）
- `expect_json_subset` — 响应 JSON 包含指定键值对

### JSON Schema 校验

```yaml
expect_json_schema:
  type: object
  properties:
    id:
      type: integer
    name:
      type: string
  required: [id, name]
```

支持类型：`string`、`integer`、`number`、`boolean`、`array`、`object`、`null`。
支持嵌套：`properties` 内可嵌套 `properties`，`items` 可定义数组元素 schema。
支持 `enum`：`type: string, enum: ["pending", "paid", "cancelled"]`

### 响应时间断言

```yaml
expect_max_response_ms: 3000  # 超过 3 秒判定失败
```

## Allure 报告

安装 `allure-pytest` 后自动生成增强报告：

```bash
pip install allure-pytest
pytest output/api_smoke.py -v --alluredir=allure-results
allure serve allure-results
```

报告内容：
- 每条用例的 title 和 tag
- 响应体（JSON 格式附件）
- 响应时间（文本附件）
- 失败时的堆栈信息

## 数据清理

测试后清理插入的数据：

```yaml
# 方式一：refs_cleanup（推荐，精确删除）
teardown:
  mode: refs_cleanup

# 方式二：API 清理
teardown:
  mode: api_cleanup
  path: /api/test/cleanup
  method: POST

# 方式三：SQL 清理
teardown:
  mode: sql_cleanup
  statements:
    - "DELETE FROM products WHERE name LIKE '技能冒烟%'"
```

## 数据驱动测试（data_source）

case 级 `data_source` 让单条用例按 CSV/JSON 数据行 parametrize 展开。

```yaml
cases:
  - id: TC-USER-QUERY-001
    method: GET
    path: /api/users/{id}
    no_auth: true
    expect_status: 200
    data_source: output/users.csv  # 相对 spec 目录
```

**CSV 格式：**

```csv
id,username,email
1,user_001,user001@test.com
2,user_002,user002@test.com
```

**生成结果：** 每条数据行生成一条 pytest 用例，`{id}` 占位符自动替换为 CSV 对应列的值。

**与 data_factory 衔接：**

```bash
# 1. data_factory 造数 + 导出 CSV
python3 codegen/run_spec.py templates/data_factory.md -o output/data_factory.py
cd output && python3 data_factory.py
# 输出: output/users.csv

# 2. API spec 引用该 CSV
cd ..
python3 codegen/run_spec.py templates/api_smoke.md -o output/api_smoke.py

# 3. 运行（自动 parametrize 展开）
pytest output/api_smoke.py -v
```

**JSON 格式：**

```yaml
data_source: data/users.json  # [{"id": 1, "username": "user_001"}, ...]
```
