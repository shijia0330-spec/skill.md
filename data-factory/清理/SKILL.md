---
name: data-cleanup
description: 生成数据清理脚本，测试完删除脏数据，保持环境干净。
---

# 数据清理

测试跑完清理数据，避免脏数据影响下一轮。

---

## 做 / 不做

| 做 | 不做 |
|----|------|
| 生成清理脚本 | 注入数据（走执行/SKILL.md） |
| 按相反顺序删除 | |

---

## 清理原则

1. **删除顺序和创建顺序相反** — 先删订单再删商品，先删商品再删用户
2. **按标识过滤** — 用户名 `customer_xx`、商品名 `秒杀演示-` 前缀，清理时好过滤
3. **幂等性** — 多次执行不报错
4. **软删优先** — 能用 UPDATE 不用 DELETE

---

## Python 清理脚本

```python
#!/usr/bin/env python3
# data_cleanup.py

import requests

API = "http://your-server:5000"

def cleanup():
    token = None  # 获取 admin token

    # 1. 删除订单（先删子表）
    resp = requests.get(f"{API}/api/orders", headers={"Authorization": f"Bearer {token}"})
    for order in resp.json():
        if order.get("user_id") and str(order["user_id"]).startswith("customer_"):
            requests.delete(f"{API}/api/orders/{order['id']}",
                          headers={"Authorization": f"Bearer {token}"})

    # 2. 删除商品（再删父表）
    resp = requests.get(f"{API}/api/products")
    for p in resp.json():
        if str(p.get("name", "")).startswith("秒杀演示"):
            requests.delete(f"{API}/api/products/{p['id']}",
                          headers={"Authorization": f"Bearer {token}"})

    # 3. 删除测试用户（通过 auth 注册接口创建的 customer_* 账号需管理员在后台清理；此处仅删商品）

    print("清理完成")

if __name__ == "__main__":
    cleanup()
```

---

## SQL 清理脚本

```sql
-- 先删子表，再删父表
DELETE FROM orders WHERE user_id IN (SELECT id FROM users WHERE username LIKE 'customer_%');
DELETE FROM products WHERE name LIKE '秒杀演示%';
DELETE FROM users WHERE username LIKE 'customer_%';
```

---

## Shell 清理脚本

```bash
#!/bin/bash
# data_cleanup.sh
API="http://your-server:5000"
TOKEN="your_admin_token"

# 删除所有测试商品
for id in $(curl -s "$API/api/products" | jq -r '.[] | select(.name | startswith("秒杀演示")) | .id'); do
  curl -s -X DELETE "$API/api/products/$id" \
    -H "Authorization: Bearer $TOKEN"
done

echo "清理完成"
```

---

## 环境重置（可选）

需要完全重置环境时：

```python
#!/usr/bin/env python3
# env_reset.py

import subprocess

def reset():
    # 1. 清空所有表
    subprocess.run(["mysql", "-u", "root", "test_db", "-e",
                    "SET FOREIGN_KEY_CHECKS=0; DROP DATABASE test_db; CREATE DATABASE test_db; SET FOREIGN_KEY_CHECKS=1;"])

    # 2. 重新执行迁移
    subprocess.run(["python", "migrate.py"])

    # 3. 注入基础数据
    subprocess.run(["python", "data_setup.py"])

    # 4. 清理 Redis
    subprocess.run(["redis-cli", "FLUSHDB"])

    print("环境重置完成")

if __name__ == "__main__":
    reset()
```

---

## 输出

输出 `data_cleanup.py` 或 `data_cleanup.sh`，与注入脚本放在同一目录。
