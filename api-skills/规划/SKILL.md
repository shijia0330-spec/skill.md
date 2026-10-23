---
name: api-planning
description: Plans API test rounds from OpenAPI/Swagger or GraphQL SDL (scope, sequencing, sample data). Use for contract-first API test planning before deeper analysis and execution.
---

# API 测试规划 — 从契约拉出一轮可执行的 backlog

手里有 **OpenAPI / Swagger**，有时还有 **GraphQL SDL**。这份 SKILL 管的是：在一轮迭代里**测哪些接口、 roughly 什么顺序、用什么假数据**，给后面的分析和执行打底。

---

## 1. 进来要带什么

| 内容 | 说明 |
|------|------|
| 契约文件或路径 | 必填 |
| `base_url` | 必填；指向测试或沙箱，别写生产 |
| 开关（可选） | 要不要顺带点一下「接口活没活」、要不要生成安全/边界场景 |

---

## 2. 规划产出模板

拿到契约后，输出一份结构化的测试计划：

```yaml
# api_test_plan.yaml
project: "电商后端V3"
base_url: "https://api-staging.example.com"
contract: "openapi/v3/products.yaml"

modules:
  - name: "商品接口"
    endpoints:
      - "GET /api/products"           # 列表查询
      - "POST /api/products"          # 新增商品
      - "PUT /api/products/{id}"      # 更新商品
      - "DELETE /api/products/{id}"   # 删除商品
    priority: "P0"
    scenarios:
      - "主流程：CRUD 完整走一遍"
      - "边界：空列表、超大分页"
      - "安全：未登录创建/删除"

  - name: "用户认证"
    endpoints:
      - "POST /api/auth/login"
      - "POST /api/auth/register"
      - "GET /api/auth/profile"
    priority: "P0"
    scenarios:
      - "主流程：注册→登录→获取信息"
      - "边界：密码长度边界、用户名特殊字符"
      - "安全：Token 过期、伪造 Token"
```

---

## 3. 样本数据生成

根据契约中的字段定义，自动生成测试数据：

```python
# 契约中的定义
# properties:
#   name:        { type: string, maxLength: 50 }
#   price:       { type: number, minimum: 0, maximum: 999999 }
#   category:    { type: string, enum: ["电子产品", "食品", "服装"] }
#   stock:       { type: integer, minimum: 0 }

# 生成的样本数据
sample_data = {
    "name": "测试商品A",              # 正常值
    "price": 99.99,                   # 正常值
    "category": "电子产品",            # 枚举第一个
    "stock": 100,                     # 正常值
}

# 边界数据（用于负面测试）
boundary_data = [
    {"name": "", "price": -1},                     # 空名称 + 负价格
    {"name": "A" * 51, "price": 1000000},          # 超长名称 + 超价格
    {"category": "不存在的分类", "stock": -1},      # 非法枚举 + 负库存
]
```

---

## 4. 一般包含几块能力

**（可选）接口探测**  
对文档里的地址做个浅请求（注意别误删数据），早发现「文档有、环境没有」的僵尸接口：

```bash
# 快速探测
for path in $(cat endpoints.txt); do
    status=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL$path")
    echo "$path → $status"
done
```

**样本数据**：按字段上的类型、长度、枚举造一批能用的 JSON；带个人隐私的用占位符。

**GraphQL**：若是 SDL，往往会先转成和 REST 那边能对应的中间结构，后面步骤接着用。

**计划正文**：通常会揉出几块：**主流程场景**、**安全相关试一下**、**边界歪数据**、**造好的样本数据集**；若开了探测，还会带一份**探测结果摘要**。

---

## 5. 工程上几条习惯

1. 第一次接仓库该跑的初始化脚本（例如 `api_project_setup`）别跳过，缓存路径统一好
2. 契约优先走**本地文件路径**，URL 拉 Swagger 容易 CI 抽风
3. `base_url` 从环境变量或 `.env` 读，别写死公网
4. 一次调用尽量把本轮需要的计划吐全，避免重复刷同一个大契约
5. 探测大面积超时先查 VPN、DNS、证书，别硬生成场景

---

## 6. 示例（秒杀财务系统）

契约新增 `POST /api/seckill/activities/{id}/prepare-stock`：

- 主流程：admin 预热后 customer `POST /api/seckill/{aid}/{pid}` 下单，Redis 库存扣减
- 安全：customer 不得调 prepare-stock；用户 A 不得查用户 B 的 `GET /api/seckill/order/{id}`
- 边界：活动未开始/已结束下单；库存 0；价格为负的 `POST /api/products`

---

## 7. 什么时候别往下走

- 契约文件语法都过不去 → 先修文档或解析器
- 主流程场景列表是空的 → 配置错了或契约真的是空的

---

## 8. 下游谁吃这份输出

| 谁 | 拿走啥 |
|----|--------|
| `02_接口分析` | 接口清单、依赖草稿 |
| `01_测试用例生成` | 场景矩阵 |
| 代码生成 | 样本数据集 |
