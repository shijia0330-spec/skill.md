---
kind: api_pytest
cases:
- id: TC-PUR-001
  expect_status: 200
  path: /api/purchase/orders
  method: GET
  name: 采购订单列表（管理员）
- id: TC-PUR-002
  expect_status: 200
  path: /api/purchase/stock-ins
  method: GET
  name: 采购入库单列表（管理员）
- id: TC-PUR-003
  expect_status: 200
  path: /api/suppliers
  method: GET
  name: 供应商列表（管理员）
auth:
  type: bearer_login
  login_path: /api/auth/login
  username_field: username
  password_field: password
  username_env: TEST_USERNAME
  password_env: TEST_PASSWORD
base_url: http://your-server:5000
---
# 用例JSON合并示例（采购）

由 `codegen/testcase_to_api_spec.py` 从用例 JSON 生成。 下一步: `./generate.sh` 指向本文件。
