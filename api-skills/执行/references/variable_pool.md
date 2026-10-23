---
name: variable-pool
description: 变量池与数据驱动 — 三层变量体系 + CSV/JSON 数据驱动，链式测试不用手工传参。
---

# 变量池与数据驱动

> **codegen 已落地**（`codegen/run_spec.py`）：`extract_vars`、`${var}`、`depends_on` 失败跳过、`data_source` CSV/JSON。示例见 `templates/api_chain_vars.md`、`templates/api_login_ddt.md`。

三层变量体系叠加后，链式API测试**基本不用手工传参**。

---

## 做 / 不做

| 做 | 不做 |
|----|------|
| 三层变量传递（全局/单次/提取） | 执行测试（走 api-skills） |
| CSV/JSON 数据驱动 | |

---

## 三层变量体系

```
GlobalVariablePool（全局，跨用例、跨 session 共享环境变量）
       ↑
VariablePool（单次链式/批量执行内）
       ↑
extract_vars（从 HTTP 响应自动提取）
```

**生活例子：公司门禁 + 工牌**

- **GlobalVariablePool** = 公司大门门禁（token 全公司通用，登录一次大家都用）
- **VariablePool** = 当天项目组临时白板（这次联调专用的 test_user_id）
- **extract_vars** = 前台发卡机（办完入职自动把工牌号写进系统）

---

## 变量传递示例

```json
// 步骤1 登录响应
{"data": {"token": "abc123", "user_id": 42}}

// extract_vars 配置
extract_vars:
  token: "$.data.token"
  user_id: "$.data.user.id"

// 变量池 → { token: "abc123", user_id: 42 }

// 步骤2 创建订单（无需手工填）
POST /api/orders
Headers: { "Authorization": "Bearer ${token}" }
Body:    { "user_id": "${user_id}", "sku": "BOOK-001" }

// 步骤2 响应 → order_id: 99 写入池

// 步骤3
GET /api/orders/${order_id}   → 自动变成 GET /api/orders/99
```

---

## 变量来源

| 来源 | 说明 | 示例 |
|------|------|------|
| 环境变量 | 系统级变量 | `${base_url}`、`${db_host}` |
| GlobalVariablePool | 跨 session 共享 | `${token}`（登录一次，所有用例用） |
| VariablePool | 单次执行内 | `${order_id}`（本次链式测试专用） |
| extract_vars | 从响应自动提取 | `${user_id}`（登录响应提取） |
| 手动定义 | 用户指定 | `${test_user}` = `customer_01` |

---

## 数据驱动

同一接口测多组数据，**模板一份，数据表格 N 行展开 N 条用例**。

### CSV 数据驱动

```csv
username,password,expected_status
admin,admin123,200
admin,,400
admin,wrong,401
,admin123,400
```

```yaml
cases:
  - id: TC-LOGIN
    method: POST
    path: /api/login
    data_source: "login_data.csv"
    json_body:
      username: "${username}"
      password: "${password}"
    expect_status: "${expected_status}"
```

### JSON 数据驱动

```json
[
  {"username": "admin", "password": "admin123", "expected_status": 200},
  {"username": "admin", "password": "", "expected_status": 400},
  {"username": "admin", "password": "wrong", "expected_status": 401}
]
```

---

## 多级路径解析

变量支持嵌套引用：

```yaml
# 一级变量
token: "${login_response.data.token}"

# 二级变量（引用一级）
order_id: "${create_order_response.data.id}"

# 三级变量（组合）
query_url: "/api/orders/${order_id}?token=${token}"
```

---

## 变量池配置

```json
{
  "variable_pool": {
    "global": {
      "base_url": "http://your-server:5000",
      "token": ""
    },
    "session": {
      "user_id": "",
      "order_id": ""
    },
    "extract_rules": {
      "token": "$.data.token",
      "user_id": "$.data.user.id",
      "order_id": "$.data.id"
    }
  }
}
```
