# 测试用例示例

> 均基于 **秒杀财务系统**（`seckill_finance_system`）。黄金样例另见包根 `examples/output_seckill_auth_testcases.md`。

## 示例 1：简单功能（二级）— 认证片段

```markdown
# 用户认证 - 测试用例

## 文档信息
- 依据需求：examples/prd_mini_seckill_auth.md
- 测试范围：注册、登录、Profile
- 结构说明：功能 → 检查点（2 级）

---

## 用户登录

### 正确凭证返回 JWT
- admin / admin123 调用 POST /api/auth/login，HTTP 200，响应含可用 Token

### 错误密码拒绝登录
- 正确 username + 错误 password，HTTP 401，无有效 Token
```

---

## 示例 2：标准功能（三级）— 商品管理片段

```markdown
# 商品管理 - 测试用例

## 文档信息
- 依据需求：seckill_finance_system/需求文档.md §2.2
- 测试范围：列表、详情、管理员新增
- 结构说明：功能 → 场景 → 检查点（3 级）

---

## 浏览在售商品列表

### 状态过滤

#### 仅展示在售
- 库中同时在售与已下架商品，GET /api/products 仅见 active 项

### 字段展示

#### 关键销售信息
- 在售商品在列表展示名称与当前价；有进行中秒杀时体现秒杀价或秒杀态

---

## 查看商品详情

### 访问控制

#### 已登录用户
- customer 已登录，GET /api/products/{id}，展示名称、描述、价格、库存及秒杀字段（若配置）

#### 未登录用户
- 未带 Token 访问详情，HTTP 401 或跳转 /login（与实现一致）

---

## 新增商品（管理员）

### 必填与默认状态

#### 仅填名称与常规价
- admin POST 提交 name 与 price，201 且状态默认为在售

### 校验

#### 价格为负数
- price=-1，拒绝并提示

#### 名称为空
- name 为空或全空白，拒绝并提示
```

---

## 示例 3：核心流程 + 详细功能（完整结构）

```markdown
# 秒杀财务 - 秒杀下单 - 测试用例

## 文档信息
- 依据需求：seckill_finance_system/需求文档.md §2.3
- 结构说明：含核心流程 + 详细功能点

---

## 核心流程测试

### 流程1：customer 在进行中活动下单成功
- GET /api/products 浏览商品
  - POST /api/auth/login 登录
    - 确认活动 ACTIVE 且 Redis 库存>0
      - POST /api/seckill/{activity_id}/{product_id}
        - 返回成功，订单 pending，库存扣减

---

## 详细功能点测试

## 秒杀下单
### 库存不足
#### 最后一件被抢后再次下单
- Redis 库存为 0 时再次 POST 下单，返回约定错误，无重复扣减

### 限购
#### 已达每用户限购次数
- 同一 customer 第 N+1 次下单（N 为 PRD 限购数），拒绝并提示
```

---
