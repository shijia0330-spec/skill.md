---
name: data-planning
description: 设计数据表结构、字段、关联关系、创建顺序。
---

# 数据规划

设计数据表结构、字段、关联关系、创建顺序。

---

## 做 / 不做

| 做 | 不做 |
|----|------|
| 设计数据表结构 | 生成注入脚本（走执行/SKILL.md） |
| 定义字段类型和约束 | |
| 确定创建顺序 | |

---

## 数据设计示例

以秒杀财务系统为例：

### 账号清单

| 账号 | 密码 | 角色 | 用途 |
|------|------|------|------|
| admin | admin123 | admin | 商品/活动/预热 |
| customer_01 | pass1234 | customer | 秒杀下单 |
| customer_02 | pass1234 | customer | 限购第二条 |

### 商品与活动

| 商品名 | price | stock | seckill_stock | 用途 |
|--------|-------|-------|---------------|------|
| 秒杀演示-A | 19.9 | 100 | 10 | 正常预热+下单 |
| 秒杀演示-售罄 | 9.9 | 0 | 0 | 库存边界 |
| 秒杀演示-XSS | 29.9 | 50 | 5 | XSS 测试 |

### 边界数据

| 类型 | 值 | 用途 |
|------|-----|------|
| 超长商品名 | 51 字符（上限 50） | 名称校验 |
| 价格为 -1 | -1 | POST /api/products 拒绝 |
| XSS | `<script>alert(1)</script>` | name 字段存储/展示 |
| 空用户名 | "" | 注册接口校验 |

### 时间边界活动（E-04 / E-05 / E-06）

相对 **服务器当前时间** 创建活动；无 clock mock 时 **禁止**在规划里写「改系统时间」。

| 数据集名 | start_time | end_time | seckill_stock | 对应用例 | 执行侧配合 |
|----------|------------|----------|---------------|----------|------------|
| 活动-未开始 | now()+2s | now()+3600s | 10 | E-04 | customer sleep(1) 后 POST，期望 4xx |
| 活动-将开始 | now()+2s | now()+3600s | 10 | E-05 | customer sleep(2) 后 POST，期望 200/201 |
| 活动-已结束 | now()-3600s | now()-2s | 10 | E-06 | customer sleep(2) 后 POST，期望 4xx |

创建顺序：admin 登录 → 商品 P1 → 活动（含时间窗）→ `prepare-stock`（E-05 需要）→ 写入 `output/test_seed.env`（`ACTIVITY_ID` / `PRODUCT_ID`）。

脚本：`python3 output/seckill_time_boundary_upcoming.py`（E-04）| `..._active.py`（E-05）| `..._ended.py`（E-06）；库：`scripts/seckill_time_boundary_lib.py`。

---

## 创建顺序

```
1. admin 账号（系统初始化）
2. customer 账号（依赖 admin 初始化）
3. 商品数据（依赖 admin token）
4. 活动数据（依赖商品）
5. 订单数据（依赖用户+商品）
```

**原则**：先基础后业务，先父后子。删除时顺序相反。

---

## 关联数据设计

跨表关联用 `ref()` 表示：

```yaml
tables:
  - name: users
    count: 50
    fields:
      id: auto_increment
  - name: orders
    count: 100
    fields:
      user_id: ref("users.id")   # 引用 users 表的 id
      product_id: ref("products.id")  # 引用 products 表的 id
```

---

## 输出

输出 `数据规划_<模块>_<日期>.md`，包含账号表 + 商品表 + 边界数据表 + 创建顺序。
