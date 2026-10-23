---
name: testcase-data-generator
description: After cases are approved, derives data needs per case and emits prep/teardown scripts (SQL, shell, or Python). Use between review and execution.
---

# 测试数据生成

**版本**: v2.0
**触发时机**: 测试用例评审通过后，开始执行前

---

## 这个模块做什么

测试用例写完后，执行之前，需要准备对应的数据。这个模块负责三件事：

1. 看用例清单，列出每条用例需要什么数据
2. 生成数据准备脚本（SQL / Shell / Python 三选一）
3. 生成对应的清理脚本，测试完把数据删掉

---

## 什么时候用

| 场景 | 是否使用 |
|------|---------|
| 用例评审完成，准备执行 | 必须 |
| 用例不依赖预置数据 | 跳过 |
| 环境已有足够数据 | 跳过 |

### 与 `data-factory` 怎么选

| 你的需求 | 走哪条 | 入口 |
|----------|--------|------|
| MySQL 声明式造数、导出 CSV、挂 pytest setup | **`data-factory`** | `templates/data_factory.md` → `./generate.sh` |
| 秒杀/API/UI 铺底变量 | **`data-factory` setup** | `POST /api/test/init`（见 `templates/api_smoke.md` setup） |
| 按用例表梳理「每条要什么数据」、写 SQL/shell/Python | **本模块** | 评审后 AI 产出 `data_setup.sh` / `data_gen.py` |
| JMeter 多用户 CSV 已 codegen | **`data-factory`** | 先 `data_factory.md`，再 `jmeter_test.md` |

不确定时：`@intent-router/SKILL.md`（「用例数据设计」→ 本模块；「数据工厂/CSV」→ `data-factory`）。

---

## 数据分类

先理清要造什么数据，分四类：

| 类别 | 说明 | 典型例子 |
|------|------|---------|
| 基础数据 | 系统运行必需 | 用户账号、角色、权限配置 |
| 业务数据 | 测试功能用 | 活动、商品、订单、Redis 库存 |
| 边界数据 | 测极限和异常 | 超长文本、超大文件、空值 |
| 安全数据 | 测注入和攻击 | SQL注入字符串、XSS脚本 |

理清类别后，再排一下创建顺序——先有用户才能建订单，先有分类才能建商品。

---

## 数据设计示例

以 **秒杀财务系统**（`http://your-server:5001`）为例：

```markdown
# 测试数据设计

## 账号清单
| 账号 | 密码 | 角色 | 用途 |
|------|------|------|------|
| admin | admin123 | admin | 商品/秒杀活动/预热 |
| customer_01 | pass1234 | customer | 秒杀下单 |
| customer_02 | pass1234 | customer | 限购第二条 |

## 商品与活动
| 商品名称 | price | stock | _stock | 用途 |
|--------|-------|-------|---------------|------|
| seckill-demo-product | 19.9 | 100 | 10 | 正常预热+下单 |
| 演示-售罄 | 9.9 | 0 | 0 | 库存边界 |

## 边界数据
| 类型 | 值 | 用途 |
|------|-----|------|
| 超长商品名称 | 51 字符（若上限 50） | 名称校验 |
| 价格为 -1 | -1 | POST /api/products 拒绝 |
| XSS | `<script>alert(1)</script>` | name 字段存储/展示 |
```

---

## 生成脚本

根据环境选择一种方式生成数据。

### API 方式（推荐，与演示系统一致）

```bash
#!/bin/bash
# setup_示例业务.sh
API="http://your-server:5001"

# 初始化 admin（见 POST /api/test/init）
curl -s -X POST "$API/api/test/init" \
  -H "Content-Type: application/json" \
  -d '{"admin_password":"admin123"}'

# 登录拿 Token
TOKEN=$(curl -s -X POST "$API/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' | jq -r '.token // .access_token')

# 创建商品（需 admin）
curl -s -X POST "$API/api/products" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"演示-数据工厂","price":19.9,"stock":100,"_stock":10}'

# 注册 customer
curl -s -X POST "$API/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"username":"customer_01","password":"pass1234","email":"c01@test.local"}'
```

### SQL 方式（直连 MySQL，表名以 `schema.sql` 为准）

```sql
-- 仅示例：执行前确认测试库；优先用 POST /api/test/init + API 造数
```

### Python 方式（批量生成）

```python
#!/usr/bin/env python3
# bulk_data_gen.py
# 适合需要生成大量随机数据的场景

import requests
import random
import string

API = "http://your-server:5001"

def make_random_name(prefix="演示", length=6):
    suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))
    return f"{prefix}_{suffix}"

def admin_token():
    r = requests.post(f"{API}/api/auth/login", json={
        "username": "admin", "password": "123456"
    })
    return r.json().get("token") or r.json().get("access_token")

def create_developers(n=3):
    for i in range(n):
        resp = requests.post(f"{API}/api/auth/register", json={
            "username": f"developer_{i+1:02d}",
            "password": "pass1234",
            "email": f"c{i+1}@test.local"
        })
        print(f"developer {i+1}: {resp.status_code}")

def create_products(n=5, token=None):
    for i in range(n):
        resp = requests.post(f"{API}/api/products", headers={
            "Authorization": f"Bearer {token}"
        }, json={
            "name": make_random_name(),
            "price": round(random.uniform(9.9, 99.9), 2),
            "stock": random.randint(10, 200)
        })
        print(f"商品 {i+1}: {resp.status_code}")

if __name__ == "__main__":
    tok = admin_token()
    create_developers(3)
    create_products(5, tok)
```

---

## 清理脚本

测试跑完记得清理，避免脏数据影响下一轮。

```python
#!/usr/bin/env python3
# cleanup_test_data.py

import requests

API = "http://your-server:5001"

def cleanup():
    # 财务：优先用测试库脚本或 admin 软删商品；以下为示意
    resp = requests.get(f"{API}/api/products")
    for p in resp.json():
        if str(p.get("name", "")).startswith("演示"):
            # DELETE /api/products/{id} 需 admin Token，略
            pass
    # developer_xx 用户清理依 ORM 与外键，见 schema.sql

    print("清理完成")

if __name__ == "__main__":
    cleanup()
```

---

## 输出文件

| 文件名 | 内容 |
|--------|------|
| `data_design.md` | 数据设计文档，列出需要什么数据 |
| `data_setup.sql` | SQL 导入脚本 |
| `data_setup.sh` | API 调用脚本 |
| `data_gen.py` | Python 批量生成脚本 |
| `data_cleanup.py` | 清理脚本 |

三个设置脚本选一个用，清理脚本必须生成。

---

## 经验建议

1. **测试数据必须带标识**——用户名 `developer_xx`、商品名称 `演示-` 前缀，清理时好过滤
2. **删除顺序和创建顺序相反**——先删订单再删商品，先删商品再删用户，否则外键约束会报错
3. **不要用生产数据**——脱敏数据也不行，万一泄露责任大，全部用虚构数据
4. **边界数据单独造**——超长文本、特殊字符、空值这些单独准备，不要混在正常数据里
5. **脚本加幂等性**——每次跑之前先清理，避免重复执行导致数据翻倍

---

## 配合关系

- 上游：testcase-skills 出完用例后触发
- 下游：UI-skills 和 api-skills 执行测试时用到这些数据
