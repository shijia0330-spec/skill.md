# 时间与状态覆盖

> 主场景：**秒杀活动** UPCOMING / ACTIVE / ENDED、商品 active/inactive、订单 pending 等。

PRD 出现 **活动时间、有效期、状态、次数限制** 时，除 `boundary_value_testing.md` 数值边界外，须按本章生成检查点。

---

## 1. 时间窗（秒杀活动）

### 必测三态（PRD 未写预期则标待澄清）

| 状态 | 条件 | 检查点要点 |
|------|------|------------|
| UPCOMING | 当前时间 < start | 不可下单；列表/详情价展示（待澄清） |
| ACTIVE | start ≤ 现在 ≤ end | 可下单；秒杀价生效 |
| ENDED | 现在 > end | 不可下单；恢复常规价（以 PRD 为准） |

### 时间边界 trio

- 结束前 1 秒 / 结束时刻 / 结束后 1 秒  
- 开始前 1 秒 / 开始时刻 / 开始后 1 秒  

### 1.1 时间边界 · API 自动化三件套（强制）

被测系统通常 **无改时钟 test API**（仅有 `POST /api/test/init` 铺底）。  
时间边界用例 **禁止**把「当前时间 = …」当作操作步骤；须写成下面 **造数 → 对齐时刻 → 断言** 三段。

| 步骤 | 写什么 | 反例 |
|------|--------|------|
| **造数** | admin 创建活动/商品，**写死相对时间**（如 `start=now()+2s`）并记录 `activity_id`、`product_id` | 只写「有一个未开始活动」 |
| **对齐时刻** | `sleep(N)` 或轮询 GET 活动直到 `status=UPCOMING/ACTIVE/ENDED` | 只写「当前时间 = start-1s」 |
| **断言** | HTTP 状态码 + body 错误码/文案 + **无有效 order_id** | 只写「拒绝下单」 |

#### 配方 A：开始前 1 秒（E-04）

1. admin：`start_time = now()+2s`，`end_time = now()+3600s`，绑定库存充足的商品  
2. customer：`sleep(1)` → 可选 GET 确认 `status=UPCOMING`  
3. `POST /api/seckill/{activity_id}/{product_id}` → 期望 **4xx**，不产生订单  

#### 配方 B：开始时刻 / 进行中（E-05）

1. admin：`start_time = now()+2s`，prepare-stock  
2. customer：`sleep(2)` 或轮询至 `status=ACTIVE`  
3. POST 下单 → 期望 **200/201** + `order_id`  

#### 配方 C：已结束（E-06）

1. admin：`start_time = now()-3600s`，`end_time = now()-2s`  
2. customer：`sleep(2)` 或 GET 确认 `status=ENDED`  
3. POST 下单 → 期望 **4xx**  

#### 降级与待澄清

- 无法稳定卡点（CI 慢、无时区约定）→ 用「未来 start 立即下单拒绝」替代精确 -1s，标 `review_required: true`  
- 时区以谁为准（T-03）→ 写入待澄清清单，步骤里注明 **UTC 或服务器本地时区**  
- 需要 Mock 时钟 → 标「（需环境）」；**不要**在 ref 未定义时让 codegen 臆造 `mock_time` 接口  

自动化映射见 `api-skills/执行/references/boundary_and_prd_supplement.md` §2.1；造数脚本见 `scripts/seckill_time_boundary_lib.py`、`output/seckill_time_boundary_*.py`。

### 非法输入

- 创建活动时 `end_time < start_time` → 拒绝（标待澄清若 PRD 未写）

---

## 2. 状态机（商品在售/下架）

### 合法迁移

- 管理员创建商品 → 默认 `active`（在售）
- 管理员软删 → `inactive`（下架）

### 非法迁移

- 已 `inactive` 商品未经管理员操作直接出现在在售列表 → 缺陷

### 与列表/详情联动

- 下架后 `GET /api/products` 不可见  
- 下架后 `GET /api/products/{id}`：404 / 403 — **以 PRD 为准，否则待澄清**

---

## 3. 次数与限购（秒杀每用户限购 N 件）

从 PRD 提取 N，应用 **N-1、N、N+1**：

```markdown
#### 第 N-1 次下单成功
- 同一 customer 在活动内第 N-1 次 POST 下单均成功

#### 第 N 次下单成功
- 第 N 次仍成功（若 PRD 允许购 N 件）

#### 第 N+1 次下单拒绝
- 返回限购相关错误，不生成新订单
```

若 PRD **无** 登录失败锁定规则，不要编造「密码错误 N 次锁定」；仅在有明确描述时写。

---

## 4. JWT 有效期（若 PRD 写明 24h）

- Token 未过期：受保护接口 200  
- Token 过期或篡改：401  
- 具体时钟模拟方式标「（需环境）」或待澄清

---

## 5. 与核心流程的关系

- **核心流程** 通常取「ACTIVE + 库存充足 + 主路径下单成功」  
- **时间/状态边界** 放在 **详细功能点** 的 V-/T- 编号下

详见 `core_flow_testing.md`。
