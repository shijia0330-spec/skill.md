---
kind: api_pytest
# seckill_finance_system：API 写库 + 可选 DB 对账
base_url: http://your-server:5000
auth:
  type: bearer_login
  login_path: /api/auth/login
  username_field: username
  password_field: password
  username_env: TEST_USERNAME
  password_env: TEST_PASSWORD
cases:
  - id: TC-DB-CHECK-001
    name: 管理员创建商品（落库）
    method: POST
    path: /api/products
    json_body:
      name: "DB对比测试-自动化"
      description: "api_db_check 模板写入"
      price: 88.88
      stock: 5
    expect_status: 201
  - id: TC-DB-CHECK-002
    name: 商品列表含新建记录
    method: GET
    path: /api/products
    no_auth: true
    expect_status: 200
    expect_body_substrings:
      - "DB对比测试-自动化"
---

# API + 数据库对比测试

本 spec 生成 **API 层**断言；数据库对账在生成的 pytest 文件末尾按需追加（见下方示例）。

## 运行

```bash
export TEST_BASE_URL=http://your-server:5001
export TEST_USERNAME=admin
export TEST_PASSWORD=admin123
./generate.sh templates/api_db_check.md
./run_pytest.sh output/api_db_check.py -v
```

## 可选：MySQL 对账（Docker 默认映射 3309）

```python
# 在 output/api_db_check.py 末尾手动追加（需 pip install pymysql）
import os
import pymysql

def test_product_row_in_db():
    """验证 API 创建的商品已写入 products 表"""
    conn = pymysql.connect(
        host=os.environ.get("DB_HOST", "127.0.0.1"),
        port=int(os.environ.get("DB_PORT", "3309")),
        user=os.environ.get("DB_USER", "root"),
        password=os.environ.get("DB_PASSWORD", "seckill123"),
        database=os.environ.get("DB_NAME", "seckill_finance_db"),
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT name, price FROM products WHERE name=%s ORDER BY id DESC LIMIT 1",
                ("DB对比测试-自动化",),
            )
            row = cur.fetchone()
            assert row is not None, "products 表中无对应记录"
            assert row[0] == "DB对比测试-自动化"
            assert float(row[1]) == 88.88
    finally:
        conn.close()
```

**适用场景**：接口 201 已通过，需确认数据真实落库且字段正确。
