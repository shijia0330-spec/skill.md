---
kind: api_pytest
# 对齐 seckill_finance_system openapi.yaml；运行前 POST /api/test/init
base_url: http://your-server:5000
auth:
  type: bearer_login
  login_path: /api/auth/login
  username_field: username
  password_field: password
  username_env: TEST_USERNAME
  password_env: TEST_PASSWORD
cases:
  # ===== 1. 商品查询 =====
  - id: TC-Q-001
    name: 商品列表查询（无需登录）
    method: GET
    path: /api/products
    no_auth: true
    expect_status: 200

  - id: TC-Q-002
    name: 商品列表按状态筛选
    method: GET
    path: /api/products
    no_auth: true
    params:
      status: active
    expect_status: 200

  - id: TC-Q-003
    name: 商品详情查询（需登录）
    method: GET
    path: /api/products/1
    expect_status: 200

  - id: TC-Q-004
    name: 商品详情查询（不存在）
    method: GET
    path: /api/products/99999
    expect_status: 404

  # ===== 2. 秒杀活动查询 =====
  - id: TC-Q-005
    name: 秒杀活动列表查询（无需登录）
    method: GET
    path: /api/seckill/activities
    no_auth: true
    expect_status: 200

  - id: TC-Q-006
    name: 秒杀活动详情查询
    method: GET
    path: /api/seckill/activities/1
    no_auth: true
    expect_status: 200

  # ===== 3. 订单查询 =====
  - id: TC-Q-007
    name: 订单列表查询（需登录）
    method: GET
    path: /api/orders
    expect_status: 200

  - id: TC-Q-008
    name: 订单列表按状态筛选
    method: GET
    path: /api/orders
    params:
      status: pending
    expect_status: 200

  - id: TC-Q-009
    name: 订单列表按类型筛选
    method: GET
    path: /api/orders
    params:
      type: seckill
    expect_status: 200

  - id: TC-Q-010
    name: 订单详情查询
    method: GET
    path: /api/orders/1
    expect_status: 200

  # ===== 4. 采购管理查询 =====
  - id: TC-Q-011
    name: 采购订单列表查询（管理员）
    method: GET
    path: /api/purchase/orders
    expect_status: 200

  - id: TC-Q-012
    name: 入库单列表查询（管理员）
    method: GET
    path: /api/purchase/stock-ins
    expect_status: 200

  - id: TC-Q-013
    name: 供应商列表查询（管理员）
    method: GET
    path: /api/suppliers
    expect_status: 200

  # ===== 5. 销售管理查询 =====
  - id: TC-Q-014
    name: 销售订单列表查询（管理员）
    method: GET
    path: /api/sales/orders
    expect_status: 200

  - id: TC-Q-015
    name: 出库单列表查询（管理员）
    method: GET
    path: /api/sales/stock-outs
    expect_status: 200

  - id: TC-Q-016
    name: 客户列表查询（管理员）
    method: GET
    path: /api/sales/customers
    expect_status: 200

  # ===== 6. 库存管理查询 =====
  - id: TC-Q-017
    name: 库存流水查询（管理员）
    method: GET
    path: /api/inventory/transactions
    expect_status: 200

  - id: TC-Q-018
    name: 库存流水按商品筛选
    method: GET
    path: /api/inventory/transactions
    params:
      product_id: 1
    expect_status: 200

  - id: TC-Q-019
    name: 商品库存汇总查询（管理员）
    method: GET
    path: /api/products/1/inventory
    expect_status: 200

  # ===== 7. 财务管理查询 =====
  - id: TC-Q-020
    name: 财务凭证列表查询（管理员）
    method: GET
    path: /api/finance/vouchers
    expect_status: 200

  - id: TC-Q-021
    name: 财务凭证按业务类型筛选
    method: GET
    path: /api/finance/vouchers
    params:
      business_type: purchase_in
    expect_status: 200

  - id: TC-Q-022
    name: 财务凭证按日期范围筛选
    method: GET
    path: /api/finance/vouchers
    params:
      start_date: "2024-01-01"
      end_date: "2026-12-31"
    expect_status: 200

  - id: TC-Q-023
    name: 凭证详情查询
    method: GET
    path: /api/finance/vouchers/1
    expect_status: 200

  - id: TC-Q-024
    name: 科目余额查询
    method: GET
    path: /api/finance/accounts/1405/balance
    expect_status: 200

  # ===== 8. 报表查询 =====
  - id: TC-Q-025
    name: 利润表查询（管理员）
    method: GET
    path: /api/finance/profit-statement
    expect_status: 200

  - id: TC-Q-026
    name: 资产负债表查询（管理员）
    method: GET
    path: /api/finance/balance-sheet
    expect_status: 200

  # ===== 9. 科目余额表 =====
  - id: TC-Q-027
    name: 科目余额表查询（管理员）
    method: GET
    path: /api/finance/subject-balance
    expect_status: 200

  # ===== 10. 通用规则 =====
  - id: TC-Q-028
    name: 分页参数（后端忽略，仍返回 200）
    method: GET
    path: /api/products
    no_auth: true
    params:
      page: 1
      per_page: 5
    expect_status: 200

  - id: TC-Q-029
    name: 无效分页参数（后端忽略）
    method: GET
    path: /api/products
    no_auth: true
    params:
      page: -1
    expect_status: 200

  - id: TC-Q-030
    name: 未登录访问需登录接口
    method: GET
    path: /api/orders
    no_auth: true
    expect_status: 401

  - id: TC-Q-031
    name: 未登录访问管理员接口
    method: GET
    path: /api/purchase/orders
    no_auth: true
    expect_status: 401

  - id: TC-Q-032
    name: 无效日期格式（后端未校验，返回 500）
    method: GET
    path: /api/finance/vouchers
    params:
      start_date: invalid-date
    expect_status: 500

  - id: TC-Q-033
    name: 日期范围倒置（返回空列表或 200）
    method: GET
    path: /api/finance/vouchers
    params:
      start_date: "2026-12-31"
      end_date: "2024-01-01"
    expect_status: 200
---

# 查询功能测试用例

对齐 `seckill_finance_system` 的 **openapi.yaml** 与 Flask 路由。

## 前置

```bash
export TEST_BASE_URL=http://your-server:5001   # Docker 默认
export TEST_USERNAME=admin
export TEST_PASSWORD=admin123
curl -X POST "$TEST_BASE_URL/api/test/init" -H "Content-Type: application/json" -d '{}'
./generate.sh templates/seckill_query_tests.md
./run_pytest.sh output/seckill_query_tests.py -v
```

## 认证说明

- 模板级 `auth.bearer_login`：默认用 **admin** Token（`TEST_USERNAME` / `TEST_PASSWORD`）
- `no_auth: true`：匿名请求，用于公开接口或 401 负向用例
-  per-case 的 `auth: user/admin` **不支持**，勿用

## 与旧版差异（V2→V3 对齐）

| 旧路径 | 新路径 |
|--------|--------|
| `/api/purchase/suppliers` | `/api/suppliers` |
| `/api/stock/transactions` | `/api/inventory/transactions` |
| `/api/stock/summary/{id}` | `/api/products/{id}/inventory` |
| `/api/finance/reports/income` | `/api/finance/profit-statement` |
| `/api/finance/reports/balance-sheet` | `/api/finance/balance-sheet` |
| `/api/dashboard` | `/api/finance/subject-balance` |
| `{id}` 占位符 | 具体 ID（如 `/1`），配合 `test/init` |
