---
kind: data_factory
database:
  host: localhost
  port: 3309
  name: seckill_finance_db
  user: root
  password: "***"
tables:
  - name: users
    count: 50
    fields:
      id: auto_increment
      username: "user_{i}"
      password_hash: hash_password("Test123!")
      email: "user{i}@test.com"
      role: random_choice("customer", "admin")
      created_at: random_date("2025-01-01", "2025-12-31")
      updated_at: random_date("2025-01-01", "2025-12-31")
      is_active: 1
  - name: orders
    count: 100
    fields:
      id: auto_increment
      order_no: "ORD-{i}"
      user_id: ref("users.id")
      total_amount: random_float(10, 5000)
      status: random_choice("pending", "paid", "cancelled", "refunded")
      order_type: random_choice("normal", "seckill")
      created_at: random_date("2025-01-01", "2025-12-31")
      updated_at: random_date("2025-01-01", "2025-12-31")
csv_export:
  - table: users
    file: users.csv
    fields: [username]
    extra_columns:
      password: "Test123!"
---

# 测试数据造数模板（匹配 seckill_finance_system 表结构）

## 用法

```bash
# 生成脚本
python3 codegen/run_spec.py templates/data_factory.md -o output/data_factory.py

# 运行造数（同时导出 CSV）
cd output && python3 data_factory.py

# 清空后重建
python3 data_factory.py --reset

# 精确清理（删除本次插入的数据，不影响其他数据）
python3 data_factory.py --cleanup
```

## 自动追踪 Created IDs

造数脚本插入数据后，自动将每个表的插入 ID 列表保存到 `output/data_refs.json`。

```json
{
  "users.ids": [1, 2, 3, ..., 50],
  "orders.ids": [1, 2, 3, ..., 100]
}
```

`--cleanup` 模式读取该文件，按 ID 精确删除：

```sql
DELETE FROM `orders` WHERE id IN (1,2,3,...,100);
DELETE FROM `users` WHERE id IN (1,2,3,...,50);
```

**逆序删除**：先删 orders（子表），再删 users（父表），避免外键约束报错。

## 与 pytest 集成

在 API/UI spec 中引用造数脚本作为 setup：

```yaml
setup:
  kind: data_factory
  script: output/data_factory.py

# 测试后精确清理
teardown:
  mode: data_factory_cleanup
  script: output/data_factory.py
```

或直接用 `refs_cleanup`（不走造数脚本，直接读 refs 文件）：

```yaml
teardown:
  mode: refs_cleanup
```

## 每条用例独立造数+清理

默认 session 级（所有用例共享同一批数据）。如需 per-test 隔离：

```yaml
setup:
  kind: data_factory
  script: output/data_factory.py
  scope: function

teardown:
  mode: refs_cleanup
  scope: function
```

`scope: function` 时每条 pytest 用例执行前造数，执行后清理，互不污染。

## CSV 导出（性能测试数据）

`csv_export` 配置段让造数脚本在插入数据后，将指定表的字段导出为 CSV 文件。

**登录压测须导出明文 `password`（非 `password_hash`）**，登录 API 接收明文密码，服务端自行校验 hash。

```yaml
csv_export:
  - table: users
    file: users.csv
    fields: [username]              # DB 列，按顺序排在前面
    extra_columns:
      password: "Test123!"          # 常量列，供 JMeter/k6 登录
```

`password_hash` 入库使用 `hash_password("Test123!")` 生成 scrypt hash（需 `pip install werkzeug`）。

导出 CSV 列顺序 = `fields` + `extra_columns` 键，须与 JMeter `variableNames` / k6 读取列一致（建议 `[username, password]`）。

**完整流程：**

```
1. data_factory 造 50 个用户 → users 表（password_hash 为真实 hash）
2. data_factory 导出 users.csv（username, password 明文）
3. JMeter/k6 读取 users.csv → 每线程/VU 一账号
4. 并发登录 → 压测业务接口
5. 清理 → data_factory --cleanup
```

**并发对齐**：`tables.users.count` ≥ 目标并发线程/VU 数；规划阶段写明 `N = count`。

## 注意

- `--reset` 会先清空 users/orders 表再插入，避免主键冲突
- `--cleanup` 只删除本次插入的 ID，不影响手动创建的数据
- `data_refs.json` 在 cleanup 后自动删除
- CSV 文件路径相对于脚本所在目录（output/）
- 压测前勿用 `fetch_perf_token.py` 预灌单 Token（多用户场景每 VU 独立登录）
