---
name: data-factory
description: Generates and injects test data from declarative specs to speed setup. Use when tests need repeatable datasets or DB/API seeding.
---

# 数据工厂 Skill

## 用途

测试前准备数据太耗时。这个 skill 通过 **声明式 spec（`kind: data_factory`）** 或 **pytest setup 脚本** 自动生成/注入数据。

> **与 `testcase-data-generator` 的分工**：本模块走 codegen（MySQL/CSV/pytest 铺底）；用例评审后的数据设计文档/SQL 脚本 → `@testcase-data-generator/SKILL.md`。  
> **与压测**：`csv_export` + `extra_columns.password` → `output/users.csv` → `jmeter_test.md` / `perf_test_k6_multiuser.md`（见 `load-testing/执行/SKILL.md`）。

## 使用方式

### 方式一：本地脚本生成

写一个 spec 文件：

```markdown
---
kind: data_factory
database:
  host: localhost
  port: 3306
  name: test_db
  user: root
tables:
  - name: users
    count: 50
    fields:
      username: "user_{i}"
      email: "user{i}@test.com"
      status: random_choice("active", "inactive")
  - name: orders
    count: 100
    fields:
      user_id: ref("users.id")
      amount: random_float(10, 5000)
      status: random_choice("pending", "paid", "cancelled")
      created_at: random_date("2025-01-01", "2025-12-31")
csv_export:
  - table: users
    file: output/users.csv
    fields: [id, username, password, email]
cleanup:
  tables: [orders, users]
seed_mode: replace   # append | replace（replace 先清理再插入）
---

# 测试数据准备
```

生成并执行：

```bash
./generate.sh data_spec.md
cd output && python3 data_spec.py
```

> 注意：生成器根据 spec 文件中的 `kind: data_factory` 自动选择渲染器，不需要 `--data-factory` 参数。

### 方式二：AI 辅助生成

在 AI 编辑器 Chat 中：

```
@data-factory/SKILL.md

帮我生成 100 个用户和 500 个订单的测试数据。
用户需要包含正常状态、禁用状态、未激活状态。
订单需要覆盖：待支付、已支付、已取消、已退款。
数据直接注入到测试数据库。
```

## 数据生成策略

### 基础字段

| 策略 | 说明 | 示例 |
|------|------|------|
| 顺序递增 | 带序号 | `user_001`, `user_002` |
| 随机选择 | 从预设列表随机 | `random_choice("active", "inactive")` |
| 随机数值 | 指定范围 | `random_float(10, 5000)` |
| 随机日期 | 指定日期范围 | `random_date("2025-01-01", "2025-12-31")` |
| 固定值 | 所有行相同 | `status: "active"` |

### 关联数据

跨表关联用 `ref()` 引用：

```yaml
tables:
  - name: users
    count: 50
    fields:
      id: auto_increment
  - name: orders
    count: 100
    fields:
      user_id: ref("users.id")  # 引用 users 表的 id
```

### 特殊数据

需要边界值或异常数据时，在 spec 中显式声明：

```yaml
tables:
  - name: users
    count: 50
    special_rows:
      - username: ""           # 空值
      - username: "a" * 200    # 超长
      - email: "not-an-email"  # 格式错误
      - status: null           # NULL 值
```

## 环境重置（规划中，SKILL 文档）

> 状态：**规划中**（见包根 `README.md` → 技能目录 → `data-factory`）。声明式 MySQL 造数仍为 **可执行**（`kind: data_factory` + `./generate.sh`）。

测试前需要干净环境。目前只有 SKILL 文档，需要 AI 编辑器辅助使用：

```
@data-factory/SKILL.md

帮我生成环境重置脚本。
需要：清空所有表、重新执行迁移、注入基础数据、清理 Redis 缓存。
数据库：test_db，localhost:3306。
```

AI 会生成一个 Python 脚本，包含 truncate、migrate、seed、cache_clear 等操作。

## 注意事项

1. **只在测试环境执行**：生成器会检查数据库名是否包含 `test`、`dev`、`staging`，生产库直接拒绝
2. **幂等性**：重复执行相同 spec，数据一致（用 `count` 控制，不会叠加）
3. **数据量控制**：默认单次最多生成 1000 条，超出需要显式确认
4. **回滚机制**：执行前自动创建数据库快照，失败可回滚
