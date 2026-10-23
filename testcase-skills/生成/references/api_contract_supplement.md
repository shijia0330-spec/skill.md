# 接口契约补充（OpenAPI / Swagger）

> 契约文件示例：`seckill_finance_system/openapi.yaml`。

当用户提供 **OpenAPI、Swagger 或接口文档** 时，在 PRD 测试点之外叠加本补充；**不替代** PRD 业务场景。

---

## 1. 何时加载

- 用户 `@` 了 `openapi.yaml` 或 `API接口文档.md`
- PRD 写明「见接口文档」
- 生成接口自动化前的 **功能用例对齐**

---

## 2. 与 PRD 的关系

| 情况 | 处理 |
|------|------|
| PRD 与契约一致 | 检查点写业务语言，括号注明状态码/字段 |
| PRD 有、契约无 | 以 PRD 为准，标「契约待同步」 |
| 契约有、PRD 无 | 生成检查点并标「（PRD 未写，契约存在）」或列入待澄清 |
| 冲突 | 写入待澄清清单，**不擅自选边** |

---

## 3. 每个端点至少覆盖

| 类别 | 检查点 |
|------|--------|
| 鉴权 | 无 Token → 401；customer 调 admin 接口 → 403 |
| 成功 | 契约成功码 + 关键响应字段（如 `id`、`status`） |
| 路径/查询参数 | 合法 product_id；不存在 → 404 |
| 请求体必填 | 缺 `name`/`price` 各 1 条 → 400 |
| 类型错误 | price 传字符串 → 400/422 |
| 枚举 | 非法 `status` 过滤值 → 400 |

---

## 4. 与 HTTP 方法映射（秒杀财务常见）

| 方法 | 端点示例 | 额外关注 |
|------|----------|----------|
| GET | /api/products | 匿名 200；仅 active |
| GET | /api/products/{id} | 需登录；404 |
| POST | /api/products | admin 201；customer 403 |
| POST | /api/auth/login | 200 + token；错密 401 |
| POST | /api/seckill/{aid}/{pid} | 成功下单；库存不足错误码 |
| POST | .../prepare-stock | admin；Redis 不可用时的错误 |

---

## 5. 示例（商品列表 GET）

```markdown
#### L-API-01 未登录可访问商品列表（契约）
- GET /api/products 无 Authorization，返回 200 且 body 为数组

#### L-API-02 响应项含在售商品关键字段（契约）
- 任一项含 name、price（及 PRD 要求的 status 或等价字段）
```

---

## 6. 不宜写进功能用例的

- 具体框架实现、数据库表名（如 `seckill_orders` 表结构）
- 与 PRD 无关的全量 fuzz
- 性能压测数字（见 `appendix_performance.md`）

接口 **自动化脚本** 由 `./generate.sh` + `api_pytest` spec 生成；本文件只约束 **测试点文档** 与契约对齐。
