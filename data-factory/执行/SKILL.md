---
name: data-execution
description: 数据注入 — 支持 spec 声明式、API、SQL、Python 四种方式，字段名自动映射 faker 类型。
---

# 数据执行

生成数据注入脚本，支持四种方式，**字段名自动映射 faker 类型**。

---

## 做 / 不做

| 做 | 不做 |
|----|------|
| 生成数据注入脚本 | 设计数据（走规划/SKILL.md） |
| 字段名→faker 类型自动映射 | 清理数据（走清理/SKILL.md） |

---

## 方式一：Spec 声明式（推荐）

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
---
```

```bash
./generate.sh data_spec.md
cd output && python3 data_spec.py
```

**与 API/UI 自动化联动**：在 `api_pytest` / `ui_pytest_playwright` spec 里可写：

```yaml
setup:
  kind: data_factory
  script: output/data_factory.py   # 相对 skills 根目录；默认即此路径
```

pytest session 开始前自动执行该脚本；简单场景用默认 `setup: test_init`（调 `POST /api/test/init`）即可，不必走 MySQL 造数。

---

## 字段名→faker 类型自动映射（核心能力）

当字段名匹配以下规则时，自动生成对应的 faker 数据：

| 字段名正则 | faker 类型 | 生成示例 |
|-----------|-----------|---------|
| `name$` | `name()` | 张三 |
| `user_name$` / `username$` | `user_name()` | zhangsan |
| `phone$` / `mobile$` / `tel$` | `phone()` | 13800138000 |
| `email$` / `mail$` | `email()` | user@example.com |
| `address$` / `addr$` | `address()` | 北京市朝阳区 |
| `city$` | `city()` | 北京市 |
| `province$` | `province()` | 北京市 |
| `company$` / `corp$` | `company()` | 科技有限公司 |
| `title$` / `subject$` | `sentence()` | 测试标题 |
| `content$` / `description$` / `remark$` | `text()` | 这是一段测试内容... |
| `price$` / `amount$` / `cost$` | `price()` | 19.99 |
| `avatar$` / `photo$` / `image$` | `image_url()` | https://example.com/img.jpg |
| `url$` / `website$` | `url()` | https://example.com |
| `company_name$` | `company()` | 科技有限公司 |
| `department$` | `company()` | 技术部 |

### 使用方式

```yaml
tables:
  - name: users
    count: 50
    fields:
      # 不指定值，自动根据字段名映射
      # username → faker.user_name()
      # phone → faker.phone()
      # email → faker.email()
      # name → faker.name()
```

---

## 字段生成策略

| 策略 | 说明 | 示例 |
|------|------|------|
| 顺序递增 | 带序号 | `user_{i}` → user_1, user_2 |
| 随机选择 | 从预设列表 | `random_choice("active", "inactive")` |
| 随机数值 | 指定范围 | `random_float(10, 5000)` |
| 随机日期 | 指定范围 | `random_date("2025-01-01", "2025-12-31")` |
| 固定值 | 所有行相同 | `status: "active"` |
| 关联引用 | 跨表引用 | `ref("users.id")` |
| **自动映射** | 字段名→faker | `phone` → 自动生成手机号 |

---

## 方式二：API 方式

```bash
#!/bin/bash
API="http://your-server:5000"

# 初始化 admin
curl -s -X POST "$API/api/test/init" \
  -H "Content-Type: application/json" \
  -d '{"admin_password":"admin123"}'

# 登录拿 Token
TOKEN=$(curl -s -X POST "$API/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' | jq -r '.token')

# 创建商品
curl -s -X POST "$API/api/products" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"秒杀演示-A","price":19.9,"stock":100}'
```

---

## 方式三：SQL 方式

```sql
INSERT INTO users (username, email, status) VALUES
  ('customer_01', 'c01@test.local', 'active'),
  ('customer_02', 'c02@test.local', 'active');
```

---

## 方式四：Python 批量生成

```python
import requests, random, string

API = "http://your-server:5000"

def make_random_name(prefix="秒杀演示", length=6):
    suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))
    return f"{prefix}_{suffix}"

def admin_token():
    r = requests.post(f"{API}/api/auth/login", json={
        "username": "admin", "password": "admin123"
    })
    return r.json().get("token")

def create_customers(n=3):
    for i in range(n):
        requests.post(f"{API}/api/auth/register", json={
            "username": f"customer_{i+1:02d}",
            "password": "pass1234",
            "email": f"c{i+1}@test.local"
        })

if __name__ == "__main__":
    create_customers(3)
```

---

## 方式选择

| 场景 | 推荐方式 |
|------|----------|
| 有数据库直连权限 | spec 声明式 |
| 有 API 接口 | API 方式 |
| 需要复杂逻辑 | Python 批量 |
| 简单导入 | SQL 方式 |

---

## 安全规则

1. **只在测试环境执行** — 数据库名必须包含 `test`、`dev`、`staging`
2. **幂等性** — 重复执行不叠加
3. **数据量控制** — 默认单次最多 1000 条
4. **不用生产数据** — 全部虚构

---

## 输出文件

| 文件名 | 内容 |
|--------|------|
| `data_setup.py` | spec 生成的注入脚本 |
| `data_setup.sh` | API 调用脚本 |
| `data_setup.sql` | SQL 导入脚本 |
| `data_gen.py` | Python 批量生成脚本 |

选一个用，不混用。
